"""
Django-Flex Settings

Configuration is read from Django settings under the DJANGO_FLEX key.
All settings have sensible defaults.

Example:
    # settings.py
    DJANGO_FLEX = {
        'DEFAULT_LIMIT': 50,
        'MAX_LIMIT': 200,
        'MAX_RELATION_DEPTH': 2,
        'PERMISSIONS': {...},
    }
"""

from django.conf import settings

DEFAULTS = {
    # Pagination
    "DEFAULT_LIMIT": 50,
    "MAX_LIMIT": 200,
    # Security
    "MAX_RELATION_DEPTH": 2,
    "REQUIRE_AUTHENTICATION": True,
    "AUDIT_QUERIES": False,
    # Token authentication (H1 fix: configurable session model)
    "SESSION_MODEL": None,  # e.g., 'myapp.models.Session' - None disables token auth
    "SESSION_TOKEN_FIELD": "token",  # Field name for token lookup
    "SESSION_USER_FIELD": "user",  # Field name for user relation
    # CSRF protection (H2 fix: secure by default)
    "CSRF_EXEMPT": False,  # Set True ONLY for token-only APIs (no session auth)
    # Response behavior
    "ALWAYS_HTTP_200": False,  # When True, all responses return HTTP 200 with status_code in payload
    # Rate limiting (requests per minute, None = disabled)
    "rate_limit": None,
    "RATE_LIMIT_USE_FORWARDED_IP": False,  # Trust X-Forwarded-For for anon rate limits
    # Model permissions
    "PERMISSIONS": {},
    # Role resolution
    "ROLE_RESOLVER": None,  # Optional: callable(user, model_name) -> str for custom role lookup
    # Middleware settings
    "MIDDLEWARE_PATH": "/api/",  # Unversioned endpoint path
    "VERSIONS": {},  # Optional versioned endpoints (e.g., {'v1': {'path': '/api/v1/', ...}})
}


class FlexSettings:
    """
    A settings object that allows django-flex settings to be accessed as
    properties. For example:

        from django_flex.conf import flex_settings
        print(flex_settings.DEFAULT_LIMIT)

    Settings can be overridden in Django settings.py under DJANGO_FLEX key.
    """

    def __init__(self, defaults=None):
        self.defaults = defaults or DEFAULTS
        self._cached_attrs = set()

    @property
    def user_settings(self):
        if not hasattr(self, "_user_settings"):
            self._user_settings = getattr(settings, "DJANGO_FLEX", {})
        return self._user_settings

    def __getattr__(self, attr):
        if attr not in self.defaults:
            raise AttributeError(f"Invalid django-flex setting: '{attr}'")

        try:
            # Check if present in user settings
            # EXPOSE in settings.py maps to PERMISSIONS internally
            if attr == "PERMISSIONS" and "EXPOSE" in self.user_settings:
                val = self.user_settings["EXPOSE"]
            else:
                val = self.user_settings[attr]
        except KeyError:
            # Fall back to defaults
            val = self.defaults[attr]

        # Cache the result
        self._cached_attrs.add(attr)
        setattr(self, attr, val)
        return val

    def reload(self):
        """Reload settings (useful for testing)."""
        for attr in self._cached_attrs:
            try:
                delattr(self, attr)
            except AttributeError:
                pass
        self._cached_attrs.clear()
        if hasattr(self, "_user_settings"):
            delattr(self, "_user_settings")


flex_settings = FlexSettings(DEFAULTS)
