from __future__ import annotations

import os

from backend.config import settings


class FirebaseConnectionError(RuntimeError):
    pass


class StorageUnavailableError(RuntimeError):
    pass


def firestore_required() -> bool:
    return settings.require_firestore


def verify_firestore_connection() -> None:
    try:
        client = get_firestore_client()
        next(client.collection("data").limit(1).stream(timeout=10, retry=None), None)
    except Exception as error:
        raise StorageUnavailableError("Firestore 연결에 실패했습니다. 설정·권한·quota를 확인하세요. 메모리 저장으로 전환하지 않습니다.") from error


def get_firestore_client():
    """Firebase Admin SDK를 한 번 초기화하고 Firestore client를 반환한다."""
    if os.getenv("LOCAL_CSV_MODE", "false").lower() in {"1", "true", "yes"}:
        raise FirebaseConnectionError("로컬 CSV 모드입니다. Firestore는 사용하지 않습니다.")
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
    except ImportError as error:
        raise FirebaseConnectionError(
            "firebase-admin 패키지가 설치되지 않았습니다. requirements.txt를 설치하세요."
        ) from error

    try:
        app = firebase_admin.get_app()
    except ValueError:
        credential_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if not credential_path:
            raise FirebaseConnectionError(
                "GOOGLE_APPLICATION_CREDENTIALS가 설정되지 않았습니다. "
                "서비스 계정 JSON 파일 경로를 현재 PowerShell 세션에 설정하세요."
            )
        if not os.path.isfile(credential_path):
            raise FirebaseConnectionError(
                "GOOGLE_APPLICATION_CREDENTIALS 경로의 파일을 찾을 수 없습니다. 경로를 확인하세요."
            )
        app = firebase_admin.initialize_app(credentials.Certificate(credential_path))
    return firestore.client(app)


def firebase_status() -> dict[str, str | bool]:
    try:
        client = get_firestore_client()
        # 실제 네트워크 요청으로 인증·DB 접근을 확인한다.
        next(client.collection("data").limit(1).stream(timeout=10, retry=None), None)
        return {"connected": True, "database": "firestore"}
    except Exception:  # 내부 예외·서비스 계정 경로는 응답에 노출하지 않는다.
        return {"connected": False, "database": "firestore", "error": "Firestore 연결 실패. 설정·권한·quota를 확인하세요."}
