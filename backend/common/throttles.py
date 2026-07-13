import hashlib

from rest_framework.throttling import SimpleRateThrottle


class LoginIPThrottle(SimpleRateThrottle):
    scope = "login_ip"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class LoginAccountThrottle(SimpleRateThrottle):
    scope = "login_account"

    def get_cache_key(self, request, view):
        username = str(request.data.get("username", "")).strip().casefold()
        if not username:
            return None
        ident = hashlib.sha256(username.encode("utf-8")).hexdigest()
        return self.cache_format % {"scope": self.scope, "ident": ident}
