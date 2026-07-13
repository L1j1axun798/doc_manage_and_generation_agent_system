from typing import cast
from urllib.parse import quote

from django.conf import settings
from django.core.files.base import File
from django.http import FileResponse, HttpResponse


def protected_download_response(
    *,
    file_handle: File,
    storage_path: str,
    filename: str,
    file_size: int,
) -> HttpResponse:
    encoded_filename = quote(filename, safe="")
    response: HttpResponse
    if getattr(settings, "USE_X_ACCEL_REDIRECT", False):
        file_handle.close()
        response = HttpResponse(content_type="application/octet-stream")
        safe_uri = "/".join(quote(part, safe="") for part in storage_path.split("/"))
        response["X-Accel-Redirect"] = f"{settings.X_ACCEL_REDIRECT_PREFIX}{safe_uri}"
    else:
        response = cast(
            HttpResponse,
            FileResponse(
                file_handle,
                as_attachment=True,
                content_type="application/octet-stream",
            ),
        )
    response["Content-Disposition"] = f"attachment; filename*=UTF-8''{encoded_filename}"
    response["Content-Length"] = str(file_size)
    response["X-Content-Type-Options"] = "nosniff"
    return response
