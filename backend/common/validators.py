from pathlib import PurePath
from typing import Any

from django.conf import settings
from rest_framework.exceptions import APIException, ValidationError

ALLOWED_UPLOAD_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".jpg",
    ".jpeg",
    ".png",
}


class UploadTooLarge(APIException):
    status_code = 413
    default_detail = "上传文件超过大小限制"
    default_code = "upload_too_large"


def uploaded_file_extension(uploaded_file: Any) -> str:
    return PurePath(uploaded_file.name).suffix.lower()


def validate_uploaded_file(uploaded_file: Any) -> None:
    if not getattr(uploaded_file, "name", ""):
        raise ValidationError("上传文件名称不能为空")

    extension = uploaded_file_extension(uploaded_file)
    if extension not in ALLOWED_UPLOAD_EXTENSIONS:
        allowed = "、".join(sorted(ALLOWED_UPLOAD_EXTENSIONS))
        raise ValidationError(f"不支持的文件类型，仅允许：{allowed}")

    size = getattr(uploaded_file, "size", 0)
    if size <= 0:
        raise ValidationError("上传文件不能为空")
    if size > settings.MAX_UPLOAD_SIZE_BYTES:
        raise UploadTooLarge()
