"""
Django-Flex Middleware

Optional middleware for handling flexible queries through a
centralized endpoint. Supports both unversioned and versioned APIs.

Features:
- Single or multiple endpoints for flex queries
- Automatic model routing
- API versioning with per-version settings
- Request/response logging (optional)
"""

import json
import logging

from django.http import JsonResponse

from django_flex.query import FlexQuery, get_model_by_name
from django_flex.response import FlexResponse
from django_flex.conf import flex_settings


logger = logging.getLogger("django_flex")


class FlexQueryMiddleware:
    """
    Middleware for handling flexible queries through single or multiple endpoints.

    Supports both unversioned (/api/) and versioned (/api/v1/, /api/v2/) APIs
    running simultaneously with different settings per version.

    Setup:
        # settings.py
        MIDDLEWARE = [
            ...
            'django_flex.middleware.FlexQueryMiddleware',
        ]

        # Unversioned only
        DJANGO_FLEX = {
            'MIDDLEWARE_PATH': '/api/',
            'PERMISSIONS': {...},
        }

        # OR: Unversioned + versioned running together
        DJANGO_FLEX = {
            'MIDDLEWARE_PATH': '/api/',  # Unversioned uses top-level settings
            'PERMISSIONS': {...},
            'MAX_LIMIT': 200,

            'VERSIONS': {
                'v1': {
                    'path': '/api/v1/',
                    'PERMISSIONS': {...},  # v1-specific
                    'MAX_LIMIT': 100,
                },
                'v2': {
                    'path': '/api/v2/',
                    'PERMISSIONS': {...},  # v2-specific
                    'MAX_LIMIT': 200,
                },
            },
        }

    Usage:
        # Client sends POST to /api/ (unversioned)
        # OR /api/v1/, /api/v2/ (versioned)
        {
            "_model": "booking",
            "_action": "list",
            "fields": "id, customer.name",
            "filters": {"status": "confirmed"},
            "limit": 20
        }
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.main_path = getattr(flex_settings, "MIDDLEWARE_PATH", "/api/")
        self.versions = getattr(flex_settings, "VERSIONS", {})

        # Build path -> version_config mapping for fast lookup
        self.path_map = {}

        # Add main (unversioned) path - uses top-level settings
        if self.main_path:
            self.path_map[self.main_path] = None  # None = use top-level settings

        # Add versioned paths
        for version_name, version_config in self.versions.items():
            path = version_config.get("path")
            if path:
                self.path_map[path] = version_config

    def __call__(self, request):
        # Check for exact path match first (legacy JSON body approach)
        if request.method == "POST" and request.path in self.path_map:
            version_config = self.path_map[request.path]
            return self.handle_flex_query(request, version_config)

        # Check for RESTful URL pattern: /api/{model} or /api/{model}/{id}
        restful_match = self._parse_restful_url(request.path)
        if restful_match:
            version_config, model_name, id_value = restful_match
            return self.handle_restful_request(request, version_config, model_name, id_value)

        return self.get_response(request)

    def _parse_restful_url(self, path):
        """
        Parse RESTful URL patterns like /api/bookings or /api/bookings/1

        Returns:
            tuple(version_config, model_name, id_value) or None if not matched
        """
        # Check each configured path prefix
        for prefix, version_config in self.path_map.items():
            if path.startswith(prefix) and len(path) > len(prefix):
                remainder = path[len(prefix) :]
                parts = remainder.strip("/").split("/")

                if len(parts) >= 1 and parts[0]:
                    model_name = parts[0]
                    id_value = parts[1] if len(parts) > 1 else None
                    return (version_config, model_name, id_value)

        return None

    def handle_restful_request(self, request, version_config, model_name, id_value):
        """Handle RESTful URL requests with HTTP method mapping."""
        # Map HTTP methods to flex actions
        method_action_map = {
            "GET": "get" if id_value else "list",
            "POST": "add",
            "PUT": "edit",
            "PATCH": "edit",
            "DELETE": "delete",
        }

        action = method_action_map.get(request.method)
        if not action:
            return FlexResponse.error("INVALID_ACTION", f"HTTP method {request.method} not supported").to_json_response()

        # Parse JSON body if present
        body = {}
        if request.body:
            try:
                body = json.loads(request.body)
            except json.JSONDecodeError:
                # Only allow truly empty bodies to pass (for GET/DELETE)
                # Non-empty invalid JSON should return an error
                if request.body.strip():
                    return FlexResponse.error("INVALID_JSON", "Invalid JSON body").to_json_response()

        # Parse query params (override body params)
        query_params = self._parse_query_params(request)
        body.update(query_params)

        # Inject model, action, and id from URL
        body["_model"] = model_name
        body["_action"] = action
        if id_value:
            body["id"] = id_value

        # Use the existing handler
        return self._handle_flex_query_internal(request, version_config, body)

    def _parse_query_params(self, request):
        """
        Parse query parameters into flex query format.

        Supports:
        - fields: comma-separated field list
        - limit: integer
        - offset: integer
        - order_by: field name with optional - prefix
        - filters.{key}: filter params with filters. prefix (shallow nesting)

        Example:
            ?fields=id,name&limit=10&filters.status=pending&filters.customer.name.icontains=khan

        Becomes:
            {fields: 'id,name', limit: 10, filters: {status: 'pending', 'customer.name.icontains': 'khan'}}

        Returns:
            Dict that can be merged with body via body.update(result)
        """
        result = {}
        filters = {}

        for key, value in request.GET.items():
            if key == "fields":
                result["fields"] = value
            elif key == "limit":
                try:
                    result["limit"] = int(value)
                except ValueError:
                    pass
            elif key == "offset":
                try:
                    result["offset"] = int(value)
                except ValueError:
                    pass
            elif key == "order_by":
                result["order_by"] = value
            elif key.startswith("filters."):
                # Extract filter key after "filters." prefix
                # Keep the rest as a dotted string key
                filter_key = key[8:]  # len("filters.") = 8
                if filter_key:
                    filters[filter_key] = value

        if filters:
            result["filters"] = filters

        return result

    def _get_setting(self, name, version_config):
        """
        Get a setting value, checking version config first, then top-level.

        Args:
            name: Setting name (e.g., 'PERMISSIONS', 'MAX_LIMIT')
            version_config: Version-specific config dict or None for unversioned

        Returns:
            Setting value from version config, or top-level, or default
        """
        # Check version-specific config first
        if version_config and name in version_config:
            return version_config[name]

        # Fall back to top-level settings
        return getattr(flex_settings, name)

    def handle_flex_query(self, request, version_config=None):
        """Handle a flex query request with optional version-specific settings."""
        # Parse request body first (needed for __token resolution)
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return FlexResponse.error("INVALID_FILTER", "Invalid JSON body").to_json_response()

        # Resolve user from Authorization header (Bearer token) or __token in body
        self._resolve_user_from_token(request, body)

        # Check authentication if required (after token resolution)
        require_auth = self._get_setting("REQUIRE_AUTHENTICATION", version_config)
        if require_auth:
            if not hasattr(request, "user") or not request.user.is_authenticated:
                return FlexResponse.error("PERMISSION_DENIED", "Authentication required").to_json_response()

        return self._handle_flex_query_internal(request, version_config, body)

    def _handle_flex_query_internal(self, request, version_config, body):
        """Internal handler for flex queries - shared by both JSON body and RESTful approaches."""
        # Note: _resolve_user_from_token is called in handle_flex_query
        # For RESTful requests, we need to resolve it here
        if not hasattr(request, "user") or request.user is None or request.user.is_anonymous:
            self._resolve_user_from_token(request, body)

        # Check authentication if required
        require_auth = self._get_setting("REQUIRE_AUTHENTICATION", version_config)
        if require_auth:
            if not hasattr(request, "user") or not request.user.is_authenticated:
                return FlexResponse.error("PERMISSION_DENIED", "Authentication required").to_json_response()

        # Extract model and action
        model_name = body.get("_model")
        action = body.get("_action", "list")

        if not model_name:
            return FlexResponse.error("MODEL_NOT_FOUND", "Missing '_model' in request").to_json_response()

        # Get model
        model = get_model_by_name(model_name)
        if model is None:
            return FlexResponse.error("MODEL_NOT_FOUND", f"Model '{model_name}' not found").to_json_response()

        # Build query spec (remove internal keys)
        query_spec = {k: v for k, v in body.items() if not k.startswith("_")}

        # Add id if present in body
        if "id" in body:
            query_spec["id"] = body["id"]

        # Log query if auditing enabled
        audit_queries = self._get_setting("AUDIT_QUERIES", version_config)
        if audit_queries:
            user = getattr(request, "user", None)
            version_name = None
            if version_config:
                # Find version name from path
                for name, cfg in self.versions.items():
                    if cfg is version_config:
                        version_name = name
                        break
            logger.info(
                "flex_query",
                extra={
                    "user": str(user) if user else "anonymous",
                    "model": model_name,
                    "action": action,
                    "query": query_spec,
                    "version": version_name,
                },
            )

        # Execute query with version-specific permissions
        user = request.user if hasattr(request, "user") else None
        permissions = self._get_setting("PERMISSIONS", version_config)

        query = FlexQuery(model)
        query.set_permissions(permissions)
        result = query.execute(query_spec, user=user, action=action)

        # Return response using to_json_response() which respects ALWAYS_HTTP_200 setting
        return result.to_json_response()

    def _resolve_user_from_token(self, request, body=None):
        """Resolve user from Authorization Bearer token or __token in request body."""
        # H1 fix: Check if token auth is configured
        session_model_path = flex_settings.SESSION_MODEL
        if not session_model_path:
            return  # Token auth disabled if not configured

        token = self._extract_token(request, body)
        if not token:
            return

        try:
            from django.apps import apps
            from django.core.exceptions import ObjectDoesNotExist

            # Parse 'myapp.models.Session' -> app_label='myapp', model_name='Session'
            parts = session_model_path.rsplit(".", 1)
            if len(parts) != 2:
                logger.error(f"Invalid SESSION_MODEL format: {session_model_path}")
                return

            module_path, model_name = parts[0], parts[1]
            # Handle 'myapp.models.Session' format
            if ".models." in module_path or module_path.endswith(".models"):
                app_label = module_path.split(".")[0]
            else:
                app_label = module_path

            SessionModel = apps.get_model(app_label, model_name)

            token_field = flex_settings.SESSION_TOKEN_FIELD
            user_field = flex_settings.SESSION_USER_FIELD

            session = SessionModel.objects.select_related(user_field).get(**{token_field: token})
            request.user = getattr(session, user_field)

        except LookupError as e:
            logger.error(f"SESSION_MODEL not found: {e}")
        except ObjectDoesNotExist:
            pass  # Invalid token - expected case
        except Exception as e:
            logger.warning(f"Token auth error: {type(e).__name__}: {e}")

    def _extract_token(self, request, body=None):
        """Extract token from Authorization header or request body."""
        token = None

        # First check Authorization header
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Remove "Bearer " prefix

        # Fallback to __token in request body
        if not token and body and "__token" in body:
            token = body["__token"]

        return token
