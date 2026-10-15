"""Ограничение частоты запросов.

Скользящее окно в памяти процесса: сколько раз ключ (IP, почта, пользователь)
дёргал ручку за последние N секунд. Для одного процесса uvicorn этого хватает;
если сервер запускается в несколько воркеров или на нескольких машинах,
счётчики нужно вынести в Redis.
"""
import math
import os
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

# За обратным прокси (nginx) реальный IP приходит в X-Forwarded-For.
# Доверяем заголовку только если это явно включено, иначе его подделает кто угодно.
TRUST_PROXY = os.getenv("TRUST_PROXY", "").lower() in ("1", "true", "yes")

_hits: dict[str, deque] = defaultdict(deque)
_lock = threading.Lock()


def client_ip(request: Request) -> str:
    if TRUST_PROXY:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def hit(bucket: str, key: str, limit: int, window: int) -> None:
    """Засчитывает попытку. Если лимит превышен - 429 с Retry-After."""
    full_key = f"{bucket}:{key}"
    now = time.monotonic()

    with _lock:
        hits = _hits[full_key]
        while hits and hits[0] <= now - window:
            hits.popleft()

        if len(hits) >= limit:
            retry_after = max(1, math.ceil(hits[0] + window - now))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "message": "Слишком много запросов. Попробуйте позже.",
                    "retry_after": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        hits.append(now)


def rate_limit(bucket: str, limit: int, window: int):
    """Зависимость FastAPI: лимит по IP-адресу клиента."""
    def dependency(request: Request) -> None:
        hit(bucket, client_ip(request), limit, window)
    return dependency


def reset() -> None:
    """Сбрасывает все счётчики (для тестов)."""
    with _lock:
        _hits.clear()
