"""
Security Tests for H3: Anonymous User Bypasses ALL Permission Checks

This test verifies that permission checks are always enforced,
even when user=None (anonymous user).

These tests will FAIL when the vulnerability exists and PASS once fixed.

Related Issue: #4 [H3] CRITICAL: Anonymous user bypasses ALL permission checks
"""

import pytest
from unittest.mock import patch, MagicMock
from django.db.models import Q
from django.contrib.auth.models import AnonymousUser

from django_flex.tests.test_utils import run_tests


# =============================================================================
# State variables for tests
# =============================================================================
state = {
    "test_model": "user",
}


# =============================================================================
# Setup functions
# =============================================================================
def setup_permissions_with_anon(state):
    """Setup permissions config that includes anon role."""
    state["permissions"] = {
        "user": {
            "anon": {
                "rows": lambda u: Q(is_active=True, is_public=True),
                "fields": ["id", "username"],
                "ops": ["list"],
            },
            "authenticated": {
                "rows": lambda u: Q(id=u.id),
                "fields": ["id", "username", "email"],
                "ops": ["get", "list", "edit"],
            },
        }
    }


# =============================================================================
# TEST CASES
# =============================================================================
TEST_CASES = [
    # ========================================
    # H3-1: Anonymous should use 'anon' role, not bypass
    # ========================================
    {
        "name": "H3-1: Anonymous user denied when anon role not configured",
        "req": {
            "_model": "user",
            "_action": "list",
            "fields": "id, username, email",
        },
        "res": {
            "success": False,
            # Should get permission denied, not all data
        },
        "expect_error": True,  # FAILS until anon role handling added
    },
    {
        "name": "H3-2: Anonymous gets only anon-allowed fields",
        "setup": setup_permissions_with_anon,
        "req": {
            "_model": "user",
            "_action": "list",
            "fields": "id, username",  # Only anon-allowed fields
        },
        "res": {
            "success": True,
        },
        "expect_error": True,  # FAILS until anon role implemented
    },
    {
        "name": "H3-3: Anonymous denied sensitive fields even if requested",
        "setup": setup_permissions_with_anon,
        "req": {
            "_model": "user",
            "_action": "list",
            "fields": "id, username, email, password",  # Includes restricted
        },
        "res": {
            "success": False,
        },
        "expect_error": True,  # FAILS - currently returns ALL fields
    },
]


# =============================================================================
# Unit tests for the specific vulnerability
# =============================================================================
class TestH3AnonymousBypass:
    """
    Direct unit tests for the anonymous user permission bypass.

    These tests verify that permission checks are always enforced,
    even when user=None.
    """

    def test_check_permission_handles_none_user(self):
        """
        Test that check_permission works with user=None.

        Expected: Uses 'anon' role or raises PermissionError
        Actual (before fix): Returns (None, all_fields) - bypasses all checks!
        """
        from django_flex.permissions import check_permission

        permissions = {
            "user": {
                "authenticated": {
                    "rows": lambda u: Q(id=u.id),
                    "fields": ["id", "username"],
                    "ops": ["list"],
                }
                # Note: NO 'anon' role defined
            }
        }

        try:
            row_filter, fields = check_permission(
                user=None, model_name="user", action="list", requested_fields=["id", "username", "email"], permissions=permissions  # Anonymous user
            )

            # If we get here without error, check if bypass occurred
            if row_filter is None:
                pytest.fail(
                    "H3 CRITICAL VULNERABILITY: check_permission with user=None "
                    "returned row_filter=None (no filtering). "
                    "Anonymous users can see ALL data!"
                )

            # Also check if all fields were returned
            if set(fields) == {"id", "username", "email"}:
                pytest.fail(
                    "H3 CRITICAL VULNERABILITY: check_permission with user=None "
                    f"returned all requested fields: {fields}. "
                    "Anonymous users can access ALL fields!"
                )

        except PermissionError:
            # CORRECT behavior - anon role not configured, so denied
            pass

    def test_execute_with_none_user_respects_permissions(self):
        """
        Test that FlexQuery.execute with user=None respects permissions.

        Expected: Permission checks still run, uses 'anon' role
        Actual (before fix): row_filter=None, validated_fields=all_fields
        """
        from django_flex.query import FlexQuery

        permissions = {
            "testmodel": {
                "authenticated": {
                    "rows": lambda u: Q(tenant_id=u.tenant_id),
                    "fields": ["id", "name"],
                    "ops": ["list"],
                }
            }
        }

        query = FlexQuery("testmodel")

        # Execute with user=None (anonymous)
        with patch.object(query, "_get_model") as mock_get_model:
            mock_model = MagicMock()
            mock_model._meta.get_fields.return_value = []
            mock_get_model.return_value = mock_model

            result = query.execute({"_action": "list", "fields": "id, name, secret_field"}, user=None, permissions=permissions)

            # Check if permission was denied (correct) or if data leaked
            if result.data.get("success") is True:
                # If success, check that secret_field was NOT included
                # This would indicate permission bypass
                pytest.fail(
                    "H3 VULNERABILITY: Query with user=None succeeded without anon role. " "Anonymous users may be accessing restricted data."
                )

    def test_anon_role_row_filter_applied(self):
        """
        Test that anon role's row filter is actually applied.

        Expected: Q filter from anon role restricts query results
        Actual (before fix): row_filter=None, all rows returned
        """
        from django_flex.permissions import check_permission

        permissions = {
            "article": {
                "anon": {
                    "rows": Q(published=True),  # Only published articles
                    "fields": ["id", "title"],
                    "ops": ["list"],
                }
            }
        }

        try:
            row_filter, fields = check_permission(
                user=None, model_name="article", action="list", requested_fields=["id", "title"], permissions=permissions
            )

            # Verify row filter is the Q(published=True), not None
            if row_filter is None:
                pytest.fail("H3 VULNERABILITY: anon role row filter not applied. " "row_filter is None, should be Q(published=True).")

            # Check it's the right filter
            assert row_filter == Q(published=True), f"Wrong row filter: {row_filter}, expected Q(published=True)"

        except (PermissionError, AttributeError) as e:
            pytest.fail(f"H3 VULNERABILITY: anon role not properly handled: {e}")


# =============================================================================
# Attack simulation tests
# =============================================================================
class TestH3AttackSimulation:
    """
    Simulated attack scenarios demonstrating anonymous bypass impact.
    """

    def test_database_dump_via_anonymous(self):
        """
        Simulate anonymous user dumping entire database.

        Attack scenario:
        1. Attacker sends request without authentication
        2. If user=None bypasses permissions, ALL data is returned
        3. Attacker gets full database dump
        """
        from django_flex.query import FlexQuery

        # Restrictive permissions for authenticated users only
        permissions = {
            "user": {
                "authenticated": {
                    "rows": lambda u: Q(id=u.id),  # Only own record
                    "fields": ["id", "username"],
                    "ops": ["get"],
                }
            }
        }

        query = FlexQuery("user")

        with patch.object(query, "_get_model") as mock_get_model:
            mock_model = MagicMock()
            mock_model.objects.all.return_value.count.return_value = 1000
            mock_get_model.return_value = mock_model

            result = query.execute({"_action": "list", "fields": "*"}, user=None, permissions=permissions)  # Request everything  # No authentication

            if result.data.get("success") is True:
                pytest.fail("H3 CRITICAL: Anonymous user accessed data from model " "that has NO 'anon' role configured. Database dump possible!")

    def test_sensitive_field_exposure(self):
        """
        Test that sensitive fields aren't exposed to anonymous users.
        """
        from django_flex.permissions import check_permission

        permissions = {
            "user": {
                "anon": {
                    "fields": ["id", "display_name"],  # Limited fields
                    "ops": ["list"],
                },
                "authenticated": {
                    "fields": ["id", "display_name", "email", "phone"],
                    "ops": ["list", "get"],
                },
            }
        }

        try:
            row_filter, fields = check_permission(
                user=None,
                model_name="user",
                action="list",
                requested_fields=["id", "display_name", "email", "phone", "password_hash"],
                permissions=permissions,
            )

            # Verify only anon-allowed fields returned
            allowed = {"id", "display_name"}
            returned = set(fields)

            leaked = returned - allowed
            if leaked:
                pytest.fail(f"H3 VULNERABILITY: Sensitive fields exposed to anonymous: {leaked}")

        except PermissionError:
            # Acceptable - denying due to restricted field request
            pass


# =============================================================================
# Integration test runner
# =============================================================================
@pytest.fixture
def setup_db(db):
    """Create test fixtures for H3 tests."""
    pass


@pytest.mark.django_db
def test_h3_anonymous_bypass(setup_db, subtests):
    """Run all H3 security test cases."""
    run_tests(TEST_CASES, state, subtests)
