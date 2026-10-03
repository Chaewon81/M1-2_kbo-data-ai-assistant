"""Exercise the real application retry wrapper with a stub SDK, not a DB."""
import unittest
from unittest.mock import MagicMock, patch
from google.api_core.exceptions import Aborted, DeadlineExceeded
from backend.services import deletion_service as deletion


class TransactionRetryTests(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock()
        self.client.transaction.side_effect = lambda **kwargs: object()
        fake_sdk = patch.object(deletion.firestore, 'transactional', side_effect=lambda operation: operation)
        fake_sdk.start(); self.addCleanup(fake_sdk.stop)
        sleep = patch.object(deletion.time, 'sleep')
        sleep.start(); self.addCleanup(sleep.stop)

    def test_aborted_read_restarts_with_fresh_transaction_and_snapshot(self):
        seen, events, current = [], [], {'manual': False}
        def operation(transaction):
            seen.append(transaction)
            if len(seen) == 1:
                current['manual'] = True
                raise Aborted('Simulated read-stage conflict')
            return current['manual']
        self.assertTrue(deletion.transactionally(self.client, operation, events.append))
        self.assertEqual(len(seen), 2)
        self.assertIsNot(seen[0], seen[1])
        self.assertEqual(events, [{'kind': 'operation_aborted', 'next_attempt': 2}])

    def test_aborted_is_bounded_to_three_outer_attempts(self):
        operation = MagicMock(side_effect=Aborted('conflict'))
        with self.assertRaises(Aborted):
            deletion.transactionally(self.client, operation)
        self.assertEqual(operation.call_count, 3)

    def test_uncertain_timeout_not_retried(self):
        operation = MagicMock(side_effect=DeadlineExceeded('uncertain'))
        with self.assertRaises(DeadlineExceeded):
            deletion.transactionally(self.client, operation)
        self.assertEqual(operation.call_count, 1)

    def test_validation_and_exhausted_sdk_commit_not_retried(self):
        for error in (ValueError('bad input'), ValueError('SDK attempts exhausted')):
            with self.subTest(error=str(error)):
                operation = MagicMock(side_effect=error)
                with self.assertRaises(ValueError):
                    deletion.transactionally(self.client, operation)
                self.assertEqual(operation.call_count, 1)


if __name__ == '__main__':
    unittest.main()
