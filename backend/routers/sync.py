from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends
from backend.services.game_sync_service import game_sync
from backend.services.chat_guard import ChatRateLimiter
from backend.config import settings

router = APIRouter(prefix='/api/sync', tags=['sync'])
trigger_limiter = ChatRateLimiter()


def limit_triggers():
    if settings.auto_sync_enabled:
        trigger_limiter.check(10)


@router.get('/status')
def sync_status():
    try:
        return game_sync.status()
    except Exception as error:
        raise HTTPException(503, '갱신 상태를 조회하지 못했습니다. Firestore 설정·권한·quota를 확인하세요.') from error


@router.post('', status_code=202, dependencies=[Depends(limit_triggers)])
def trigger_sync(background: BackgroundTasks):
    try:
        state, owner = game_sync.claim()
    except Exception as error:
        raise HTTPException(503, '갱신 시작에 실패했습니다. 기존 데이터를 사용하고 Firestore 상태를 확인하세요.') from error
    if owner:
        background.add_task(game_sync.run, owner)
    return state
