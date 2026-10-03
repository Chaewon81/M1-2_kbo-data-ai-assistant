"""Offline sync state machine and transaction-intent tests. No KBO/DB/AI calls."""
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.services import game_sync_service as sync
from backend.routers import sync as router


class Snapshot:
    def __init__(self, reference, value):
        self.reference, self.id, self.exists = reference, reference.id, value is not None
        self.value = deepcopy(value)
    def to_dict(self):
        return deepcopy(self.value)


class Reference:
    def __init__(self, client, path):
        self.client, self.path, self.id = client, path, path.split('/')[-1]
    def get(self, **kwargs):
        return Snapshot(self, self.client.docs.get(self.path))


class Collection:
    def __init__(self, client, name):
        self.client, self.name = client, name
        self.condition, self.max_count = None, None
    def document(self, item_id):
        return Reference(self.client, f'{self.name}/{item_id}')
    def where(self, *, filter):
        self.condition = (filter.field_path, filter.value)
        return self
    def order_by(self, *args, **kwargs):
        return self
    def limit(self, count):
        self.max_count = count
        return self
    def stream(self, **kwargs):
        rows = [(path, value) for path, value in self.client.docs.items() if path.startswith(f'{self.name}/')]
        if self.condition:
            field, target = self.condition
            rows = [(path, value) for path, value in rows if value.get(field) == target]
        rows.sort(key=lambda item: item[1].get('date', ''), reverse=True)
        return iter([Snapshot(Reference(self.client, path), value) for path, value in rows[:self.max_count]])


class Client:
    def __init__(self):
        self.docs = {}
    def collection(self, name):
        return Collection(self, name)
    def get_all(self, references, **kwargs):
        return iter([reference.get() for reference in reversed(references)])


class Transaction:
    def __init__(self, client):
        self.client, self.pending = client, []
    def set(self, reference, data, merge=False):
        self.pending.append((reference.path, deepcopy(data), merge))
    def update(self, reference, data):
        if reference.path not in self.client.docs:
            raise RuntimeError('Missing update')
        self.set(reference, data, merge=True)
    def commit(self):
        for path, data, merge in self.pending:
            self.client.docs[path] = {**self.client.docs.get(path, {}), **data} if merge else data


def transactionally(client, operation):
    transaction = Transaction(client)
    value = operation(transaction)
    transaction.commit()
    return value


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 2, 0, 0, tzinfo=timezone.utc)
        self.client = Client()
        self.rows = [dict(date='2026-09-30', season=2026, game_id='20260930KTHT0', team='KIA', opponent='KT',
                    home_away='home', runs_for=2, runs_against=3, result='L', status='completed', stadium='광주'),
                    dict(date='2026-09-30', season=2026, game_id='20260930KTHT0', team='KT', opponent='KIA',
                    home_away='away', runs_for=3, runs_against=2, result='W', status='completed', stadium='광주')]
        self.service = sync.GameSyncService(lambda: self.client, lambda start, cutoff, heartbeat: self.rows, lambda: self.now)
        p = patch.object(sync, 'settings', SimpleNamespace(auto_sync_enabled=True)); p.start(); self.addCleanup(p.stop)
        p = patch.object(sync, 'transactionally', side_effect=transactionally); p.start(); self.addCleanup(p.stop)
        p = patch.object(sync.logger, 'exception'); p.start(); self.addCleanup(p.stop)

    def state(self):
        return self.client.docs[f'{sync.STATE_COLLECTION}/{sync.STATE_ID}']

    def start(self):
        _, owner = self.service.claim()
        return owner

    def test_kst_yesterday_and_shared_single_owner(self):
        state, owner = self.service.claim()
        self.assertEqual(state['target_date'], '2026-10-01')
        other = sync.GameSyncService(lambda: self.client, clock=lambda: self.now)
        shared, other_owner = other.claim()
        self.assertIsNone(other_owner)
        self.assertEqual(shared['status'], 'running')
        self.assertEqual(self.state()['owner'], owner)

    def test_first_sync_applies_pair_and_marks_dates(self):
        self.service.run(self.start())
        self.assertEqual(self.state()['status'], 'success')
        self.assertEqual(self.state()['counts'], {'changed': 1})
        self.assertEqual(self.state()['last_checked_date'], '2026-10-01')
        self.assertEqual(self.state()['latest_game_date'], '2026-09-30')
        self.assertEqual(len([path for path in self.client.docs if path.startswith('data/')]), 2)

    def test_repeat_visit_cooldown_and_overlap(self):
        self.service.run(self.start())
        _, owner = self.service.claim()
        self.assertIsNone(owner)
        self.now += timedelta(seconds=sync.SUCCESS_COOLDOWN + 1)
        self.start()
        self.assertEqual(self.state()['window_start'], '2026-09-25')
        self.assertFalse(self.state()['full_audit'])

    def test_gap_and_weekly_full_audit(self):
        self.service.run(self.start())
        self.now += timedelta(days=8)
        self.start()
        self.assertTrue(self.state()['full_audit'])
        self.assertEqual(self.state()['window_start'], '2026-03-01')

    def test_deleted_side_preserves_entire_pair(self):
        self.client.docs['data_deletions/20260930KTHT0_KIA'] = {'reason': 'user_deleted'}
        self.service.run(self.start())
        self.assertEqual(self.state()['counts'], {'deleted_protected': 1})
        self.assertFalse(any(path.startswith('data/') for path in self.client.docs))

    def test_manual_side_preserves_entire_pair(self):
        self.client.docs['data/20260930KTHT0_KIA'] = {'is_manual': True, 'runs_for': 9, 'date': '2026-09-30', 'status': 'completed'}
        before = deepcopy(self.client.docs['data/20260930KTHT0_KIA'])
        self.service.run(self.start())
        self.assertEqual(self.state()['counts'], {'manual_protected': 1})
        self.assertEqual(self.client.docs['data/20260930KTHT0_KIA'], before)
        self.assertNotIn('data/20260930KTHT0_KT', self.client.docs)

    def test_official_correction_updates_both_and_conversation_unchanged(self):
        self.service.run(self.start())
        self.client.docs['conversations/saved'] = {'summary': {'wins': 6}}
        self.now += timedelta(seconds=sync.SUCCESS_COOLDOWN + 1)
        self.rows[0].update(runs_for=5, result='W')
        self.rows[1].update(runs_against=5, result='L')
        self.service.run(self.start())
        self.assertEqual(self.client.docs['data/20260930KTHT0_KIA']['runs_for'], 5)
        self.assertEqual(self.client.docs['data/20260930KTHT0_KT']['runs_against'], 5)
        self.assertEqual(self.client.docs['conversations/saved'], {'summary': {'wins': 6}})

    def test_validation_failure_keeps_old_data_and_success_date(self):
        self.service.run(self.start())
        before = deepcopy(self.client.docs['data/20260930KTHT0_KIA'])
        prior = self.state()['last_success_at']
        self.now += timedelta(seconds=sync.SUCCESS_COOLDOWN + 1)
        self.rows[0]['result'] = 'W'
        self.service.run(self.start())
        self.assertEqual(self.state()['status'], 'failed')
        self.assertEqual(self.state()['last_success_at'], prior)
        self.assertEqual(self.client.docs['data/20260930KTHT0_KIA'], before)

    def test_collection_failure_no_game_writes(self):
        self.service.collector = MagicMock(side_effect=RuntimeError('secret error'))
        self.service.run(self.start())
        self.assertEqual(self.state()['status'], 'failed')
        self.assertNotIn('secret', self.state()['error'])
        self.assertFalse(any(path.startswith('data/') for path in self.client.docs))

    def test_empty_completed_window_is_success(self):
        self.service.run(self.start())
        self.now += timedelta(seconds=sync.SUCCESS_COOLDOWN + 1)
        self.rows = []
        self.service.run(self.start())
        self.assertEqual(self.state()['status'], 'success')
        self.assertEqual(self.state()['latest_game_date'], '2026-09-30')

    def test_empty_full_audit_keeps_success_metadata(self):
        self.service.run(self.start())
        prior = deepcopy(self.state())
        self.now += timedelta(days=8)
        self.rows = []
        self.service.run(self.start())
        self.assertEqual(self.state()['status'], 'failed')
        self.assertEqual(self.state()['error_code'], 'UnexpectedEmptyAudit')
        for field in ('last_success_at', 'last_checked_date', 'last_full_audit_at'):
            self.assertEqual(self.state()[field], prior[field])

    def test_initial_empty_full_audit_is_not_success(self):
        self.rows = []
        self.service.run(self.start())
        self.assertEqual(self.state()['status'], 'failed')
        self.assertNotIn('last_full_audit_at', self.state())
        self.assertFalse(any(path.startswith('data/') for path in self.client.docs))

    def test_year_boundaries_and_preseason_empty_policy(self):
        for day, cutoff, season, status in (
            ('2027-01-01', '2026-12-31', 2026, 'failed'),
            ('2027-01-02', '2027-01-01', 2027, 'success'),
            ('2027-02-20', '2027-02-19', 2027, 'success'),
            ('2027-03-02', '2027-03-01', 2027, 'failed'),
            ('2026-11-15', '2026-11-14', 2026, 'failed'),
        ):
            with self.subTest(day=day):
                self.client.docs = {}
                self.now = datetime.fromisoformat(day).replace(tzinfo=sync.KST).astimezone(timezone.utc)
                self.rows = []
                owner = self.start()
                self.assertEqual(self.state()['target_date'], cutoff)
                self.assertEqual(self.state()['target_season'], season)
                self.assertEqual(self.state()['window_start'], f'{season}-03-01')
                self.service.run(owner)
                self.assertEqual(self.state()['status'], status)

    def test_new_year_resets_full_audit(self):
        self.service.run(self.start())
        self.now = datetime(2027, 1, 2, tzinfo=sync.KST).astimezone(timezone.utc)
        self.start()
        self.assertTrue(self.state()['full_audit'])
        self.assertEqual(self.state()['target_season'], 2027)

    def test_old_owner_cannot_write_after_new_claim(self):
        old = self.start()
        self.now += timedelta(seconds=sync.LEASE_SECONDS + 1)
        new = self.start()
        self.assertNotEqual(old, new)
        with self.assertRaises(sync.LeaseLost):
            self.service.apply_pair(self.client, old, sync.validated_pairs(self.rows, 2026)[0])
        self.assertFalse(any(path.startswith('data/') for path in self.client.docs))

    def test_preflight_query_failure_no_game_writes(self):
        with patch.object(self.service, 'latest_date', side_effect=RuntimeError('index missing')):
            self.service.run(self.start())
        self.assertEqual(self.state()['status'], 'failed')
        self.assertFalse(any(path.startswith('data/') for path in self.client.docs))

    def test_router_enqueues_no_gpt_call(self):
        app = FastAPI(); app.include_router(router.router)
        app.dependency_overrides[router.limit_triggers] = lambda: None
        with patch.object(router, 'game_sync', self.service), patch('openai.OpenAI') as ai:
            response = TestClient(app).post('/api/sync')
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()['status'], 'running')
        self.assertEqual(self.state()['status'], 'success')
        ai.assert_not_called()

    def test_disabled_has_no_storage_access(self):
        with patch.object(sync, 'settings', SimpleNamespace(auto_sync_enabled=False)):
            self.assertEqual(self.service.claim(), ({'status': 'disabled'}, None))
            self.assertEqual(self.service.status(), {'status': 'disabled'})
        self.assertEqual(self.client.docs, {})

    def test_kst_midnight_differs_from_utc_day(self):
        self.now = datetime(2026, 10, 1, 16, 0, tzinfo=timezone.utc)  # KST Oct 2, 01:00
        state, _ = self.service.claim()
        self.assertEqual(state['target_date'], '2026-10-01')

    def test_partial_failure_does_not_claim_complete(self):
        original = self.rows
        self.rows = original + [dict(row, game_id='20261001KTHT0', date='2026-10-01') for row in original]
        real_apply = self.service.apply_pair
        calls = []
        def fail_second(*args):
            calls.append(1)
            if len(calls) == 2:
                raise RuntimeError('commit failed')
            return real_apply(*args)
        with patch.object(self.service, 'apply_pair', side_effect=fail_second):
            self.service.run(self.start())
        self.assertEqual(self.state()['status'], 'failed')
        self.assertEqual(self.state()['counts'], {'changed': 1})
        self.assertEqual(len([path for path in self.client.docs if path.startswith('data/')]), 2)

    def test_public_status_hides_owner_and_marks_expired(self):
        self.start()
        state = self.service.status()
        self.assertNotIn('owner', state)
        self.now += timedelta(seconds=sync.LEASE_SECONDS + 1)
        self.assertEqual(self.service.status()['status'], 'stale')


if __name__ == '__main__':
    unittest.main()
