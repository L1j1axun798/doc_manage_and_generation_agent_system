import os
from urllib.parse import urlparse

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403

DEBUG = False

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_HSTS_SECONDS = SECURE_HSTS_SECONDS_VALUE  # noqa: F405
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
TRUST_PROXY_HEADERS = True
USE_X_ACCEL_REDIRECT = True
ENABLE_DJANGO_ADMIN = False
ENABLE_API_DOCS = False

if len(SECRET_KEY) < 50 or SECRET_KEY.startswith(("unsafe-", "replace-")):  # noqa: F405
    raise ImproperlyConfigured("DJANGO_SECRET_KEY 必须替换为至少 50 字符的随机生产密钥")
if not ALLOWED_HOSTS or any(  # noqa: F405
    host == "*" or host.startswith(".")
    for host in ALLOWED_HOSTS  # noqa: F405
):
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS 必须配置为精确生产域名")


def _require_https_origins(setting_name: str, origins: list[str]) -> None:
    if not origins:
        raise ImproperlyConfigured(f"{setting_name} 必须配置生产 HTTPS Origin")
    for origin in origins:
        parsed = urlparse(origin)
        if parsed.scheme != "https" or not parsed.netloc or parsed.path not in {"", "/"}:
            raise ImproperlyConfigured(f"{setting_name} 只能包含精确 HTTPS Origin")


_require_https_origins("DJANGO_CSRF_TRUSTED_ORIGINS", CSRF_TRUSTED_ORIGINS)  # noqa: F405
_require_https_origins("DJANGO_CORS_ALLOWED_ORIGINS", CORS_ALLOWED_ORIGINS)  # noqa: F405
_require_https_origins("WEBAUTHN_ALLOWED_ORIGINS", WEBAUTHN_ALLOWED_ORIGINS)  # noqa: F405
if WEBAUTHN_RP_ID not in ALLOWED_HOSTS:  # noqa: F405
    raise ImproperlyConfigured("WEBAUTHN_RP_ID 必须与生产 ALLOWED_HOSTS 中的精确域名一致")

if DOCUMENT_AGENT_ALLOW_FAKE_PROVIDER:  # noqa: F405
    raise ImproperlyConfigured("生产环境禁止启用Document Agent Fake Provider")
if DOCUMENT_AGENT_ENABLED:  # noqa: F405
    if not DOCUMENT_AGENT_PHASE5_APPROVED:  # noqa: F405
        raise ImproperlyConfigured("Document Agent未通过Phase 5门禁，禁止生产启用")
    required_agent_settings = (
        "LLM_BASE_URL",
        "LLM_API_KEY",
        "EMBEDDING_BASE_URL",
        "EMBEDDING_API_KEY",
    )
    if any(not os.environ.get(name, "").strip() for name in required_agent_settings):
        raise ImproperlyConfigured("Document Agent生产启用前必须配置真实模型和Embedding服务")
    for name in ("LLM_BASE_URL", "EMBEDDING_BASE_URL"):
        if urlparse(os.environ[name]).scheme != "https":
            raise ImproperlyConfigured(f"{name} 必须使用HTTPS")
    if urlparse(REDIS_URL).hostname not in {"127.0.0.1", "localhost", "::1"}:  # noqa: F405
        raise ImproperlyConfigured("Document Agent Redis必须仅使用本机地址")
