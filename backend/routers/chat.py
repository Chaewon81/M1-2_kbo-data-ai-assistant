from fastapi import APIRouter, HTTPException, Depends
from google.api_core.exceptions import GoogleAPICallError, RetryError

from backend.models.schemas import ChatRequest, ChatResponse
from backend.config import settings
from backend.services.chat_guard import check_chat_rate
from backend.services.firebase_service import StorageUnavailableError
from backend.services.chat_service import ChatConfigurationError, ChatQuotaError, ChatTimeoutError, ChatProviderError, chat_service


router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.get("/status")
def chat_status() -> dict:
    mock = settings.openai_mock_mode
    key = settings.openrouter_api_key if settings.ai_provider == "openrouter" else settings.openai_api_key
    return {"mode": "mock" if mock else "real", "provider": settings.ai_provider,
            "model": "mock" if mock else (settings.openrouter_model if settings.ai_provider == "openrouter" else settings.openai_model),
            "configured": mock or bool(key),
            "storage_policy": "firestore_required" if settings.require_firestore else "development_fallback_allowed"}


@router.post("", response_model=ChatResponse, dependencies=[Depends(check_chat_rate)])
def chat(request: ChatRequest) -> ChatResponse:
    try:
        return chat_service.answer(request)
    except (StorageUnavailableError, GoogleAPICallError, RetryError) as error:
        raise HTTPException(status_code=503, detail="Firestore 처리에 실패했습니다. 저장 성공으로 간주하지 말고 설정·권한·quota를 확인하세요.") from error
    except ChatConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ChatQuotaError as error:
        raise HTTPException(status_code=429, detail=str(error)) from error
    except ChatTimeoutError as error:
        raise HTTPException(status_code=504, detail=str(error)) from error
    except ChatProviderError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=502, detail="Chat 처리에 실패했습니다. 서버 상태를 확인해주세요.") from error
