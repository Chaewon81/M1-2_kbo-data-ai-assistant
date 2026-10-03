"""On-visit regular-season sync. Shared lease + fenced per-game transactions.

No AI calls; stored conversations and canonical CSV snapshots are never updated.
"""
import logging
from collections import defaultdict
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from backend.config import settings
from backend.models.schemas import DataRecord
from backend.services.firebase_service import get_firestore_client
from backend.services.deletion_service import DELETION_COLLECTION, transactionally
from backend.scripts.repair_missing_games import build_pairs
from backend.scripts.import_to_firestore import row_to_document

KST = timezone(timedelta(hours=9))
STATE_COLLECTION, STATE_ID = 'sync_control', 'regular_games'
LEASE_SECONDS, SUCCESS_COOLDOWN, FAILURE_COOLDOWN = 600, 1800, 300
FULL_AUDIT_DAYS, OVERLAP_DAYS = 7, 7
logger = logging.getLogger(__name__)


def utcnow():
    return datetime.now(timezone.utc)


def timestamp(value):
    return datetime.fromisoformat(value) if value else datetime.min.replace(tzinfo=timezone.utc)


class LeaseLost(RuntimeError):
    pass


class UnexpectedEmptyAudit(ValueError):
    pass


def assert_owner(state, owner, now):
    if state.get('owner') != owner or state.get('status') != 'running' or timestamp(state.get('lease_until')) <= now:
        raise LeaseLost('Expired or superseded sync owner')


def collect_window(start, cutoff, heartbeat):
    # Lazy import reuses the existing official collector without making calls on import.
    from backend.scripts.collect_10_teams import fetch_schedule, build_records, TEAMS
    months = [(year, month) for year in range(start.year, cutoff.year + 1) for month in range(3, 11)
              if date(year, month, 1) <= cutoff and date(year, month, 1) + timedelta(days=31) >= start]
    rows = []
    for year, month in months:
        heartbeat()
        payload = fetch_schedule(year, month)
        if not isinstance(payload, dict) or not isinstance(payload.get('rows'), list):
            raise ValueError('Unexpected KBO schedule response')
        records = build_records(payload, year, TEAMS)
        if payload['rows'] and not records:
            raise ValueError('Nonempty official response produced no team records')
        for record in records:
            if start <= date.fromisoformat(record.date) <= cutoff and record.status == 'completed':
                rows.append(asdict(record))
    heartbeat()
    return rows  # Empty is valid outside the season / on days with no completed games.


def validated_pairs(rows, season):
    ids = [row_to_document(row)[0] for row in rows]
    report = {'season': season, 'missing': [{'id': item_id} for item_id in ids]}
    return build_pairs(report, rows, max_records=max(1, len(rows)))


class GameSyncService:
    def __init__(self, client_factory=get_firestore_client, collector=collect_window, clock=utcnow):
        self.client_factory, self.collector, self.clock = client_factory, collector, clock

    @staticmethod
    def reference(client):
        return client.collection(STATE_COLLECTION).document(STATE_ID)

    @staticmethod
    def public(state):
        # Do not expose lease owners, credential errors or database internals.
        return {field: state.get(field) for field in ('status', 'last_success_at', 'last_checked_date',
                'target_date', 'target_season', 'latest_game_date', 'last_full_audit_at', 'counts', 'error', 'error_code')}

    def status(self):
        if not settings.auto_sync_enabled:
            return {'status': 'disabled'}
        snapshot = self.reference(self.client_factory()).get(timeout=10, retry=None)
        state = snapshot.to_dict() if snapshot.exists else {'status': 'idle'}
        if state.get('status') == 'running' and timestamp(state.get('lease_until')) <= self.clock():
            state = {**state, 'status': 'stale', 'error': '이전 갱신이 중단됐습니다. 다시 접속하거나 새로고침하세요.'}
        return self.public(state)

    def claim(self):
        if not settings.auto_sync_enabled:
            return {'status': 'disabled'}, None
        client = self.client_factory()
        reference = self.reference(client)
        owner = uuid4().hex
        def operation(transaction):
            now = self.clock()
            snapshot = reference.get(transaction=transaction, timeout=10, retry=None)
            state = snapshot.to_dict() if snapshot.exists else {}
            if state.get('status') == 'running' and timestamp(state.get('lease_until')) > now:
                return self.public(state), None
            if timestamp(state.get('next_allowed_at')) > now:
                return self.public(state), None
            cutoff = now.astimezone(KST).date() - timedelta(days=1)
            full = (not state.get('last_checked_date') or
                    date.fromisoformat(state['last_checked_date']).year != cutoff.year or
                    timestamp(state.get('last_full_audit_at')) <= now - timedelta(days=FULL_AUDIT_DAYS))
            start = date(cutoff.year, 3, 1) if full else min(cutoff - timedelta(days=OVERLAP_DAYS - 1),
                        date.fromisoformat(state['last_checked_date']) + timedelta(days=1))
            new = {**state, 'status': 'running', 'owner': owner, 'lease_until': (now + timedelta(seconds=LEASE_SECONDS)).isoformat(),
                   'target_date': cutoff.isoformat(), 'target_season': cutoff.year,
                   'window_start': start.isoformat(), 'full_audit': full,
                   'error': None, 'error_code': None, 'counts': {}}
            transaction.set(reference, new)
            return self.public(new), owner
        return transactionally(client, operation)

    def owned_state(self, client, transaction, owner):
        snapshot = self.reference(client).get(transaction=transaction, timeout=10, retry=None)
        state = snapshot.to_dict() if snapshot.exists else {}
        assert_owner(state, owner, self.clock())
        return state

    def heartbeat(self, client, owner):
        def operation(transaction):
            self.owned_state(client, transaction, owner)
            transaction.update(self.reference(client), {'lease_until': (self.clock() + timedelta(seconds=LEASE_SECONDS)).isoformat()})
        transactionally(client, operation)

    def apply_pair(self, client, owner, pair):
        refs = [client.collection('data').document(item_id) for item_id, _ in pair]
        markers = [client.collection(DELETION_COLLECTION).document(item_id) for item_id, _ in pair]
        def operation(transaction):
            # The owner check is in the SAME transaction as game writes (fencing).
            ownership = self.owned_state(client, transaction, owner)
            snapshots = list(client.get_all([*refs, *markers], transaction=transaction, timeout=10, retry=None))
            values = {snapshot.reference.path: snapshot for snapshot in snapshots}
            if set(values) != {reference.path for reference in [*refs, *markers]}:
                raise RuntimeError('Incomplete game/marker read')
            if any(values[reference.path].exists for reference in markers):
                return 'deleted_protected'
            if any(values[reference.path].exists and values[reference.path].to_dict().get('is_manual') is True for reference in refs):
                return 'manual_protected'
            assert_owner(ownership, owner, self.clock())
            changed = False
            for reference, (_, source) in zip(refs, pair):
                DataRecord.model_validate(source)
                existing = values[reference.path]
                if not existing.exists or any(existing.to_dict().get(k) != v for k, v in source.items()):
                    transaction.set(reference, source, merge=True)
                    changed = True
            # An incomplete official pair is filled only when BOTH sides are unprotected.
            return 'changed' if changed else 'unchanged'
        return transactionally(client, operation)

    def latest_date(self, client):
        # A bounded query; create data(status ASC, date DESC) index if console asks.
        from google.cloud.firestore_v1.base_query import FieldFilter
        query = client.collection('data').where(filter=FieldFilter('status', '==', 'completed')).order_by('date', direction='DESCENDING').limit(1)
        snapshots = list(query.stream(timeout=10, retry=None))
        return snapshots[0].to_dict().get('date') if snapshots else None

    def finish(self, client, owner, counts, latest, error=None, error_code=None):
        # Counts include only calls whose outcomes were acknowledged. An uncertain
        # commit error can leave a DB change absent from these counters.
        def operation(transaction):
            state = self.owned_state(client, transaction, owner)
            now = self.clock()
            updates = {'status': 'failed' if error else 'success', 'counts': dict(counts), 'error': error,
                       'error_code': error_code, 'lease_until': now.isoformat(),
                       'next_allowed_at': (now + timedelta(seconds=FAILURE_COOLDOWN if error else SUCCESS_COOLDOWN)).isoformat()}
            if not error:
                updates.update(last_success_at=now.isoformat(), last_checked_date=state['target_date'], latest_game_date=latest)
                if state['full_audit']:
                    updates['last_full_audit_at'] = now.isoformat()
            transaction.update(self.reference(client), updates)
        transactionally(client, operation)

    def run(self, owner):
        client = self.client_factory()
        counts = defaultdict(int)
        try:
            def read(transaction):
                return self.owned_state(client, transaction, owner)
            state = transactionally(client, read)
            start, cutoff = date.fromisoformat(state['window_start']), date.fromisoformat(state['target_date'])
            rows = self.collector(start, cutoff, lambda: self.heartbeat(client, owner))
            # Before March the configured regular-season window has not started.
            # From March onward an empty FULL audit is inconclusive, not proof of
            # a successful season-wide collection (even if opening day is later).
            if state['full_audit'] and not rows and cutoff >= date(cutoff.year, 3, 1):
                raise UnexpectedEmptyAudit('Empty full-season audit requires verification')
            pairs = validated_pairs(rows, cutoff.year)  # ALL validation before any game write.
            # Ensure the status query/index works before applying game changes.
            self.latest_date(client)
            self.heartbeat(client, owner)
            last_heartbeat = self.clock()
            for pair in pairs:
                if self.clock() - last_heartbeat >= timedelta(seconds=30):
                    self.heartbeat(client, owner)
                    last_heartbeat = self.clock()
                counts[self.apply_pair(client, owner, pair)] += 1
            self.finish(client, owner, counts, self.latest_date(client))
        except LeaseLost:
            logger.warning('Sync stopped: lease expired or ownership changed')
        except Exception as error:
            logger.exception('Game sync failed; prior per-game commits may exist')
            try:
                message = ('전체 시즌 조회 결과가 비어 확인이 필요합니다. 성공 기준일은 갱신하지 않았습니다.'
                           if isinstance(error, UnexpectedEmptyAudit) else
                           '갱신 실패. 기존 데이터는 유지됩니다. 일부 경기 반영 여부는 재확인하세요.')
                self.finish(client, owner, counts, None, message, type(error).__name__)
            except Exception:
                logger.warning('Could not record failure; lease expiry will permit recovery')


game_sync = GameSyncService()
