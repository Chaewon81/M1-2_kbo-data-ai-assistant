"""Opt-in real Firestore tests, dedicated test project, synthetic records only.

No KBO collection or AI calls. Test documents are retained for inspection.
"""
import argparse
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Barrier
from uuid import uuid4
from unittest.mock import patch

from backend.scripts.isolated_firestore_check import connect, ScopedClient


def require(condition, label):
    if not condition:
        raise AssertionError(label)


def parallel(*jobs):
    gate = Barrier(len(jobs))
    def start(job):
        gate.wait(timeout=15)
        return job()
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        futures = [pool.submit(start, job) for job in jobs]
        return [future.result(timeout=45) for future in futures]


def run_suite(raw, project):
    # Prevent imported application globals from resolving production ADC/.env.
    os.environ['LOCAL_CSV_MODE'] = 'true'
    os.environ['REQUIRE_FIRESTORE'] = 'false'
    os.environ['AUTO_SYNC_ENABLED'] = 'true'
    os.environ['OPENAI_MOCK_MODE'] = 'true'
    from backend.services import game_sync_service as sync
    from backend.services import deletion_service as deletion
    from backend.services.data_store import DataStore
    from backend.models.schemas import DataUpdate
    from google.api_core.exceptions import Aborted

    run_id = uuid4().hex[:12]
    result = {'project_id': project, 'run_id': run_id, 'ai_calls': 0, 'kbo_calls': 0,
              'synthetic_only': True, 'documents_retained': True, 'cases': []}
    now = datetime(2026, 10, 3, tzinfo=timezone.utc)
    rows = [dict(date='2026-09-29', season=2026, game_id='20260929KTHT0', team='KIA', opponent='KT',
                 home_away='home', runs_for=2, runs_against=3, result='L', status='completed', stadium='TEST ONLY',
                 memo='SYNTHETIC TEST, NOT KBO', source_url=''),
            dict(date='2026-09-29', season=2026, game_id='20260929KTHT0', team='KT', opponent='KIA',
                 home_away='away', runs_for=3, runs_against=2, result='W', status='completed', stadium='TEST ONLY',
                 memo='SYNTHETIC TEST, NOT KBO', source_url='')]

    class TestSync(sync.GameSyncService):
        def latest_date(self, client):
            # Bounded synthetic dataset; avoids provisioning an index for each
            # unique test collection. Production latest-date query is NOT tested here.
            return max((doc.to_dict()['date'] for doc in client.collection('data').limit(10).stream(timeout=10, retry=None)
                        if doc.to_dict().get('status') == 'completed'), default=None)

    def environment(name):
        client = ScopedClient(raw, project, f'kbo_it_{run_id}_{name}')
        clock = [now]
        service = TestSync(lambda: client, lambda *args: deepcopy(rows), lambda: clock[0])
        # Inject scoped DB without invoking a constructor/global ADC lookup.
        store = object.__new__(DataStore)
        store._db, store._items, store._deletions = client, {}, {}
        return client, service, store, clock

    def state(client):
        return sync.GameSyncService.reference(client).get(timeout=10, retry=None).to_dict()

    def execute(service):
        _, owner = service.claim()
        require(owner is not None, 'Expected new lease')
        service.run(owner)

    def case(name, operation):
        retry_events = []
        original_transactionally = deletion.transactionally
        def tracked(client, callback):
            return original_transactionally(client, callback, on_retry=retry_events.append)
        try:
            with patch.object(deletion, 'transactionally', side_effect=tracked), patch.object(sync, 'transactionally', side_effect=tracked):
                details = operation() or {}
            result['cases'].append({'name': name, 'status': 'PASS', **details,
                                    'operation_aborted_retries': len(retry_events)})
        except Exception as error:
            import traceback
            result['cases'].append({'name': name, 'status': 'FAILED', 'error_type': type(error).__name__,
                                    'operation_aborted_retries': len(retry_events),
                                    'failure_frames': [{'function': frame.name, 'line': frame.lineno}
                                                       for frame in traceback.extract_tb(error.__traceback__)[-8:]]})
            # Stop on unexpected failures; retain the unique namespace for inspection.
            return False
        return True

    def manual():
        client, service, store, _ = environment('manual')
        execute(service)
        item_id = '20260929KTHT0_KIA'
        store.update(item_id, DataUpdate(runs_for=9, is_manual=False))
        before = store.get(item_id).model_dump(mode='json')
        _, owner = service.claim()  # Successful run is in cooldown.
        require(owner is None, 'Cooldown must share prior status')
        # A fresh explicit lease for the pair-protection test after cooldown.
        service.clock = lambda: now + timedelta(seconds=sync.SUCCESS_COOLDOWN + 1)
        _, owner = service.claim()
        outcome = service.apply_pair(client, owner, sync.validated_pairs(rows, 2026)[0])
        require(outcome == 'manual_protected', 'Manual pair not protected')
        require(store.get(item_id).model_dump(mode='json') == before, 'Manual record changed')
        require(before['is_manual'] is True, 'Client false unlocked protection')

    def deleted():
        client, service, store, _ = environment('deleted')
        execute(service)
        item_id = '20260929KTHT0_KIA'
        require(store.delete(item_id), 'Deletion failed')
        service.clock = lambda: now + timedelta(seconds=sync.SUCCESS_COOLDOWN + 1)
        _, owner = service.claim()
        require(service.apply_pair(client, owner, sync.validated_pairs(rows, 2026)[0]) == 'deleted_protected', 'Deleted pair restored')
        require(store.get(item_id) is None, 'Deleted record exists')
        require(store.update(item_id, DataUpdate(memo='attempt to resurrect')) is None, 'Update restored deleted record')
        require(client.collection('data_deletions').document(item_id).get(timeout=10, retry=None).exists, 'Missing tombstone')

    def shared_lease():
        client, service, _, _ = environment('lease')
        other = TestSync(lambda: client, clock=lambda: now)
        claims = parallel(service.claim, other.claim)
        require(sum(owner is not None for _, owner in claims) == 1, 'Multiple owners acquired same lease')

    def update_delete_race():
        _, service, store, _ = environment('update_delete')
        execute(service)
        item_id = '20260929KTHT0_KIA'
        outcomes = parallel(lambda: store.update(item_id, DataUpdate(runs_for=9)), lambda: store.delete(item_id))
        require(outcomes[1] is True, 'Concurrent deletion failed')
        require(store.get(item_id) is None, 'Concurrent update resurrected record')
        return {'ordering': 'nondeterministic; final deletion checked', 'sdk_commit_retry_count': 'not measured'}

    def manual_import_race():
        client, service, store, _ = environment('manual_import')
        execute(service)
        item_id, source = sync.validated_pairs(rows, 2026)[0][0]
        def importer():
            try:
                deletion.create_unless_deleted(client, item_id, source)
                return 'imported_before_manual'
            except deletion.ManualRecordError:
                return 'manual_protected'
        outcomes = parallel(lambda: store.update(item_id, DataUpdate(runs_for=9)), importer)
        require(store.get(item_id).is_manual and store.get(item_id).runs_for == 9, 'Import overwrote manual value')
        return {'import_outcome': outcomes[1], 'sdk_commit_retry_count': 'not measured'}

    def sdk_retry():
        client, _, _, _ = environment('sdk_retry')
        ref = client.collection('retry_probe').document('counter')
        ref.create({'value': 0}, timeout=10, retry=None)
        transaction = client.transaction(max_attempts=3)
        original_commit = transaction._commit
        commits, attempts = [], []
        def commit_once_aborted(*args, **kwargs):
            commits.append(1)
            if len(commits) == 1:
                raise Aborted('Deliberate test fault at commit, not a server conflict')
            return original_commit(*args, **kwargs)
        def increment(tx):
            attempts.append(1)
            current = ref.get(transaction=tx, timeout=10, retry=None).to_dict()['value']
            tx.update(ref, {'value': current + 1})
        from google.cloud import firestore
        with patch.object(transaction, '_commit', side_effect=commit_once_aborted):
            firestore.transactional(increment)(transaction)
        require(len(attempts) == 2 and ref.get(timeout=10, retry=None).to_dict()['value'] == 1, 'SDK retry did not recompute safely')
        return {'attempts': len(attempts), 'fault': 'injected Aborted at SDK commit',
                'real_server_conflict_retry': 'not established by this test'}

    def failure_recovery(partial):
        client, service, store, clock = environment('partial' if partial else 'prewrite')
        execute(service)
        before = deepcopy(state(client))
        clock[0] += timedelta(seconds=sync.SUCCESS_COOLDOWN + 1)
        new_rows = [dict(row, game_id='20260930KTHT0', date='2026-09-30') for row in rows]
        more_rows = [dict(row, game_id='20261001KTHT0', date='2026-10-01') for row in rows]
        if partial:
            service.collector = lambda *args: deepcopy(rows + new_rows + more_rows)
            real_apply = service.apply_pair
            def fail_last(*args):
                if args[-1][0][1]['date'] == '2026-10-01':
                    raise RuntimeError('Deliberate pre-commit fault on final pair')
                return real_apply(*args)
            with patch.object(service, 'apply_pair', side_effect=fail_last), patch.object(sync.logger, 'exception'):
                execute(service)
        else:
            def fail_collection(*args):
                raise RuntimeError('Deliberate collection failure before any game write')
            service.collector = fail_collection
            with patch.object(sync.logger, 'exception'):
                execute(service)
        failed = state(client)
        require(failed['status'] == 'failed', 'Failure was marked successful')
        for field in ('last_success_at', 'last_checked_date', 'last_full_audit_at'):
            require(failed[field] == before[field], 'Successful metadata changed on failure')
        require(store.get('20260929KTHT0_KIA') is not None, 'Prior record lost')
        require((store.get('20260930KTHT0_KIA') is not None) == partial, 'Unexpected partial commit behavior')
        require(store.get('20261001KTHT0_KIA') is None, 'Failed pair was written')
        require(failed['counts'] == ({'unchanged': 1, 'changed': 1} if partial else {}), 'Failure counts misrepresent partial commits')
        clock[0] += timedelta(seconds=sync.FAILURE_COOLDOWN + 1)
        service.collector = lambda *args: deepcopy(rows + new_rows + more_rows)
        execute(service)
        require(state(client)['status'] == 'success', 'Recovery did not succeed')
        require(store.get('20261001KTHT0_KIA') is not None, 'Recovery missed final pair')
        return {'partial_commit_expected': partial, 'recovery': 'PASS', 'full_rollback_claimed': False}

    for name, operation in [('manual_protection', manual), ('deletion_protection', deleted),
                            ('concurrent_lease_claims', shared_lease), ('concurrent_update_delete', update_delete_race),
                            ('concurrent_manual_import', manual_import_race), ('sdk_injected_retry', sdk_retry),
                            ('failure_before_write_recovery', lambda: failure_recovery(False)),
                            ('partial_commit_failure_recovery', lambda: failure_recovery(True))]:
        if not case(name, operation):
            break
    result['status'] = 'PASS' if len(result['cases']) == 8 and all(c['status'] == 'PASS' for c in result['cases']) else 'FAILED'
    return result


def main():
    parser = argparse.ArgumentParser(description='Isolated real Firestore integration tests (synthetic data only)')
    parser.add_argument('--project-id', required=True)
    parser.add_argument('--credentials', required=True)
    parser.add_argument('--apply', action='store_true', help='Explicitly allow test-project writes')
    args = parser.parse_args()
    if not args.apply:
        raise ValueError('Writes require --apply; use isolated_firestore_check for read-only preflight')
    raw = connect(args.project_id, args.credentials)
    raw.collection('kbo_test_preflight').document('connectivity').get(timeout=10, retry=None)
    result = run_suite(raw, args.project_id)
    output = Path(__file__).resolve().parents[2] / f"data/validation/ISOLATED_FIRESTORE_{result['run_id']}.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True))
    if result['status'] != 'PASS':
        raise SystemExit(1)


if __name__ == '__main__':
    logging.getLogger('google').setLevel(logging.WARNING)
    try:
        main()
    except Exception as error:
        raise SystemExit(f'Isolated tests stopped: {type(error).__name__}. Test documents may remain; no credential details printed.') from None
