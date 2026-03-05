import logging
import time


class ApiLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.logger = logging.getLogger("api")

    def __call__(self, request):
        start = time.time()
        response = self.get_response(request)
        if request.path.startswith("/api/"):
            duration_ms = int((time.time() - start) * 1000)
            user = getattr(request, "user", None)
            user_id = getattr(user, "id", None)
            self.logger.info(
                "api_request method=%s path=%s status=%s user_id=%s duration_ms=%s",
                request.method,
                request.path,
                response.status_code,
                user_id,
                duration_ms,
            )
        return response
