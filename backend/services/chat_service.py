from __future__ import annotations

import json

from backend.config import settings
from backend.models.schemas import ChatRequest, ChatResponse
from backend.services.conversation_store import conversation_store
from backend.services.data_store import store
from backend.services.summary_service import build_summary


class ChatConfigurationError(RuntimeError):
    pass


class ChatQuotaError(RuntimeError):
    pass


class ChatTimeoutError(RuntimeError):
    pass


class ChatProviderError(RuntimeError):
    pass


class ChatService:
    def _summary(self, request: ChatRequest) -> dict:
        items = store.list(team=request.team, season=request.season, limit=100000)
        return build_summary(items, team=request.team, season=request.season, last_n=request.last_n)

    @staticmethod
    def _system_prompt(summary: dict) -> str:
        return (
            "당신은 KBO 경기 데이터 분석 AI 비서입니다.\n"
            "반드시 아래에 제공된 데이터 요약을 근거로 답변하세요.\n"
            "요약에 없는 사실, 실시간 정보, 부상·라인업 원인은 단정하지 마세요.\n"
            "답변에는 가능하면 사용한 기간과 데이터 수를 간단히 포함하세요.\n\n"
            f"[데이터 요약]\n{json.dumps(summary, ensure_ascii=False, indent=2)}"
        )

    def answer(self, request: ChatRequest) -> ChatResponse:
        if settings.ai_provider not in {"openai", "openrouter"}:
            raise ChatConfigurationError("AI_PROVIDER는 openai 또는 openrouter여야 합니다.")
        api_key = settings.openrouter_api_key if settings.ai_provider == "openrouter" else settings.openai_api_key
        if not settings.openai_mock_mode and not api_key:
            raise ChatConfigurationError(
                f"{'OPENROUTER_API_KEY' if settings.ai_provider == 'openrouter' else 'OPENAI_API_KEY'}가 설정되지 않았습니다. 백엔드 환경변수 또는 .env를 확인하세요."
            )
        summary = self._summary(request)
        if request.conversation_id:
            conversation = conversation_store.get(request.conversation_id)
            if conversation is None:
                raise ValueError("conversation not found")
            conversation_id = conversation.id
        else:
            conversation_id = None

        if settings.openai_mock_mode:
            metrics = summary.get("metrics", {})
            answer = (
                "[개발용 Mock 응답] 실제 OpenAI 호출 없이 Chat 흐름을 확인했습니다.\n"
                f"대상 데이터는 {summary.get('count', 0)}건이며, "
                f"승률은 {metrics.get('win_rate', 0):.1%}입니다. "
                f"현재 추세는 {summary.get('trend', '알 수 없음')}입니다."
            )
        else:
            try:
                from openai import OpenAI, RateLimitError, APITimeoutError, APIStatusError, APIConnectionError
            except ImportError as error:
                raise ChatConfigurationError("openai 패키지가 설치되지 않았습니다.") from error
            try:
                if settings.ai_provider == "openrouter":
                    client = OpenAI(
                        api_key=settings.openrouter_api_key,
                        timeout=45.0,
                        max_retries=0,
                        base_url="https://openrouter.ai/api/v1",
                        default_headers={
                            "HTTP-Referer": "http://127.0.0.1:5500",
                            "X-Title": "KBO Data AI Assistant",
                        },
                    )
                    model = settings.openrouter_model
                else:
                    client = OpenAI(api_key=settings.openai_api_key, base_url="https://api.openai.com/v1", timeout=45.0, max_retries=0)
                    model = settings.openai_model
                with client:
                    response = client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": self._system_prompt(summary)},
                            {"role": "user", "content": request.message},
                        ],
                        max_tokens=500,
                        temperature=0.2,
                    )
                answer = response.choices[0].message.content
                if not answer or not answer.strip():
                    raise ChatProviderError("AI가 빈 답변을 반환했습니다. 잠시 후 다시 질문해주세요.")
            except RateLimitError as error:
                code = getattr(error, "code", None)
                message = ("AI 서비스 크레딧 또는 할당량이 부족합니다. 계정 설정을 확인하거나 Mock 모드를 사용하세요."
                           if code in {"insufficient_quota", "credit_balance_exhausted"} else
                           "AI 서비스 요청 한도에 도달했습니다. 무료 한도 또는 일시적 제한일 수 있으니 잠시 후 다시 시도하세요.")
                raise ChatQuotaError(message) from error
            except APITimeoutError as error:
                raise ChatTimeoutError("AI 응답 대기 시간이 초과되었습니다. 잠시 후 다시 시도하세요.") from error
            except APIStatusError as error:
                if error.status_code in {401, 403}:
                    raise ChatConfigurationError("AI 서비스 인증에 실패했습니다. 백엔드 API 키와 사용 권한을 확인하세요.") from error
                if error.status_code == 402:
                    raise ChatQuotaError("선택한 AI 모델의 크레딧이 부족합니다. 무료 모델 설정과 계정 한도를 확인하세요.") from error
                raise ChatProviderError("AI 제공업체가 요청을 처리하지 못했습니다. 모델 가용성을 확인하고 잠시 후 다시 시도하세요.") from error
            except APIConnectionError as error:
                raise ChatProviderError("AI 서비스에 연결하지 못했습니다. 네트워크 상태를 확인하세요.") from error
        saved = conversation_store.save_exchange(conversation_id, request.message, answer, summary)
        conversation_id = saved.id
        return ChatResponse(
            answer=answer,
            conversation_id=conversation_id,
            summary=summary,
            model="mock" if settings.openai_mock_mode else (settings.openrouter_model if settings.ai_provider == "openrouter" else settings.openai_model),
        )


chat_service = ChatService()
