import logging
from uuid import UUID

from django.core.cache import cache

ARCHIVE_DOWNLOAD_CANCEL_TTL_SECONDS = 300
logger = logging.getLogger(__name__)


def request_archive_download_cancel(*, user_id: int, download_id: UUID) -> None:
    cache.set(
        _cache_key(user_id=user_id, download_id=download_id),
        True,
        timeout=ARCHIVE_DOWNLOAD_CANCEL_TTL_SECONDS,
    )


def archive_download_is_canceled(*, user_id: int, download_id: UUID) -> bool:
    try:
        return bool(cache.get(_cache_key(user_id=user_id, download_id=download_id)))
    except Exception:
        logger.exception("Failed to read archive download cancellation state")
        return False


def clear_archive_download_cancel(*, user_id: int, download_id: UUID) -> None:
    try:
        cache.delete(_cache_key(user_id=user_id, download_id=download_id))
    except Exception:
        logger.exception("Failed to clear archive download cancellation state")


def _cache_key(*, user_id: int, download_id: UUID) -> str:
    return f"document-archive-download-cancel:{user_id}:{download_id}"
