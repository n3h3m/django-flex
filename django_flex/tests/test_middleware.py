"""
Tests for django_flex middleware __token authentication.

Tests the ability to authenticate via __token in request body
as an alternative to Authorization Bearer header.
"""

import json
from unittest.mock import MagicMock, patch

import pytest


class TestResolveUserFromToken:
    """Tests for _resolve_user_from_token middleware method."""

    def test_token_from_authorization_header(self):
        """Authorization: Bearer header should authenticate user."""
        from django_flex.middleware import FlexQueryMiddleware

        middleware = FlexQueryMiddleware(lambda r: r)
        request = MagicMock()
        request.headers = {"Authorization": "Bearer test_token_123"}

        with patch("app.models.Session") as mock_session:
            mock_user = MagicMock()
            mock_user.email = "test@example.com"
            mock_session_obj = MagicMock()
            mock_session_obj.user = mock_user
            mock_session.objects.select_related.return_value.get.return_value = mock_session_obj

            middleware._resolve_user_from_token(request, {})

            assert request.user == mock_user
            mock_session.objects.select_related.assert_called_with("user")

    def test_token_from_request_body(self):
        """__token in request body should authenticate user."""
        from django_flex.middleware import FlexQueryMiddleware

        middleware = FlexQueryMiddleware(lambda r: r)
        request = MagicMock()
        request.headers = {}

        body = {"__token": "body_token_456", "_model": "user", "_action": "get"}

        with patch("app.models.Session") as mock_session:
            mock_user = MagicMock()
            mock_user.email = "body@example.com"
            mock_session_obj = MagicMock()
            mock_session_obj.user = mock_user
            mock_session.objects.select_related.return_value.get.return_value = mock_session_obj

            middleware._resolve_user_from_token(request, body)

            assert request.user == mock_user

    def test_header_takes_precedence_over_body(self):
        """Authorization header should be used before __token in body."""
        from django_flex.middleware import FlexQueryMiddleware

        middleware = FlexQueryMiddleware(lambda r: r)
        request = MagicMock()
        request.headers = {"Authorization": "Bearer header_token"}

        body = {"__token": "body_token", "_model": "user"}

        with patch("app.models.Session") as mock_session:
            mock_user = MagicMock()
            mock_session_obj = MagicMock()
            mock_session_obj.user = mock_user
            mock_session.objects.select_related.return_value.get.return_value = mock_session_obj

            middleware._resolve_user_from_token(request, body)

            # Verify token used was from header, not body
            mock_session.objects.select_related.return_value.get.assert_called_with(token="header_token")

    def test_invalid_token_leaves_user_unchanged(self):
        """Invalid token should not modify request.user."""
        from django_flex.middleware import FlexQueryMiddleware

        middleware = FlexQueryMiddleware(lambda r: r)
        request = MagicMock()
        request.headers = {}
        original_user = MagicMock()
        request.user = original_user

        body = {"__token": "invalid_token"}

        with patch("app.models.Session") as mock_session:
            mock_session.objects.select_related.return_value.get.side_effect = Exception("Not found")

            middleware._resolve_user_from_token(request, body)

            # User should remain unchanged
            assert request.user == original_user

    def test_no_token_leaves_user_unchanged(self):
        """Request without token should not modify request.user."""
        from django_flex.middleware import FlexQueryMiddleware

        middleware = FlexQueryMiddleware(lambda r: r)
        request = MagicMock()
        request.headers = {}
        original_user = MagicMock()
        request.user = original_user

        body = {"_model": "user", "_action": "get"}

        middleware._resolve_user_from_token(request, body)

        # User should remain unchanged
        assert request.user == original_user

    def test_empty_body_handled_gracefully(self):
        """None body should be handled without error."""
        from django_flex.middleware import FlexQueryMiddleware

        middleware = FlexQueryMiddleware(lambda r: r)
        request = MagicMock()
        request.headers = {}

        # Should not raise
        middleware._resolve_user_from_token(request, None)


class TestHandleFlexQueryTokenFlow:
    """Tests for full handle_flex_query flow with __token."""

    def test_body_parsed_before_auth_check(self):
        """Body should be parsed and __token resolved before REQUIRE_AUTHENTICATION check."""
        from django_flex.middleware import FlexQueryMiddleware

        middleware = FlexQueryMiddleware(lambda r: r)
        request = MagicMock()
        request.method = "POST"
        request.path = "/flex/"
        request.headers = {}
        request.body = json.dumps(
            {
                "_model": "user",
                "_action": "get",
                "__token": "valid_token",
                "id": 1,
            }
        ).encode()

        with patch.object(middleware, "_get_setting") as mock_setting:
            mock_setting.return_value = True  # REQUIRE_AUTHENTICATION = True

            with patch.object(middleware, "_resolve_user_from_token") as mock_resolve:
                mock_user = MagicMock()
                mock_user.is_authenticated = True

                def set_user(req, body):
                    req.user = mock_user

                mock_resolve.side_effect = set_user

                with patch.object(middleware, "_handle_flex_query_internal") as mock_internal:
                    mock_internal.return_value = MagicMock()

                    middleware.handle_flex_query(request)

                    # _resolve_user_from_token should be called with parsed body
                    mock_resolve.assert_called_once()
                    call_args = mock_resolve.call_args
                    assert "__token" in call_args[0][1]


class TestAlwaysHttp200AuthErrors:
    """Tests that auth errors respect ALWAYS_HTTP_200 setting."""

    def test_auth_error_returns_200_with_success_false(self, settings):
        """When ALWAYS_HTTP_200=True, auth errors should return HTTP 200 with success:false."""
        settings.DJANGO_FLEX = {"ALWAYS_HTTP_200": True, "REQUIRE_AUTHENTICATION": True}

        from django_flex.middleware import FlexQueryMiddleware
        from django_flex.conf import flex_settings

        # Reload settings
        flex_settings.reload()

        middleware = FlexQueryMiddleware(lambda r: r)
        request = MagicMock()
        request.method = "POST"
        request.path = "/flex/"
        request.headers = {}
        request.body = json.dumps(
            {
                "_model": "user",
                "_action": "get",
                "__token": "invalid_token_that_wont_work",
                "id": 1,
            }
        ).encode()

        # Mock the session lookup to fail (invalid token)
        with patch("app.models.Session") as mock_session:
            mock_session.objects.select_related.return_value.get.side_effect = Exception("Not found")

            response = middleware.handle_flex_query(request)

            # Should be HTTP 200
            assert response.status_code == 200

            # Response body should have success:false
            data = json.loads(response.content)
            assert data["success"] is False
            assert data["status_code"] == 403
            assert "error" in data

    def test_auth_error_returns_401_when_always_http_200_disabled(self, settings):
        """When ALWAYS_HTTP_200=False, auth errors should return HTTP 401."""
        settings.DJANGO_FLEX = {"ALWAYS_HTTP_200": False, "REQUIRE_AUTHENTICATION": True}

        from django_flex.middleware import FlexQueryMiddleware
        from django_flex.conf import flex_settings

        # Reload settings
        flex_settings.reload()

        middleware = FlexQueryMiddleware(lambda r: r)
        request = MagicMock()
        request.method = "POST"
        request.path = "/flex/"
        request.headers = {}
        request.body = json.dumps(
            {
                "_model": "user",
                "_action": "get",
                "__token": "invalid_token",
                "id": 1,
            }
        ).encode()

        with patch("app.models.Session") as mock_session:
            mock_session.objects.select_related.return_value.get.side_effect = Exception("Not found")

            response = middleware.handle_flex_query(request)

            # Should be HTTP 403 when ALWAYS_HTTP_200=False
            assert response.status_code == 403
