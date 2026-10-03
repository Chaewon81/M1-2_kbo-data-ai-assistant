from fastapi import APIRouter

from backend.services.firebase_service import firebase_status


router = APIRouter(prefix="/api/firebase", tags=["firebase"])


@router.get("/status")
def get_firebase_status() -> dict:
    return firebase_status()
