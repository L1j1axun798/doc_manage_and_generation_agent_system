from .base import *  # noqa: F403

ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "test.sqlite3",  # noqa: F405
    }
}

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

WEBAUTHN_RP_ID = "testserver"
WEBAUTHN_ALLOWED_ORIGINS = ["http://testserver"]
API_REQUIRE_WEBAUTHN_SESSION = False
API_ENFORCE_PASSWORD_CHANGE = False
VALIDATE_UPLOAD_FILE_SIGNATURES = False
DOCUMENT_AGENT_ENABLED = True
DOCUMENT_AGENT_PHASE5_APPROVED = True
DOCUMENT_AGENT_ALLOW_FAKE_PROVIDER = True
