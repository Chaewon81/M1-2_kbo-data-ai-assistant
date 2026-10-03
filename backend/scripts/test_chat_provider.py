"""Provider boundary tests: no network, credentials, or Firestore writes."""
import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
import openai
from fastapi import FastAPI
from fastapi.testclient import TestClient

with patch('backend.services.firebase_service.get_firestore_client', side_effect=RuntimeError('test')):
    from backend.services import chat_service as service
    from backend.routers import chat as router


class ChatProviderTests(unittest.TestCase):
    def setUp(self):
        self.cfg = replace(service.settings, ai_provider='openrouter', openrouter_api_key='test-key',
                           openrouter_model='openrouter/free', openai_mock_mode=False)
        self.summary = {'count': 10, 'metrics': {'win_rate': 0.5}, 'trend': '유지'}
        self.conversations = MagicMock()
        self.conversations.save_exchange.return_value = SimpleNamespace(id='test-conversation')
        for target,value in [(service, None), (router, None)]:
            p = patch.object(target,'settings',self.cfg); p.start(); self.addCleanup(p.stop)
        for p in (patch.object(service,'conversation_store',self.conversations),
                  patch.object(service.chat_service,'_summary',return_value=self.summary)):
            p.start(); self.addCleanup(p.stop)
        app = FastAPI(); app.include_router(router.router)
        app.dependency_overrides[router.check_chat_rate] = lambda: None
        self.client = TestClient(app)
        self.sdk = MagicMock()
        self.sdk.__enter__.return_value = self.sdk
        p = patch('openai.OpenAI',return_value=self.sdk)
        self.factory = p.start(); self.addCleanup(p.stop)

    def request(self):
        return self.client.post('/api/chat',json={'message':'KIA 최근 경기력은?', 'team':'KIA','season':2026,'last_n':10})

    def test_real_provider_context_and_save(self):
        self.sdk.chat.completions.create.return_value = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='데이터 기준 답변'))])
        response=self.request()
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['model'],'openrouter/free')
        self.assertEqual(self.factory.call_args.kwargs['timeout'],45)
        self.assertEqual(self.factory.call_args.kwargs['max_retries'],0)
        self.assertEqual(self.factory.call_args.kwargs['base_url'],'https://openrouter.ai/api/v1')
        self.assertIn('"count": 10',self.sdk.chat.completions.create.call_args.kwargs['messages'][0]['content'])
        self.conversations.save_exchange.assert_called_once_with(None, 'KIA 최근 경기력은?', '데이터 기준 답변', self.summary)
        self.assertEqual(self.client.get('/api/chat/status').json()['mode'],'real')

    def test_rate_limit_not_always_credits(self):
        self.sdk.chat.completions.create.side_effect = openai.RateLimitError('limited',response=httpx.Response(429,request=httpx.Request('POST','https://example.test')),body={'code':'rate_limit_exceeded'})
        response=self.request()
        self.assertEqual(response.status_code,429)
        self.assertIn('요청 한도',response.json()['detail'])
        self.conversations.save_exchange.assert_not_called()

    def test_openai_gpt_provider(self):
        cfg = replace(self.cfg, ai_provider='openai', openai_api_key='test-openai-key', openai_model='gpt-4o-mini')
        self.sdk.chat.completions.create.return_value = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='GPT 테스트 답변'))])
        with patch.object(service,'settings',cfg), patch.object(router,'settings',cfg):
            response=self.request()
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()['model'],'gpt-4o-mini')
            self.assertEqual(self.factory.call_args.kwargs['base_url'],'https://api.openai.com/v1')
            self.assertEqual(self.factory.call_args.kwargs['api_key'],'test-openai-key')
            self.assertEqual(self.client.get('/api/chat/status').json()['provider'],'openai')

    def test_timeout(self):
        self.sdk.chat.completions.create.side_effect = openai.APITimeoutError(request=httpx.Request('POST','https://example.test'))
        self.assertEqual(self.request().status_code,504)
        self.conversations.save_exchange.assert_not_called()

    def test_provider_errors_do_not_leak(self):
        for status,expected in [(401,503),(402,429),(500,502)]:
            with self.subTest(status=status):
                self.sdk.chat.completions.create.side_effect = openai.APIStatusError('SECRET',response=httpx.Response(status,request=httpx.Request('POST','https://example.test')),body={})
                response=self.request()
                self.assertEqual(response.status_code,expected)
                self.assertNotIn('SECRET',response.text)

    def test_missing_key_and_mock(self):
        with patch.object(service,'settings',replace(self.cfg,openrouter_api_key=None)):
            response=self.request()
            self.assertEqual(response.status_code,503)
            self.assertIn('OPENROUTER_API_KEY',response.json()['detail'])
        with patch.object(service,'settings',replace(self.cfg,openai_mock_mode=True)):
            response=self.request()
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()['model'],'mock')
        self.factory.assert_not_called()


if __name__=='__main__':
    unittest.main()
