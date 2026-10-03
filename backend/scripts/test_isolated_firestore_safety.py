"""Offline guards only; no Firebase connection or writes."""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock
from backend.scripts.isolated_firestore_check import validate_target, ScopedClient


class SafetyTests(unittest.TestCase):
    def test_production_requested_blocked(self):
        with self.assertRaises(ValueError):
            validate_target('kbo-data-ai-assistant', 'kbo-safety-test')

    def test_production_credential_blocked(self):
        with self.assertRaises(ValueError):
            validate_target('kbo-safety-test', 'kbo-data-ai-assistant')

    def test_mismatch_and_non_test_project_blocked(self):
        for project, credential in [('kbo-safety-test', 'other-test-project'), ('kbo-demo-live', 'kbo-demo-live')]:
            with self.subTest(project=project), self.assertRaises(ValueError):
                validate_target(project, credential)

    def test_matching_test_project_allowed(self):
        validate_target('kbo-safety-test', 'kbo-safety-test')

    def test_collection_scoped_and_unknown_blocked(self):
        raw = MagicMock(project='kbo-safety-test')
        scoped = ScopedClient(raw, raw.project, 'kbo_it_abcdef123456_manual')
        scoped.collection('data')
        raw.collection.assert_called_once_with('kbo_it_abcdef123456_manual_data')
        with self.assertRaises(ValueError):
            scoped.collection('conversations')

    def test_reference_and_project_change_blocked(self):
        raw = MagicMock(project='kbo-safety-test')
        scoped = ScopedClient(raw, raw.project, 'kbo_it_abcdef123456_manual')
        with self.assertRaises(ValueError):
            scoped.get_all([SimpleNamespace(path='data/original', _client=raw)])
        raw.project = 'kbo-data-ai-assistant'
        with self.assertRaises(ValueError):
            scoped.transaction()


if __name__ == '__main__':
    unittest.main()
