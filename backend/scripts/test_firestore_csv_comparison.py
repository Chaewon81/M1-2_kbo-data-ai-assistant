"""Offline audit logic tests; no database access."""
import unittest
from backend.scripts.compare_firestore_csv import compare


class ComparisonTests(unittest.TestCase):
    def row(self):
        return {'game_id': '20260930KTHT0', 'team': 'KIA', 'season': 2026,
                'date': '2026-09-30', 'status': 'completed', 'runs_for': 2, 'runs_against': 3}

    def test_missing(self):
        report = compare([self.row()], [])
        self.assertEqual(report['missing'][0]['id'], '20260930KTHT0_KIA')
        self.assertEqual(report['teams'][0]['csv_count'], 1)

    def test_manual_difference_is_reported_not_changed(self):
        row = self.row()
        manual = dict(row, runs_for=9, is_manual=True)
        report = compare([row], [('20260930KTHT0_KIA', manual)])
        self.assertTrue(report['differences'][0]['is_manual'])
        self.assertEqual(report['manual_ids'], ['20260930KTHT0_KIA'])
        self.assertEqual(manual['runs_for'], 9)
        self.assertEqual(row['runs_for'], 2)

    def test_alternate_id_and_duplicates(self):
        row = self.row()
        report = compare([row, dict(row)], [('other-id', row), ('20260930KTHT0_KIA', dict(row))])
        self.assertEqual(len(report['extra']), 1)
        self.assertEqual(report['duplicate_game_team_keys'], ['20260930KTHT0_KIA'])
        self.assertEqual(report['csv_duplicate_keys'], ['20260930KTHT0_KIA'])
        self.assertEqual(report['document_id_mismatches'][0]['id'], 'other-id')


if __name__ == '__main__':
    unittest.main()
