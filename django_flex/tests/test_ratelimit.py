"""
Tests for django_flex.ratelimit module.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestResolveRateLimit:
    """Tests for resolve_rate_limit function."""

    def test_no_permissions_returns_global(self):
        from django_flex.ratelimit import resolve_rate_limit

        with patch("django_flex.ratelimit.flex_settings") as mock_settings:
            mock_settings.PERMISSIONS = {}
            mock_settings.rate_limit = 100

            result = resolve_rate_limit("booking", "authenticated", "query")
            assert result == 100

    def test_model_integer_limit(self):
        from django_flex.ratelimit import resolve_rate_limit

        permissions = {
            "booking": {
                "rate_limit": 50,
                "authenticated": {"fields": ["*"], "ops": ["query"]},
            }
        }

        result = resolve_rate_limit("booking", "authenticated", "query", permissions)
        assert result == 50

    def test_model_dict_limit_action_specific(self):
        from django_flex.ratelimit import resolve_rate_limit

        permissions = {
            "booking": {
                "rate_limit": {"default": 50, "query": 30},
                "authenticated": {"fields": ["*"], "ops": ["query"]},
            }
        }

        result = resolve_rate_limit("booking", "authenticated", "query", permissions)
        assert result == 30

    def test_model_dict_limit_default(self):
        from django_flex.ratelimit import resolve_rate_limit

        permissions = {
            "booking": {
                "rate_limit": {"default": 50, "query": 30},
                "authenticated": {"fields": ["*"], "ops": ["query"]},
            }
        }

        # 'get' not in dict, should use default
        result = resolve_rate_limit("booking", "authenticated", "get", permissions)
        assert result == 50

    def test_role_integer_limit_overrides_model(self):
        from django_flex.ratelimit import resolve_rate_limit

        permissions = {
            "booking": {
                "rate_limit": 50,
                "authenticated": {
                    "fields": ["*"],
                    "ops": ["query"],
                    "rate_limit": 20,
                },
            }
        }

        result = resolve_rate_limit("booking", "authenticated", "query", permissions)
        assert result == 20

    def test_role_dict_limit_action_specific(self):
        from django_flex.ratelimit import resolve_rate_limit

        permissions = {
            "booking": {
                "rate_limit": 50,
                "authenticated": {
                    "fields": ["*"],
                    "ops": ["query"],
                    "rate_limit": {"default": 30, "query": 10},
                },
            }
        }

        result = resolve_rate_limit("booking", "authenticated", "query", permissions)
        assert result == 10

    def test_role_without_limit_uses_model_limit(self):
        from django_flex.ratelimit import resolve_rate_limit

        permissions = {
            "booking": {
                "rate_limit": 50,
                "authenticated": {
                    "fields": ["*"],
                    "ops": ["query"],
                    # No rate_limit for this role
                },
            }
        }

        result = resolve_rate_limit("booking", "authenticated", "query", permissions)
        assert result == 50

    def test_different_roles_different_limits(self):
        from django_flex.ratelimit import resolve_rate_limit

        permissions = {
            "booking": {
                "rate_limit": 50,
                "authenticated": {
                    "fields": ["*"],
                    "ops": ["query"],
                    "rate_limit": 20,
                },
                "staff": {
                    "fields": ["*"],
                    "ops": ["query"],
                    "rate_limit": 200,
                },
            }
        }

        auth_limit = resolve_rate_limit("booking", "authenticated", "query", permissions)
        staff_limit = resolve_rate_limit("booking", "staff", "query", permissions)

        assert auth_limit == 20
        assert staff_limit == 200


class TestCheckRateLimit:
    """Tests for check_rate_limit function."""

    def test_anonymous_user_always_allowed(self):
        from django_flex.ratelimit import check_rate_limit

        allowed, retry_after = check_rate_limit(None, "booking", "query")
        assert allowed is True
        assert retry_after == 0

    def test_superuser_bypasses_limits(self):
        from django_flex.ratelimit import check_rate_limit

        user = MagicMock()
        user.is_authenticated = True
        user.is_superuser = True

        permissions = {"booking": {"rate_limit": 1}}

        allowed, retry_after = check_rate_limit(user, "booking", "query", permissions)
        assert allowed is True
        assert retry_after == 0

    def test_no_limit_configured_always_allowed(self):
        from django_flex.ratelimit import check_rate_limit

        user = MagicMock()
        user.is_authenticated = True
        user.is_superuser = False
        user.is_staff = False
        user.groups.first.return_value = None

        # No rate_limit in permissions
        permissions = {"booking": {"authenticated": {"fields": ["*"], "ops": ["query"]}}}

        with patch("django_flex.ratelimit.flex_settings") as mock_settings, patch("django_flex.permissions.get_user_role") as mock_get_role:
            mock_settings.PERMISSIONS = permissions
            mock_settings.rate_limit = None
            mock_get_role.return_value = "authenticated"

            allowed, retry_after = check_rate_limit(user, "booking", "query", permissions)
            assert allowed is True

    def test_within_limit_allowed(self):
        from django_flex.ratelimit import check_rate_limit

        user = MagicMock()
        user.pk = 123
        user.is_authenticated = True
        user.is_superuser = False
        user.is_staff = False
        user.groups.first.return_value = None

        permissions = {
            "booking": {
                "rate_limit": 10,
                "authenticated": {"fields": ["*"], "ops": ["query"]},
            }
        }

        with patch("django_flex.ratelimit.cache") as mock_cache, patch("django_flex.permissions.get_user_role") as mock_get_role:
            mock_cache.get.return_value = 5  # 5 requests so far, limit is 10
            mock_get_role.return_value = "authenticated"

            allowed, retry_after = check_rate_limit(user, "booking", "query", permissions)
            assert allowed is True

    def test_at_limit_rejected(self):
        from django_flex.ratelimit import check_rate_limit

        user = MagicMock()
        user.pk = 123
        user.is_authenticated = True
        user.is_superuser = False
        user.is_staff = False
        user.groups.first.return_value = None

        permissions = {
            "booking": {
                "rate_limit": 10,
                "authenticated": {"fields": ["*"], "ops": ["query"]},
            }
        }

        with patch("django_flex.ratelimit.cache") as mock_cache, patch("django_flex.permissions.get_user_role") as mock_get_role:
            mock_cache.get.return_value = 10  # At limit
            mock_get_role.return_value = "authenticated"

            allowed, retry_after = check_rate_limit(user, "booking", "query", permissions)
            assert allowed is False
            assert retry_after > 0


class TestGetRateLimitKey:
    """Tests for get_rate_limit_key function."""

    def test_key_format(self):
        from django_flex.ratelimit import get_rate_limit_key

        key = get_rate_limit_key(123, "booking", "query")

        assert key.startswith("flex_rate:123:booking:query:")
        # Should end with minute timestamp
        assert len(key.split(":")) == 5
