import hashlib
import hmac
import secrets

from django.conf import settings


def generate_temporary_access_token() -> str:
    return secrets.token_urlsafe(32)


def hash_temporary_access_token(token: str) -> str:
    return hmac.new(
        key=settings.SECRET_KEY.encode("utf-8"),
        msg=token.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()
