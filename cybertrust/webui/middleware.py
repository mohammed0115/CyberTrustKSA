from __future__ import annotations

from typing import Callable

from django.http import HttpRequest, HttpResponse


class WebuiLangMiddleware:
    """Persist a requested UI language in session when ?lang=ar|en is provided."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        lang = request.GET.get("lang")
        if lang in ("ar", "en"):
            request.session["lang"] = lang
        return self.get_response(request)
