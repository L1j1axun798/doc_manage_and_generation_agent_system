import re
from pathlib import PurePath, PureWindowsPath
from typing import Any
from zipfile import BadZipFile, ZipFile

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
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


class UploadTooLarge(APIException):
    status_code = 413
    default_detail = "上传文件超过大小限制"
    default_code = "upload_too_large"


def uploaded_file_extension(uploaded_file: Any) -> str:
    return PurePath(normalize_upload_filename(uploaded_file.name)).suffix.lower()


def normalize_upload_filename(value: str) -> str:
    name = str(value or "").strip()
    if not name or name in {".", ".."}:
        raise ValidationError("上传文件名称不能为空")
    if any(ord(character) < 32 or ord(character) == 127 for character in name):
        raise ValidationError("文件名不能包含控制字符")
    if "/" in name or "\\" in name:
        raise ValidationError("文件名不能包含路径分隔符")
    if PurePath(name).name != name or PureWindowsPath(name).name != name:
        raise ValidationError("文件名格式不合法")
    if re.search(r'[<>:"|?*]', name):
        raise ValidationError("文件名包含不支持的字符")
    if name[-1] in {" ", "."}:
        raise ValidationError("文件名不能以空格或句点结尾")
    if PurePath(name).stem.upper() in WINDOWS_RESERVED_NAMES:
        raise ValidationError("文件名使用了系统保留名称")
    if len(name) > 255:
        raise ValidationError("文件名不能超过 255 个字符")
    return name


def validate_uploaded_file(uploaded_file: Any) -> None:
    normalize_upload_filename(getattr(uploaded_file, "name", ""))

    extension = uploaded_file_extension(uploaded_file)
    if extension not in ALLOWED_UPLOAD_EXTENSIONS:
        allowed = "、".join(sorted(ALLOWED_UPLOAD_EXTENSIONS))
        raise ValidationError(f"不支持的文件类型，仅允许：{allowed}")

    size = getattr(uploaded_file, "size", 0)
    if size <= 0:
        raise ValidationError("上传文件不能为空")
    if size > settings.MAX_UPLOAD_SIZE_BYTES:
        raise UploadTooLarge()
    if getattr(settings, "VALIDATE_UPLOAD_FILE_SIGNATURES", True):
        _validate_file_signature(uploaded_file, extension)


def _validate_file_signature(uploaded_file: Any, extension: str) -> None:
    position = uploaded_file.tell() if hasattr(uploaded_file, "tell") else 0
    try:
        uploaded_file.seek(0)
        header = uploaded_file.read(16)
        if extension == ".pdf" and not header.startswith(b"%PDF-"):
            raise ValidationError("PDF 文件内容与扩展名不一致")
        if extension == ".png" and not header.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValidationError("PNG 文件内容与扩展名不一致")
        if extension in {".jpg", ".jpeg"} and not header.startswith(b"\xff\xd8\xff"):
            raise ValidationError("JPEG 文件内容与扩展名不一致")
        if extension in {".doc", ".xls"} and not header.startswith(
            b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
        ):
            raise ValidationError("Office 文件内容与扩展名不一致")
        if extension in {".docx", ".xlsx"}:
            _validate_openxml(uploaded_file, extension)
    finally:
        uploaded_file.seek(position)


def _validate_openxml(uploaded_file: Any, extension: str) -> None:
    try:
        uploaded_file.seek(0)
        with ZipFile(uploaded_file) as archive:
            names = set(archive.namelist())
    except (BadZipFile, OSError, ValueError) as exc:
        raise ValidationError("Office Open XML 文件结构无效") from exc
    required_prefix = "word/" if extension == ".docx" else "xl/"
    if "[Content_Types].xml" not in names or not any(
        name.startswith(required_prefix) for name in names
    ):
        raise ValidationError("Office 文件内容与扩展名不一致")
