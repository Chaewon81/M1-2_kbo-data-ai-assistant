"""Offline storage-policy and persistence simulation; never calls GPT/Firestore."""
import unittest
from dataclasses import replace
from unittest.mock import MagicMock, patch
from fastapi import HTTPException, FastAPI
from fastapi.testclient import TestClient
from google.api_core.exceptions import ServiceUnavailable

from backend.services import firebase_service as firebase
from backend.services.conversation_store import ConversationStore
from backend.services.chat_guard import ChatRateLimiter
from backend.services import chat_guard

with patch.object(firebase, 'firestore_required', return_value=False), patch.object(firebase, 'get_firestore_client', side_effect=RuntimeError('offline')):
    from backend.services import data_store
    from backend.routers import chat as router


class SubmissionStorageTests(unittest.TestCase):
    def test_strict_storage_has_no_fallback(self):
        with patch('backend.services.conversation_store.firestore_required', return_value=True), patch('backend.services.conversation_store.get_firestore_client', side_effect=RuntimeError('private path')):
            store = ConversationStore()
            with self.assertRaises(firebase.StorageUnavailableError):
                store.save_exchange(None, 'question', 'answer', {'count': 10})
            self.assertEqual(store._items, {})
        with patch.object(data_store, 'firestore_required', return_value=True), patch.object(data_store, 'get_firestore_client', side_effect=RuntimeError('offline')), patch.object(data_store.DataStore, 'load_csv') as load:
            with self.assertRaises(firebase.StorageUnavailableError):
                data_store.DataStore()
            load.assert_not_called()

    def test_development_fallback(self):
        with patch('backend.services.conversation_store.firestore_required', return_value=False), patch('backend.services.conversation_store.get_firestore_client', side_effect=RuntimeError('offline')):
            store = ConversationStore()
            saved = store.save_exchange(None, 'question', 'answer', {'count': 10})
            self.assertEqual(len(store.get(saved.id).messages), 2)

    def test_two_messages_and_summary_single_write_reload(self):
        db = MagicMock()
        reference = db.collection.return_value.document.return_value
        disk = {}
        reference.set.side_effect = lambda value: disk.update(value)
        reference.get.return_value.exists = True
        reference.get.return_value.to_dict.side_effect = lambda: dict(disk)
        with patch('backend.services.conversation_store.get_firestore_client', return_value=db):
            saved = ConversationStore().save_exchange(None, 'question', 'answer', {'count': 10})
            reference.get.return_value.id = saved.id
            restored = ConversationStore().get(saved.id)
            self.assertEqual(restored.summary, {'count': 10})
            self.assertEqual([m.content for m in restored.messages], ['question', 'answer'])
            reference.set.assert_called_once()
            ConversationStore().save_exchange(saved.id, 'next', 'reply', {'count': 5})
            self.assertEqual(len(ConversationStore().get(saved.id).messages), 4)
            self.assertEqual(disk['summary'], {'count': 5})

    def test_failed_write_not_reported_as_success(self):
        db = MagicMock()
        db.collection.return_value.document.return_value.set.side_effect = ServiceUnavailable('private error')
        with patch('backend.services.conversation_store.get_firestore_client', return_value=db):
            store = ConversationStore()
            with self.assertRaises(ServiceUnavailable):
                store.save_exchange(None, 'question', 'answer', {})
            self.assertEqual(store._items, {})

    def test_startup_check_sanitizes_failure(self):
        with patch.object(firebase, 'get_firestore_client', side_effect=RuntimeError('SECRET')):
            with self.assertRaises(firebase.StorageUnavailableError) as caught:
                firebase.verify_firestore_connection()
            self.assertNotIn('SECRET', str(caught.exception))

    def test_rate_limit_and_window(self):
        limiter = ChatRateLimiter()
        limiter.check(2, now=100)
        limiter.check(2, now=101)
        with self.assertRaises(HTTPException) as caught:
            limiter.check(2, now=102)
        self.assertEqual(caught.exception.status_code, 429)
        limiter.check(2, now=161)

    def test_firestore_failure_http_503(self):
        app = FastAPI()
        app.include_router(router.router)
        app.dependency_overrides[router.check_chat_rate] = lambda: None
        with patch.object(router.chat_service, 'answer', side_effect=ServiceUnavailable('SECRET')):
            response = TestClient(app).post('/api/chat', json={'message': 'question', 'team': 'KIA', 'season': 2026})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('SECRET', response.text)

    def test_http_rate_limit_prevents_chat_call(self):
        app = FastAPI()
        app.include_router(router.router)
        cfg = replace(chat_guard.settings, openai_mock_mode=False, chat_requests_per_minute=1)
        with patch.object(chat_guard, 'settings', cfg), patch.object(chat_guard, 'limiter', ChatRateLimiter()), patch.object(router.chat_service, 'answer', side_effect=ValueError('not found')) as answer:
            client = TestClient(app)
            payload = {'message': 'question', 'team': 'KIA', 'season': 2026}
            self.assertEqual(client.post('/api/chat', json=payload).status_code, 404)
            response = client.post('/api/chat', json=payload)
            self.assertEqual(response.status_code, 429)
            self.assertEqual(response.headers['Retry-After'], '60')
            answer.assert_called_once()

    def test_lifespan_connection_failure_stops_startup(self):
        from backend import main
        cfg = replace(main.settings, require_firestore=True)
        with patch.object(main, 'settings', cfg), patch.object(main, 'verify_firestore_connection', side_effect=firebase.StorageUnavailableError('offline')):
            with self.assertRaises(firebase.StorageUnavailableError):
                with TestClient(main.app):
                    self.fail('startup must not complete')

    def test_lifespan_success_no_gpt_call(self):
        from backend import main
        cfg = replace(main.settings, require_firestore=True, openai_mock_mode=False, ai_provider='openai', openai_api_key='test')
        with patch.object(main, 'settings', cfg), patch.object(main, 'verify_firestore_connection') as verify, patch('openai.OpenAI') as sdk:
            with TestClient(main.app) as client:
                self.assertEqual(client.get('/health').status_code, 200)
            verify.assert_called_once()
            sdk.assert_not_called()


if __name__ == '__main__':
    unittest.main()
