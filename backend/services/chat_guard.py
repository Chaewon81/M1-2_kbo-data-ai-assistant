"""Single-process demo limit; not a substitute for authentication or a billing cap."""
from collections import deque
from threading import Lock
from time import monotonic

from fastapi import HTTPException
from backend.config import settings


class ChatRateLimiter:
    def __init__(self):
        self.requests = deque()
        self.lock = Lock()

    def check(self, limit: int, now: float | None = None) -> None:
        current = monotonic() if now is None else now
        with self.lock:
            while self.requests and self.requests[0] <= current - 60:
                self.requests.popleft()
            if len(self.requests) >= limit:
                raise HTTPException(429, "Chat 요청이 너무 많습니다. 1분 후 다시 시도하세요.",
                                    headers={"Retry-After": "60"})
            self.requests.append(current)


limiter = ChatRateLimiter()


def check_chat_rate() -> None:
    if not settings.openai_mock_mode:
        limiter.check(settings.chat_requests_per_minute)
