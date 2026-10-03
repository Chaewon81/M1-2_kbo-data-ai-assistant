"""Offline demo-key policy and header checks; no real DB or AI."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from backend.services import access_service as access


class DemoAccessTests(unittest.TestCase):
    def setUp(self):
        self.settings = SimpleNamespace(app_env='production', demo_access_key='test-key-' + 'x' * 24,
                                        require_firestore=True, allowed_origins=('https://demo.example.com',))
        patched = patch.object(access, 'settings', self.settings)
        patched.start(); self.addCleanup(patched.stop)
        self.calls = []
        app = FastAPI()
        @app.get('/api/probe', dependencies=[Depends(access.require_demo_access)])
        def probe():
            self.calls.append(1)
            return {'ok': True}
        self.client = TestClient(app)

    def test_missing_and_wrong_keys_block_handler(self):
        for headers in ({}, {'X-Demo-Key': 'wrong'}, {'X-Demo-Key': '한글'}):
            if headers.get('X-Demo-Key') == '한글':
                # Direct dependency test covers unicode without httpx ASCII headers.
                from fastapi import HTTPException
                with self.assertRaises(HTTPException):
                    access.require_demo_access('한글')
            else:
                self.assertEqual(self.client.get('/api/probe', headers=headers).status_code, 401)
        self.assertEqual(self.calls, [])

    def test_valid_key_allows_handler(self):
        self.assertEqual(self.client.get('/api/probe', headers={'X-Demo-Key': self.settings.demo_access_key}).status_code, 200)
        self.assertEqual(len(self.calls), 1)

    def test_development_without_key_keeps_local_workflow(self):
        self.settings.app_env, self.settings.demo_access_key = 'development', None
        self.assertEqual(self.client.get('/api/probe').status_code, 200)

    def test_production_missing_key_fails_closed(self):
        self.settings.demo_access_key = None
        with self.assertRaises(RuntimeError):
            access.validate_access_settings()
        self.assertEqual(self.client.get('/api/probe').status_code, 503)

    def test_short_key_and_memory_fallback_block_startup(self):
        for values in ({'demo_access_key': 'short'}, {'require_firestore': False}):
            with self.subTest(values=values), patch.multiple(self.settings, **values), self.assertRaises(RuntimeError):
                access.validate_access_settings()

    def test_production_cors_requires_exact_https(self):
        for origin in ('*', 'http://localhost:5500', 'https://*.vercel.app'):
            with self.subTest(origin=origin), patch.object(self.settings, 'allowed_origins', (origin,)), self.assertRaises(RuntimeError):
                access.validate_access_settings()
        access.validate_access_settings()

    def test_actual_app_all_api_routes_have_server_access_dependency(self):
        with (patch('backend.services.firebase_service.get_firestore_client', side_effect=RuntimeError('offline')),
              patch('backend.services.firebase_service.firestore_required', return_value=False)):
            from backend.main import app
        operations = [(path, method, operation) for path, methods in app.openapi()['paths'].items()
                      if path.startswith('/api/') for method, operation in methods.items()]
        self.assertTrue(operations)
        client = TestClient(app)  # No lifespan/real DB startup in this offline test.
        for path, method, operation in operations:
            with self.subTest(path=path, method=method):
                self.assertIn({'DemoAccessKey': []}, operation.get('security', []))
                target = path.replace('{item_id}', 'dummy').replace('{conversation_id}', 'dummy')
                response = client.request(method.upper(), target, json={} if method in ('post', 'put') else None)
                self.assertEqual(response.status_code, 401)


if __name__ == '__main__':
    unittest.main()
