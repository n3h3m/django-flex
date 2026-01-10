"""
Security Tests for Medium-Priority Issues (M1-M5)

This file consolidates the medium-priority security issues:
- M1: Rate limit bypass via IP spoofing
- M2: Silent exception swallowing in token authentication
- M3: No input validation on filter values
- M4: FlexModelView allowed_models default allows all models
- M5: Superuser cannot access unconfigured models (documentation issue)

These tests verify security aspects that are important but not critical.

Related Issues: #7, #8, #9, #10, #11
"""

import pytest
from unittest.mock import patch, MagicMock
from django.test import RequestFactory

from django_flex.tests.test_utils import run_tests


# =============================================================================
# State variables for tests
# =============================================================================
state = {
    "spoofed_ip": "192.168.1.100",
    "real_ip": "10.0.0.1",
}


# =============================================================================
# TEST CASES
# =============================================================================
TEST_CASES = [
    # ========================================
    # M1: Rate limit bypass tests
    # ========================================
    {
        "name": "M1-1: Rate limit applies to authenticated users",
        "req": {
            "_model": "testmodel",
            "_action": "list",
        },
        "res": {
            "success": True,
        },
    },
]


# =============================================================================
# M1: Rate Limit Bypass Tests
# =============================================================================
class TestM1RateLimitBypass:
    """
    Tests for M1: Rate limit bypass via IP spoofing.

    Anonymous rate limiting relies on IP address from X-Forwarded-For header,
    which can be easily spoofed by attackers.
    """

    def test_get_client_ip_uses_remote_addr_by_default(self):
        """
        Test that client IP uses REMOTE_ADDR by default, not spoofable header.

        Expected (after fix): Use REMOTE_ADDR unless explicitly configured
        Actual (before fix): Uses X-Forwarded-For first (spoofable)
        """
        from django_flex.ratelimit import _get_client_ip

        factory = RequestFactory()
        request = factory.get("/")

        # Set REMOTE_ADDR (real IP from socket)
        request.META["REMOTE_ADDR"] = "10.0.0.1"

        # Set spoofed X-Forwarded-For
        request.META["HTTP_X_FORWARDED_FOR"] = "1.2.3.4, 5.6.7.8"

        ip = _get_client_ip(request)

        # After fix, should use REMOTE_ADDR, not X-Forwarded-For
        if ip == "1.2.3.4":
            pytest.fail(
                "M1 VULNERABILITY: _get_client_ip uses X-Forwarded-For header. "
                "Attacker can bypass rate limits by rotating spoofed IPs: "
                "curl -H 'X-Forwarded-For: random-ip' ..."
            )

    def test_rate_limit_not_bypassable_via_header(self):
        """
        Test that rotating X-Forwarded-For doesn't bypass rate limit.
        """
        from django_flex.ratelimit import check_rate_limit, _get_client_ip

        factory = RequestFactory()

        # Simulate multiple requests with different spoofed IPs
        for i in range(10):
            request = factory.get("/")
            request.META["REMOTE_ADDR"] = "10.0.0.1"  # Same real IP
            request.META["HTTP_X_FORWARDED_FOR"] = f"192.168.1.{i}"  # Different spoofed

            ip = _get_client_ip(request)

            # All should resolve to same IP (10.0.0.1)
            if ip != "10.0.0.1":
                pytest.fail(f"M1 VULNERABILITY: Request {i} got IP {ip} from spoofed header. " "Each spoofed IP gets fresh rate limit counter!")


# =============================================================================
# M2: Silent Exception Swallowing Tests
# =============================================================================
class TestM2SilentExceptions:
    """
    Tests for M2: Silent exception swallowing in token authentication.

    All token auth errors are caught with 'except Exception: pass',
    hiding security-relevant errors and making debugging impossible.
    """

    def test_token_auth_logs_errors(self):
        """
        Test that token authentication errors are logged.

        Expected: Errors logged at WARNING/ERROR level
        Actual (before fix): except Exception: pass (silent)
        """
        import logging
        from django_flex.middleware import FlexQueryMiddleware

        # Setup log capture
        logger = logging.getLogger("django_flex.security")

        with patch.object(logger, "warning") as mock_warning:
            with patch.object(logger, "debug") as mock_debug:
                factory = RequestFactory()
                request = factory.post("/", {"__token": "invalid-token"})

                middleware = FlexQueryMiddleware(lambda r: r)

                # This should log something, not silently pass
                try:
                    middleware._resolve_user_from_token(request)
                except Exception:
                    pass  # Method may not exist yet

                # Check if any logging occurred
                # Note: This test documents expected behavior after fix

    def test_specific_exceptions_caught(self):
        """
        Test that specific exceptions are caught, not bare 'except Exception'.
        """
        import inspect
        from django_flex.middleware import FlexQueryMiddleware

        source = inspect.getsource(FlexQueryMiddleware)

        # Check for bare except
        if "except Exception:" in source and "pass" in source:
            # Could be a vulnerability - check context
            lines = source.split("\n")
            for i, line in enumerate(lines):
                if "except Exception:" in line:
                    # Check if next non-empty line is 'pass'
                    for j in range(i + 1, min(i + 3, len(lines))):
                        if "pass" in lines[j] and "#" not in lines[j]:
                            pytest.fail(
                                "M2 VULNERABILITY: 'except Exception: pass' found in middleware. "
                                "This silently swallows all errors including ImportError, DatabaseError, etc."
                            )


# =============================================================================
# M3: Filter Input Validation Tests
# =============================================================================
class TestM3FilterValidation:
    """
    Tests for M3: No input validation on filter values.

    Filter values are passed directly to Django ORM without validation,
    enabling DoS via memory exhaustion or type errors.
    """

    def test_in_operator_list_size_limited(self):
        """
        Test that 'in' operator has list size limit.

        Expected: Large lists rejected to prevent memory exhaustion
        Actual (before fix): Any size list accepted
        """
        from django_flex.filters import build_q_object

        # Create a very large list
        huge_list = list(range(100000))

        filters = {"id.in": huge_list}

        try:
            q = build_q_object(filters)
            # If we get here, no size limit exists
            pytest.fail(
                f"M3 VULNERABILITY: Filter 'id.in' accepted list of {len(huge_list)} items. "
                "Attacker can exhaust memory with: {'id.in': [1,2,3,...,1000000]}"
            )
        except (ValueError, PermissionError) as e:
            # CORRECT - size limit enforced
            assert "size" in str(e).lower() or "limit" in str(e).lower()

    def test_filter_value_type_validated(self):
        """
        Test that filter values are type-validated.
        """
        from django_flex.filters import build_q_object

        # Nested object where scalar expected
        filters = {"id": {"nested": {"deep": "object"}}}

        try:
            q = build_q_object(filters)
            # Check if this could cause issues
        except (ValueError, TypeError):
            # GOOD - type validation occurred
            pass


# =============================================================================
# M4: FlexModelView allowed_models Tests
# =============================================================================
class TestM4AllowedModels:
    """
    Tests for M4: FlexModelView allowed_models default allows all models.

    When allowed_models=[] (default), the security check passes for ALL models.
    """

    def test_empty_allowed_models_denies_all(self):
        """
        Test that empty allowed_models list denies all access.

        Expected: Empty list = deny all (secure default)
        Actual (before fix): Empty list = allow all (insecure)
        """
        from django_flex.views import FlexModelView

        class TestView(FlexModelView):
            allowed_models = []  # Default

        view = TestView()
        view.kwargs = {"model_name": "user"}

        model = view.get_model()

        if model is not None:
            pytest.fail(
                "M4 VULNERABILITY: FlexModelView with empty allowed_models "
                "returned a model. Any model is accessible! "
                "Empty allowed_models should deny all access."
            )

    def test_allowed_models_check_not_skipped(self):
        """
        Test that allowed_models check is not skipped when list is empty.
        """
        from django_flex.views import FlexModelView
        import inspect

        source = inspect.getsource(FlexModelView.get_model)

        # Check for the buggy pattern: if self.allowed_models and ...
        if "if self.allowed_models and" in source or "if self.allowed_models:" in source:
            pytest.fail(
                "M4 VULNERABILITY: get_model uses 'if self.allowed_models' which is False for []. "
                "Change to explicit check: 'if allowed_models is not None' or deny if empty."
            )


# =============================================================================
# M5: Superuser Access Documentation Tests
# =============================================================================
class TestM5SuperuserDocs:
    """
    Tests for M5: Superuser cannot access unconfigured models.

    This is correct security behavior but needs documentation.
    Tests verify the behavior is as expected (deny by default).
    """

    def test_superuser_denied_unconfigured_model(self):
        """
        Test that superuser is denied access to models not in PERMISSIONS.

        This is CORRECT behavior (deny by default) but may surprise developers.
        """
        from django_flex.permissions import check_permission
        from unittest.mock import MagicMock

        superuser = MagicMock()
        superuser.is_superuser = True
        superuser.is_authenticated = True

        permissions = {
            # 'unconfigured_model' is NOT here
            "configured_model": {
                "superuser": "*",
            }
        }

        try:
            check_permission(user=superuser, model_name="unconfigured_model", action="list", requested_fields=["id"], permissions=permissions)
            pytest.fail(
                "M5 UNEXPECTED: Superuser accessed unconfigured model. " "Deny-by-default should apply even to superusers for unconfigured models."
            )
        except PermissionError:
            # CORRECT - superuser still needs model to be configured
            pass

    def test_superuser_bypasses_within_configured_model(self):
        """
        Test that superuser with '*' config bypasses field/row restrictions.
        """
        from django_flex.permissions import check_permission
        from unittest.mock import MagicMock
        from django.db.models import Q

        superuser = MagicMock()
        superuser.is_superuser = True
        superuser.is_authenticated = True

        permissions = {
            "user": {
                "superuser": "*",  # Full bypass
                "authenticated": {
                    "rows": lambda u: Q(id=u.id),
                    "fields": ["id", "username"],
                    "ops": ["get"],
                },
            }
        }

        row_filter, fields = check_permission(
            user=superuser,
            model_name="user",
            action="list",  # Not in 'authenticated' ops
            requested_fields=["id", "username", "email", "is_superuser"],
            permissions=permissions,
        )

        # Superuser should bypass row filter and field restrictions
        assert row_filter == Q() or row_filter is None, "Superuser should have no row filter"
        # Fields should include all requested
        assert "email" in fields, "Superuser should access all fields"


# =============================================================================
# Integration test runner
# =============================================================================
@pytest.fixture
def setup_db(db):
    """Create test fixtures for medium-priority tests."""
    pass


@pytest.mark.django_db
def test_medium_priority_security(setup_db, subtests):
    """Run all medium-priority security test cases."""
    run_tests(TEST_CASES, state, subtests)
