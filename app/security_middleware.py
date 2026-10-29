from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.security import AuthSettings


class ApplicationSecurityMiddleware(BaseHTTPMiddleware):
    """Apply transport, media-type, cache, and browser security controls."""

    _documentation_paths = {"/docs", "/redoc", "/openapi.json"}
    _protected_prefixes = ("/auth", "/employees", "/admin", "/chatbot")
    _unsafe_methods = {"POST", "PUT", "PATCH"}

    def __init__(self, app, settings: AuthSettings):
        super().__init__(app)
        self.settings = settings

    def _is_secure(self, request: Request) -> bool:
        if request.url.scheme == "https":
            return True
        return self.settings.trust_proxy_headers and request.headers.get("x-forwarded-proto") == "https"

    def _is_api_path(self, path: str) -> bool:
        return path not in self._documentation_paths

    def _has_request_body(self, request: Request) -> bool:
        content_length = request.headers.get("content-length")
        return content_length not in {None, "", "0"} or "transfer-encoding" in request.headers

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if self.settings.enforce_https and not self._is_secure(request):
            https_url = request.url.replace(scheme="https")
            return RedirectResponse(str(https_url), status_code=307)

        if self._is_api_path(path) and request.method in self._unsafe_methods and self._has_request_body(request):
            content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            if content_type != "application/json":
                return JSONResponse(status_code=415, content={"detail": "Content-Type must be application/json"})

        if self._is_api_path(path):
            accepted = request.headers.get("accept", "*/*").lower()
            if "*/*" not in accepted and "application/json" not in accepted and "text/event-stream" not in accepted:
                return JSONResponse(status_code=406, content={"detail": "Requested response format is not supported"})

        response = await call_next(request)

        if self._is_api_path(path):
            response.headers["Content-Security-Policy"] = "default-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "no-referrer"
            response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
            response.headers["Server"] = ""
            if path.startswith(self._protected_prefixes):
                response.headers["Cache-Control"] = "no-store, private"
                response.headers["Pragma"] = "no-cache"
            if self.settings.enforce_https and self._is_secure(request):
                response.headers["Strict-Transport-Security"] = f"max-age={self.settings.hsts_max_age_seconds}; includeSubDomains"

        return response
