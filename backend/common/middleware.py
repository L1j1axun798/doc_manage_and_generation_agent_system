from collections.abc import Callable
from uuid import uuid4

from django.http import HttpRequest, HttpResponse


class RequestIDMiddleware:
    response_header_name = "X-Request-ID"

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request_id = uuid4().hex
        request.request_id = request_id  # type: ignore[attr-defined]
        response = self.get_response(request)
        response[self.response_header_name] = request_id
        return response
