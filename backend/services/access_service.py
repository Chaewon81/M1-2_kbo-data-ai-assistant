"""Shared demonstration access key, not per-user accounts or cost protection."""
import secrets
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader
from backend.config import settings

access_header = APIKeyHeader(name='X-Demo-Key', auto_error=False, scheme_name='DemoAccessKey')


def validate_access_settings():
    if settings.demo_access_key and len(settings.demo_access_key) < 24:
        raise RuntimeError('DEMO_ACCESS_KEY must be at least 24 characters')
    if settings.app_env == 'production':
        if not settings.demo_access_key:
            raise RuntimeError('Production requires DEMO_ACCESS_KEY')
        if not settings.require_firestore:
            raise RuntimeError('Production requires Firestore; memory fallback is forbidden')
        if any(not origin.startswith('https://') or '*' in origin for origin in settings.allowed_origins):
            raise RuntimeError('Production requires explicit HTTPS frontend origins')


def require_demo_access(value: str | None = Security(access_header)):
    expected = settings.demo_access_key
    if not expected:
        if settings.app_env == 'production':
            raise HTTPException(503, '시연 접근 설정이 필요합니다.')
        return
    if not value or not secrets.compare_digest(value.encode('utf-8'), expected.encode('utf-8')):
        raise HTTPException(401, '시연 접근 키를 확인해주세요.')
