import asyncio
import secrets
import time

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from .config import get_settings


class RequestGuardMiddleware:
    """Protect paid endpoints with optional Bearer auth and a per-process request budget."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        settings = get_settings()
        self.api_key = (settings.service_api_key or "").strip()
        self.limit = settings.api_rate_limit_per_minute
        self.window_started = time.monotonic()
        self.window_count = 0
        self.lock = asyncio.Lock()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not self._is_protected(scope):
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        if self.api_key and not self._authorized(headers):
            response = JSONResponse(
                {"detail": "缺少或无效的服务访问令牌"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
            await response(scope, receive, send)
            return
        if self.limit and not await self._within_rate_limit():
            response = JSONResponse(
                {"detail": "请求过于频繁，请稍后重试"},
                status_code=429,
                headers={"Retry-After": "60"},
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)

    @staticmethod
    def _is_protected(scope: Scope) -> bool:
        path = scope.get("path", "")
        if path in {"/", "/health", "/openapi.json", "/redoc"} or path.startswith("/docs"):
            return False
        return scope.get("method") != "OPTIONS"

    def _authorized(self, headers: Headers) -> bool:
        authorization = headers.get("authorization", "")
        candidate = authorization[7:] if authorization.startswith("Bearer ") else headers.get("x-api-key", "")
        return bool(candidate) and secrets.compare_digest(candidate, self.api_key)

    async def _within_rate_limit(self) -> bool:
        async with self.lock:
            now = time.monotonic()
            if now - self.window_started >= 60:
                self.window_started, self.window_count = now, 0
            if self.window_count >= self.limit:
                return False
            self.window_count += 1
            return True
