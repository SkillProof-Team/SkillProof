"""Host, Origin and request-size checks for API requests."""
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.datastructures import MutableHeaders
from .config import Settings
from .security import validate_origin
from .url_validation import authority_hostname


class RequestGuard:
    """ASGI body limit works for both Content-Length and chunked requests."""

    def __init__(self, app, settings: Settings):
        self.app = app
        self.settings = settings

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request = Request(scope)

        async def secure_send(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
                headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
                headers["Content-Security-Policy"] = (
                    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
                )
                if scope["path"].startswith("/api"):
                    headers["Cache-Control"] = "no-store"
                if self.settings.cookie_secure:
                    headers["Strict-Transport-Security"] = "max-age=31536000"
            await send(message)

        host_headers = [value for name, value in scope.get("headers", []) if name == b"host"]
        try:
            host = authority_hostname(request.headers.get("host", ""))
        except ValueError:
            host = None
        if len(host_headers) != 1 or not host or ("*" not in self.settings.allowed_hosts and host not in self.settings.allowed_hosts):
            await JSONResponse({"detail": "无效的服务域名"}, status_code=400)(scope, receive, secure_send)
            return
        if not validate_origin(request):
            await JSONResponse({"detail": "跨站请求已被拒绝"}, status_code=403)(scope, receive, secure_send)
            return
        if scope["path"].startswith("/api") and request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            content_length = request.headers.get("content-length")
            if content_length is not None:
                try:
                    declared_size = int(content_length)
                except ValueError:
                    declared_size = -1
                if declared_size < 0:
                    await JSONResponse({"detail": "无效的请求长度"}, status_code=400)(scope, receive, secure_send)
                    return
                if declared_size > self.settings.max_body_bytes:
                    await JSONResponse({"detail": "请求内容过大"}, status_code=413)(scope, receive, secure_send)
                    return
            chunks = []
            size = 0
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                body = message.get("body", b"")
                size += len(body)
                if size > self.settings.max_body_bytes:
                    await JSONResponse({"detail": "请求内容过大"}, status_code=413)(scope, receive, secure_send)
                    return
                chunks.append(body)
                if not message.get("more_body", False):
                    break
            sent = False

            async def replay_receive():
                nonlocal sent
                if not sent:
                    sent = True
                    return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
                return await receive()

            await self.app(scope, replay_receive, secure_send)
        else:
            await self.app(scope, receive, secure_send)
