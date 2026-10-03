from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from google.api_core.exceptions import GoogleAPICallError, RetryError
from .services.firebase_service import StorageUnavailableError, verify_firestore_connection

from .config import settings
from .services.access_service import require_demo_access, validate_access_settings
from .routers.data import router as data_router
from .routers.summary import router as summary_router
from .routers.firebase import router as firebase_router
from .routers.conversations import router as conversations_router
from .routers.chat import router as chat_router
from .routers.predictions import router as predictions_router
from .routers.pitchers import router as pitchers_router
from .routers.sync import router as sync_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_access_settings()
    if settings.require_firestore:
        verify_firestore_connection()
        if not settings.openai_mock_mode and settings.ai_provider == "openai" and not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY가 필요합니다. 제출용 .env를 확인하세요.")
    yield


app = FastAPI(
    title=settings.app_name,
    description="KBO 10개 구단 시즌별 데이터 분석 AI Assistant API",
    version="0.1.0",
    lifespan=lifespan,
)


async def storage_error_handler(request, error):
    return JSONResponse(status_code=503, content={"detail": "Firestore 처리에 실패했습니다. 설정·권한·quota를 확인하세요. 메모리로 전환하지 않습니다."})


for error_type in (StorageUnavailableError, GoogleAPICallError, RetryError):
    app.add_exception_handler(error_type, storage_error_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for api_router in (summary_router, data_router, firebase_router, conversations_router,
                   chat_router, predictions_router, pitchers_router, sync_router):
    app.include_router(api_router, dependencies=[Depends(require_demo_access)])


@app.get("/", tags=["health"])
def health_check() -> dict[str, str]:
    return {"service": settings.app_name, "status": "ok"}


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
