"""Offline tests: no credentials, paid calls, or actual database writes."""
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from google.api_core.exceptions import AlreadyExists, ServiceUnavailable
from backend.scripts.repair_missing_games import build_pairs, run


class RepairTests(unittest.TestCase):
    def setUp(self):
        self.rows = [dict(date='2026-09-30', season='2026', game_id='20260930KTHT0',
                          team='KIA', opponent='KT', home_away='home', runs_for='2', runs_against='3', result='L', status='completed', stadium='광주'),
                     dict(date='2026-09-30', season='2026', game_id='20260930KTHT0',
                          team='KT', opponent='KIA', home_away='away', runs_for='3', runs_against='2', result='W', status='completed', stadium='광주')]
        self.report = {'season': 2026, 'missing': [{'id': '20260930KTHT0_KIA'}, {'id': '20260930KTHT0_KT'}]}
        self.pairs = build_pairs(self.report, self.rows)
        self.client = MagicMock()
        self.client.collection.side_effect = lambda name: SimpleNamespace(document=lambda item_id: SimpleNamespace(id=item_id, path=f'{name}/{item_id}'))
        self.client.get_all.return_value = [SimpleNamespace(id=i, exists=False, reference=SimpleNamespace(path=f'{collection}/{i}'))
                                            for collection in ('data', 'data_deletions') for i, _ in self.pairs[0]]
        p = patch('backend.services.deletion_service.transactionally', side_effect=lambda client, op: op(client.transaction.return_value))
        p.start(); self.addCleanup(p.stop)

    def test_preview_never_writes(self):
        result = run(self.client, self.pairs)
        self.assertEqual(result['candidate_records'], 2)
        self.assertEqual(result['created_records'], 0)
        self.client.batch.assert_not_called()
        self.client.transaction.return_value.create.assert_not_called()

    def test_create_two_documents_one_transaction(self):
        result = run(self.client, self.pairs, apply=True)
        self.assertEqual(result['created_records'], 2)
        self.assertEqual(self.client.transaction.return_value.create.call_count, 2)
        self.assertIs(self.client.get_all.call_args.kwargs['transaction'], self.client.transaction.return_value)
        self.client.transaction.return_value.set.assert_not_called()

    def test_existing_manual_or_official_never_overwritten(self):
        for manual in (False, True):
            with self.subTest(manual=manual):
                self.client.get_all.return_value[0].exists = True
                result = run(self.client, self.pairs, apply=True)
                self.assertEqual(result['results'][0]['status'], 'skipped_existing_pair')
                self.client.batch.assert_not_called()
                self.client.transaction.return_value.create.assert_not_called()

    def test_race_is_create_only_conflict(self):
        self.client.transaction.return_value.create.side_effect = AlreadyExists('race')
        result = run(self.client, self.pairs, apply=True)
        self.assertEqual(result['created_records'], 0)
        self.assertEqual(result['results'][0]['status'], 'skipped_concurrent_create')

    def test_failure_stops_and_requires_reaudit(self):
        self.client.transaction.return_value.create.side_effect = ServiceUnavailable('private details')
        result = run(self.client, self.pairs * 2, apply=True)
        self.assertEqual(len(result['results']), 1)
        self.assertEqual(result['results'][0]['status'], 'failed_or_uncertain')
        self.assertTrue(result['needs_reaudit'])

    def test_bad_pair_score_and_result_rejected(self):
        for change in ({'runs_for': '9'}, {'result': 'W'}, {'date': '2026-99-99'}, {'team': 'string'}):
            rows = deepcopy(self.rows)
            rows[0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                build_pairs(self.report, rows)

    def test_limit_partial_pair_and_conflicting_report_rejected(self):
        with self.assertRaises(ValueError):
            build_pairs(self.report, self.rows, max_records=1)
        with self.assertRaises(ValueError):
            build_pairs(dict(self.report, missing=self.report['missing'][:1]), self.rows)
        with self.assertRaises(ValueError):
            build_pairs(dict(self.report, differences=[{'id': 'conflict'}]), self.rows)
        with self.assertRaises(ValueError):
            build_pairs(self.report, self.rows + self.rows)


if __name__ == '__main__':
    unittest.main()
