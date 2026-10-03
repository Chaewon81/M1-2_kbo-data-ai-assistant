"""Offline transaction intent/CRUD tests, not real Firestore concurrency proof."""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import io
from google.api_core.exceptions import Aborted
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.services import deletion_service as deletion

with patch('backend.services.firebase_service.firestore_required', return_value=False), patch('backend.services.firebase_service.get_firestore_client', side_effect=RuntimeError('offline')):
    from backend.services.data_store import DataStore
    from backend.routers import data as router

from backend.models.schemas import DataCreate, DataUpdate


class DeletionTests(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.docs = {}
        def collection(name):
            def document(item_id):
                path = f'{name}/{item_id}'
                if path not in self.docs:
                    reference = MagicMock()
                    reference.id, reference.path = item_id, path
                    reference.get.return_value = SimpleNamespace(exists=False, id=item_id,
                                                                reference=reference, to_dict=lambda: {})
                    self.docs[path] = reference
                return self.docs[path]
            return SimpleNamespace(document=document)
        self.db.collection.side_effect = collection
        self.transaction = MagicMock()
        p = patch.object(deletion, 'transactionally', side_effect=lambda client, op: op(self.transaction))
        p.start(); self.addCleanup(p.stop)

    def test_delete_marker_and_data_in_same_transaction(self):
        record = self.db.collection('data').document('game_KIA')
        record.get.return_value.exists = True
        record.get.return_value.to_dict = lambda: {'game_id': 'game', 'team': 'KIA', 'season': 2026, 'date': '2026-09-30'}
        self.assertTrue(deletion.delete_with_marker(self.db, 'game_KIA'))
        self.transaction.set.assert_called_once()
        marker, data = self.transaction.set.call_args.args
        self.assertEqual(marker.path, 'data_deletions/game_KIA')
        self.assertEqual(data['reason'], 'user_deleted')
        self.transaction.delete.assert_called_once_with(record)
        self.assertIs(record.get.call_args.kwargs['transaction'], self.transaction)

    def test_nonexistent_delete_makes_no_marker(self):
        self.assertFalse(deletion.delete_with_marker(self.db, 'missing'))
        self.transaction.set.assert_not_called()
        self.transaction.delete.assert_not_called()

    def test_general_create_cannot_restore_deleted(self):
        marker = self.db.collection('data_deletions').document('game_KIA')
        marker.get.return_value.exists = True
        with self.assertRaises(deletion.DeletedRecordError):
            deletion.create_unless_deleted(self.db, 'game_KIA', {})
        self.transaction.set.assert_not_called()

    def test_deleted_either_side_skips_entire_pair(self):
        pair = [('game_KIA', {}), ('game_KT', {})]
        snapshots = [self.db.collection(collection).document(item_id).get.return_value
                     for collection in ('data', 'data_deletions') for item_id, _ in pair]
        snapshots[-1].exists = True
        self.db.get_all.return_value = list(reversed(snapshots))
        result = deletion.create_pair_unless_deleted(self.db, pair, apply=True)
        self.assertEqual(result['status'], 'skipped_deleted_pair')
        self.assertEqual(result['deleted_ids'], ['game_KT'])
        self.transaction.create.assert_not_called()
        self.assertIs(self.db.get_all.call_args.kwargs['transaction'], self.transaction)

    def test_incomplete_read_aborts(self):
        self.db.get_all.return_value = []
        with self.assertRaises(RuntimeError):
            deletion.create_pair_unless_deleted(self.db, [('a', {}), ('b', {})], apply=True)
        self.transaction.create.assert_not_called()

    def test_local_delete_blocks_create_and_reload(self):
        with patch('backend.services.data_store.get_firestore_client', side_effect=RuntimeError('offline')), patch('backend.services.data_store.firestore_required', return_value=False):
            store = DataStore()
            item = store.list(team='KIA', season=2026, limit=1)[0]
            self.assertTrue(store.delete(item.id))
            with self.assertRaises(deletion.DeletedRecordError):
                store.create(DataCreate.model_validate(item.model_dump()))
            store.load_csv()
            self.assertIsNone(store.get(item.id))
            self.assertFalse(store.delete(item.id))

    def test_create_conflict_http_409(self):
        app = FastAPI(); app.include_router(router.router)
        payload = {'date': '2026-09-30', 'season': 2026, 'team': 'KIA', 'opponent': 'KT',
                   'home_away': 'home', 'runs_for': 2, 'runs_against': 3, 'result': 'L',
                   'run_diff': -1, 'value': -1, 'game_id': '20260930KTHT0'}
        with patch.object(router.store, 'create', side_effect=deletion.DeletedRecordError('deleted')):
            response = TestClient(app).post('/api/data', json=payload)
        self.assertEqual(response.status_code, 409)

    def test_import_skips_deleted_record(self):
        from backend.scripts import import_to_firestore as importer
        source = 'date,season,team,opponent,home_away,runs_for,runs_against,result,game_id\n2026-09-30,2026,KIA,KT,home,2,3,L,20260930KTHT0\n'
        path = MagicMock()
        path.exists.return_value = True
        path.open.return_value = io.StringIO(source)
        with patch('sys.argv', ['import_to_firestore']), patch.object(importer, 'source_path', return_value=path), patch.object(importer, 'get_firestore_client', return_value=self.db), patch.object(importer, 'create_unless_deleted', side_effect=deletion.DeletedRecordError('deleted')) as create, patch('builtins.print'):
            importer.main()
            create.assert_called_once()
            self.db.batch.assert_not_called()

    def test_manual_import_protected_inside_transaction(self):
        record = self.db.collection('data').document('game_KIA')
        record.get.return_value.exists = True
        record.get.return_value.to_dict = lambda: {'is_manual': True, 'runs_for': 9}
        with self.assertRaises(deletion.ManualRecordError):
            deletion.create_unless_deleted(self.db, 'game_KIA', {'is_manual': False, 'runs_for': 2})
        self.assertIs(record.get.call_args.kwargs['transaction'], self.transaction)
        self.transaction.set.assert_not_called()

    def test_deleted_or_absent_update_never_creates(self):
        for deleted in (True, False):
            with self.subTest(deleted=deleted):
                self.db.collection('data_deletions').document('game_KIA').get.return_value.exists = deleted
                transform = MagicMock()
                self.assertIsNone(deletion.update_unless_deleted(self.db, 'game_KIA', transform))
                transform.assert_not_called()
                self.transaction.update.assert_not_called()
                self.transaction.set.assert_not_called()

    def test_update_delete_race_rechecks_on_transaction_retry(self):
        record = self.db.collection('data').document('game_KIA')
        marker = self.db.collection('data_deletions').document('game_KIA')
        record.get.return_value.exists = True
        record.get.return_value.to_dict = lambda: {'runs_for': 2}
        attempt_one, attempt_two = MagicMock(), MagicMock()
        def delete_between_read_and_commit(*args):
            record.get.return_value.exists = False
            marker.get.return_value.exists = True
            raise Aborted('Simulated conflict: DELETE after update snapshot')
        attempt_one.update.side_effect = delete_between_read_and_commit
        def retry(client, operation):
            try:
                return operation(attempt_one)
            except Aborted:
                return operation(attempt_two)
        with patch.object(deletion, 'transactionally', side_effect=retry):
            result = deletion.update_unless_deleted(self.db, 'game_KIA', lambda current: dict(current, runs_for=9))
        self.assertIsNone(result)
        attempt_one.update.assert_called_once()
        attempt_two.update.assert_not_called()
        attempt_two.set.assert_not_called()
        self.assertFalse(record.get.return_value.exists)

    def test_import_manual_edit_race_rechecks_on_retry(self):
        record = self.db.collection('data').document('game_KIA')
        record.get.return_value.exists = True
        data = {'is_manual': False, 'runs_for': 2}
        record.get.return_value.to_dict = lambda: dict(data)
        first, second = MagicMock(), MagicMock()
        def manual_edit(*args, **kwargs):
            data.update(is_manual=True, runs_for=9)
            raise Aborted('Simulated manual update before import commit')
        first.set.side_effect = manual_edit
        def retry(client, operation):
            try:
                return operation(first)
            except Aborted:
                return operation(second)
        with patch.object(deletion, 'transactionally', side_effect=retry), self.assertRaises(deletion.ManualRecordError):
            deletion.create_unless_deleted(self.db, 'game_KIA', {'runs_for': 2, 'is_manual': False})
        second.set.assert_not_called()
        self.assertEqual(data, {'is_manual': True, 'runs_for': 9})

    def test_update_calculates_from_transaction_snapshot(self):
        store = DataStore.__new__(DataStore)
        store._db = self.db
        record = self.db.collection('data').document('game_KIA')
        record.get.return_value.exists = True
        record.get.return_value.to_dict = lambda: {'date': '2026-09-30', 'season': 2026, 'team': 'KIA', 'opponent': 'KT',
            'home_away': 'home', 'game_id': '20260930KTHT0', 'runs_for': 2, 'runs_against': 8, 'result': 'L', 'run_diff': -6, 'value': -6}
        changed = store.update('game_KIA', DataUpdate(runs_for=9))
        self.assertEqual((changed.run_diff, changed.result, changed.is_manual), (1, 'W', True))
        self.assertIs(record.get.call_args.kwargs['transaction'], self.transaction)
        self.transaction.update.assert_called_once()
        self.transaction.set.assert_not_called()

    def test_import_reports_manual_skip(self):
        from backend.scripts import import_to_firestore as importer
        source = 'date,season,team,opponent,home_away,runs_for,runs_against,result,game_id\n2026-09-30,2026,KIA,KT,home,2,3,L,20260930KTHT0\n'
        path = MagicMock(); path.exists.return_value = True; path.open.return_value = io.StringIO(source)
        with patch('sys.argv', ['import_to_firestore']), patch.object(importer, 'source_path', return_value=path), patch.object(importer, 'get_firestore_client', return_value=self.db), patch.object(importer, 'create_unless_deleted', side_effect=deletion.ManualRecordError('manual')), patch('builtins.print') as output:
            importer.main()
            self.assertIn(('수동 수정 보호로 제외: 1건',), [call.args for call in output.call_args_list])

    def test_null_completed_score_update_http_422(self):
        with patch('backend.services.data_store.get_firestore_client', side_effect=RuntimeError('offline')), patch('backend.services.data_store.firestore_required', return_value=False):
            store = DataStore()
        item = store.list(team='KIA', season=2026, limit=1)[0]
        app = FastAPI(); app.include_router(router.router)
        with patch.object(router, 'store', store):
            response = TestClient(app).put(f'/api/data/{item.id}', json={'runs_for': None})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(store.get(item.id).runs_for, item.runs_for)

    def test_public_update_false_or_null_keeps_protection(self):
        with patch('backend.services.data_store.get_firestore_client', side_effect=RuntimeError('offline')), patch('backend.services.data_store.firestore_required', return_value=False):
            store = DataStore()
        item = store.list(team='KIA', season=2026, limit=1)[0]
        app = FastAPI(); app.include_router(router.router)
        with patch.object(router, 'store', store):
            for supplied in (False, None):
                with self.subTest(supplied=supplied):
                    response = TestClient(app).put(f'/api/data/{item.id}', json={'memo': 'user edit', 'is_manual': supplied})
                    self.assertEqual(response.status_code, 200)
                    self.assertIs(response.json()['is_manual'], True)
                    self.assertIs(store.get(item.id).is_manual, True)

    def test_firestore_update_false_or_null_is_written_as_true(self):
        store = DataStore.__new__(DataStore)
        store._db = self.db
        record = self.db.collection('data').document('game_KIA')
        record.get.return_value.exists = True
        record.get.return_value.to_dict = lambda: {'date': '2026-09-30', 'season': 2026, 'team': 'KIA', 'opponent': 'KT',
            'home_away': 'home', 'game_id': '20260930KTHT0', 'runs_for': 2, 'runs_against': 3, 'result': 'L',
            'run_diff': -1, 'value': -1, 'is_manual': True}
        for supplied in (False, None):
            with self.subTest(supplied=supplied):
                self.transaction.reset_mock()
                changed = store.update('game_KIA', DataUpdate(memo='user edit', is_manual=supplied))
                self.assertIs(changed.is_manual, True)
                self.assertIs(self.transaction.update.call_args.args[1]['is_manual'], True)
                self.assertIs(record.get.call_args.kwargs['transaction'], self.transaction)


if __name__ == '__main__':
    unittest.main()
