"""
Tests for ROLE_RESOLVER feature in django_flex.permissions.

Tests cover:
- Custom role resolver returning string (role only)
- Custom role resolver returning tuple (role, row_filter)
- Row filter fallback behavior in check_permission
- Config rows override resolver's row_filter
"""

import pytest
from unittest.mock import Mock, patch
from django.db.models import Q


class TestGetUserRoleWithResolver:
    """Tests for get_user_role with custom ROLE_RESOLVER."""

    def test_resolver_returning_string(self):
        """Resolver that returns just a role string."""
        from django_flex.permissions import get_user_role

        user = Mock()
        user.is_authenticated = True
        user.is_superuser = False
        user.is_staff = False

        def simple_resolver(user, model_name):
            return "custom_role"

        with patch("django_flex.permissions.flex_settings") as mock_settings:
            mock_settings.ROLE_RESOLVER = simple_resolver
            result = get_user_role(user, "booking")

        assert result == "custom_role"

    def test_resolver_returning_tuple(self):
        """Resolver that returns (role, row_filter) tuple."""
        from django_flex.permissions import get_user_role

        user = Mock()
        user.is_authenticated = True
        user.is_superuser = False
        user.is_staff = False
        user.pk = 42

        expected_filter = Q(company__user=user)

        def tuple_resolver(user, model_name):
            return ("manager", expected_filter)

        with patch("django_flex.permissions.flex_settings") as mock_settings:
            mock_settings.ROLE_RESOLVER = tuple_resolver
            result = get_user_role(user, "booking")

        assert isinstance(result, tuple)
        assert result[0] == "manager"
        assert str(result[1]) == str(expected_filter)

    def test_resolver_returning_none_falls_back(self):
        """When resolver returns None, fall back to default resolution."""
        from django_flex.permissions import get_user_role

        user = Mock()
        user.is_authenticated = True
        user.is_superuser = True
        user.is_staff = False

        def none_resolver(user, model_name):
            return None

        with patch("django_flex.permissions.flex_settings") as mock_settings:
            mock_settings.ROLE_RESOLVER = none_resolver
            result = get_user_role(user, "booking")

        assert result == "superuser"

    def test_resolver_role_is_lowercased(self):
        """Resolver's role should be lowercased."""
        from django_flex.permissions import get_user_role

        user = Mock()
        user.is_authenticated = True
        user.is_superuser = False
        user.is_staff = False

        def uppercase_resolver(user, model_name):
            return "OWNER"

        with patch("django_flex.permissions.flex_settings") as mock_settings:
            mock_settings.ROLE_RESOLVER = uppercase_resolver
            result = get_user_role(user, "company")

        assert result == "owner"

    def test_resolver_tuple_role_is_lowercased(self):
        """Tuple resolver's role should also be lowercased."""
        from django_flex.permissions import get_user_role

        user = Mock()
        user.is_authenticated = True
        user.is_superuser = False
        user.is_staff = False

        def tuple_resolver(user, model_name):
            return ("MANAGER", Q())

        with patch("django_flex.permissions.flex_settings") as mock_settings:
            mock_settings.ROLE_RESOLVER = tuple_resolver
            result = get_user_role(user, "company")

        assert result[0] == "manager"

    def test_no_resolver_uses_default_logic(self):
        """Without ROLE_RESOLVER, use default Django auth logic."""
        from django_flex.permissions import get_user_role

        user = Mock()
        user.is_authenticated = True
        user.is_superuser = False
        user.is_staff = True

        with patch("django_flex.permissions.flex_settings") as mock_settings:
            mock_settings.ROLE_RESOLVER = None
            result = get_user_role(user, "booking")

        assert result == "staff"

    def test_model_name_passed_to_resolver(self):
        """Model name should be passed to the resolver."""
        from django_flex.permissions import get_user_role

        user = Mock()
        user.is_authenticated = True

        received_model_name = []

        def capturing_resolver(user, model_name):
            received_model_name.append(model_name)
            return "test_role"

        with patch("django_flex.permissions.flex_settings") as mock_settings:
            mock_settings.ROLE_RESOLVER = capturing_resolver
            get_user_role(user, "my_model")

        assert received_model_name == ["my_model"]


class TestCheckPermissionWithResolverRowFilter:
    """Tests for check_permission using resolver's row_filter."""

    def test_uses_resolver_row_filter_when_config_has_no_rows(self):
        """When config doesn't specify rows, use resolver's row_filter."""
        from django_flex.permissions import check_permission

        user = Mock()
        user.is_authenticated = True
        user.is_superuser = False
        user.pk = 42

        resolver_filter = Q(company_id=99)

        def tuple_resolver(user, model_name):
            return ("editor", resolver_filter)

        permissions = {
            "article": {
                "editor": {
                    "fields": ["id", "title"],
                    "ops": ["get", "list"],
                    # No "rows" key - should use resolver's filter
                }
            }
        }

        with patch("django_flex.permissions.flex_settings") as mock_settings:
            mock_settings.ROLE_RESOLVER = tuple_resolver
            mock_settings.PERMISSIONS = permissions
            mock_settings.MAX_RELATION_DEPTH = 2
            row_filter, fields = check_permission(user, "article", "get", ["id"], permissions)

        assert str(row_filter) == str(resolver_filter)

    def test_config_rows_override_resolver_row_filter(self):
        """Config's rows should override resolver's row_filter."""
        from django_flex.permissions import check_permission

        user = Mock()
        user.is_authenticated = True
        user.is_superuser = False
        user.pk = 42

        resolver_filter = Q(company_id=99)
        config_filter = Q(owner_id=user.pk)

        def tuple_resolver(user, model_name):
            return ("editor", resolver_filter)

        permissions = {
            "article": {
                "editor": {
                    "fields": ["id", "title"],
                    "ops": ["get", "list"],
                    "rows": lambda u: config_filter,  # Override resolver
                }
            }
        }

        with patch("django_flex.permissions.flex_settings") as mock_settings:
            mock_settings.ROLE_RESOLVER = tuple_resolver
            mock_settings.PERMISSIONS = permissions
            mock_settings.MAX_RELATION_DEPTH = 2
            row_filter, fields = check_permission(user, "article", "get", ["id"], permissions)

        assert str(row_filter) == str(config_filter)

    def test_config_rows_star_allows_all(self):
        """Config rows='*' should allow all rows (no filter)."""
        from django_flex.permissions import check_permission

        user = Mock()
        user.is_authenticated = True
        user.is_superuser = False
        user.pk = 42

        resolver_filter = Q(company_id=99)

        def tuple_resolver(user, model_name):
            return ("admin", resolver_filter)

        permissions = {
            "article": {
                "admin": {
                    "fields": ["*"],
                    "ops": ["get", "list"],
                    "rows": "*",  # All rows
                }
            }
        }

        with patch("django_flex.permissions.flex_settings") as mock_settings:
            mock_settings.ROLE_RESOLVER = tuple_resolver
            mock_settings.PERMISSIONS = permissions
            mock_settings.MAX_RELATION_DEPTH = 2
            row_filter, fields = check_permission(user, "article", "get", ["id"], permissions)

        # Empty Q() means no filter (all rows)
        assert str(row_filter) == str(Q())

    def test_no_row_filter_anywhere_allows_all(self):
        """Without rows in config or resolver, allow all rows."""
        from django_flex.permissions import check_permission

        user = Mock()
        user.is_authenticated = True
        user.is_superuser = False
        user.pk = 42

        def string_resolver(user, model_name):
            return "viewer"  # No row_filter

        permissions = {
            "article": {
                "viewer": {
                    "fields": ["id", "title"],
                    "ops": ["get", "list"],
                    # No "rows" key
                }
            }
        }

        with patch("django_flex.permissions.flex_settings") as mock_settings:
            mock_settings.ROLE_RESOLVER = string_resolver
            mock_settings.PERMISSIONS = permissions
            mock_settings.MAX_RELATION_DEPTH = 2
            row_filter, fields = check_permission(user, "article", "get", ["id"], permissions)

        # No filter = all rows
        assert str(row_filter) == str(Q())


class TestTupleHandlingInOtherFunctions:
    """Tests for tuple handling in check_filter_permission and check_order_permission."""

    def test_check_filter_permission_handles_tuple(self):
        """check_filter_permission should handle tuple from resolver."""
        from django_flex.permissions import check_filter_permission

        user = Mock()
        user.is_authenticated = True

        def tuple_resolver(user, model_name):
            return ("editor", Q(pk=1))

        permissions = {
            "article": {
                "editor": {
                    "fields": ["id"],
                    "filters": ["id", "status"],
                    "ops": ["get"],
                }
            }
        }

        with patch("django_flex.permissions.flex_settings") as mock_settings:
            mock_settings.ROLE_RESOLVER = tuple_resolver
            mock_settings.PERMISSIONS = permissions
            mock_settings.MAX_RELATION_DEPTH = 2
            # Should not raise
            check_filter_permission(user, "article", ["id"], permissions)

    def test_check_order_permission_handles_tuple(self):
        """check_order_permission should handle tuple from resolver."""
        from django_flex.permissions import check_order_permission

        user = Mock()
        user.is_authenticated = True

        def tuple_resolver(user, model_name):
            return ("editor", Q(pk=1))

        permissions = {
            "article": {
                "editor": {
                    "fields": ["id"],
                    "order_by": ["created_at", "-created_at"],
                    "ops": ["get"],
                }
            }
        }

        with patch("django_flex.permissions.flex_settings") as mock_settings:
            mock_settings.ROLE_RESOLVER = tuple_resolver
            mock_settings.PERMISSIONS = permissions
            # Should not raise
            check_order_permission(user, "article", "created_at", permissions)
