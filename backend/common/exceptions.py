from typing import Any

from rest_framework.response import Response
from rest_framework.views import exception_handler


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    response = exception_handler(exc, context)
    request = context.get("request")
    request_id = getattr(request, "request_id", None)

    if response is None:
        return response

    detail = response.data
    response.data = {
        "code": getattr(exc, "default_code", "error"),
        "message": _extract_message(detail),
        "errors": detail if isinstance(detail, dict) else None,
        "request_id": request_id,
    }
    return response


def _extract_message(detail: Any) -> str:
    if isinstance(detail, dict):
        value = detail.get("detail") or detail.get("non_field_errors") or detail
        return str(value)
    if isinstance(detail, list):
        return "; ".join(str(item) for item in detail)
    return str(detail)
