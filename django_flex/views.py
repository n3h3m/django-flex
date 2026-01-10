"""
Django-Flex Views

Provides Django class-based views for handling flexible queries.

Features:
- FlexQueryView for easy integration
- Automatic permission handling
- Configurable per-view settings
"""

from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

import json

from django_flex.query import FlexQuery
from django_flex.response import FlexResponse
from django_flex.conf import flex_settings


class FlexQueryView(View):
    """
    Generic view for handling flexible queries.

    Subclass this view and configure the model and permissions
    to create an endpoint for flexible queries.

    CSRF Protection:
        By default, CSRF protection is ENABLED (secure by default).
        To disable for token-only APIs, set CSRF_EXEMPT=True in settings.

    Example:
        # views.py
        from django_flex.views import FlexQueryView
        from myapp.models import Booking

        class BookingQueryView(FlexQueryView):
            model = Booking

            # Optional: custom permissions
            flex_permissions = {
                'owner': {
                    'rows': lambda user: Q(company__owner=user),
                    'fields': ['*', 'customer.*'],
                    'filters': ['status', 'status.in', 'customer.name.icontains'],
                    'order_by': ['created_at', '-created_at'],
                    'ops': ['get', 'list'],
                },
            }

        # urls.py
        from django.urls import path
        from myapp.views import BookingQueryView

        urlpatterns = [
            path('api/bookings/', BookingQueryView.as_view(), name='booking-query'),
        ]
    """

    # Required: the model to query
    model = None

    # Optional: custom permissions (uses settings.DJANGO_FLEX.PERMISSIONS if not set)
    flex_permissions = None

    # Optional: require authentication
    require_auth = True

    # Optional: allowed actions
    allowed_actions = ["get", "list"]

    @classmethod
    def as_view(cls, **initkwargs):
        """Override as_view to conditionally apply csrf_exempt based on settings."""
        view = super().as_view(**initkwargs)
        # H2 fix: Only apply csrf_exempt if explicitly configured (secure by default)
        if flex_settings.CSRF_EXEMPT:
            view = csrf_exempt(view)
        return view

    def get_model(self):
        """Get the model to query. Override for dynamic model selection."""
        return self.model

    def get_permissions(self):
        """Get permissions configuration. Override for dynamic permissions."""
        return self.flex_permissions

    def get_user(self, request):
        """Get the user for permission checking. Override for custom auth."""
        return request.user if hasattr(request, "user") else None

    def check_auth(self, request):
        """Check authentication. Override for custom auth logic."""
        if not self.require_auth:
            return True

        user = self.get_user(request)
        return user and user.is_authenticated

    def get_query_spec(self, request):
        """
        Extract query specification from request.

        Override to customize how queries are parsed from requests.
        Supports JSON body for both GET and POST requests.
        Also checks URL kwargs for 'pk' for single-object retrieval.
        """
        spec = {}

        # Try to parse JSON body (works for both GET and POST)
        if request.body:
            try:
                spec = json.loads(request.body)
            except json.JSONDecodeError:
                # Fall back to query params for GET
                if request.method != "GET":
                    return None

        # For GET without JSON body, parse query params
        if request.method == "GET" and not spec:
            if "fields" in request.GET:
                spec["fields"] = request.GET["fields"]
            if "filters" in request.GET:
                try:
                    spec["filters"] = json.loads(request.GET["filters"])
                except json.JSONDecodeError:
                    spec["filters"] = {}
            if "limit" in request.GET:
                try:
                    spec["limit"] = int(request.GET["limit"])
                except ValueError:
                    pass
            if "offset" in request.GET:
                try:
                    spec["offset"] = int(request.GET["offset"])
                except ValueError:
                    pass
            if "order_by" in request.GET:
                spec["order_by"] = request.GET["order_by"]
            if "id" in request.GET:
                try:
                    spec["id"] = int(request.GET["id"])
                except ValueError:
                    spec["id"] = request.GET["id"]

        # Check for pk in URL kwargs (e.g., /api/bookings/1)
        pk = self.kwargs.get("pk")
        if pk is not None:
            spec["id"] = pk

        return spec

    def post(self, request, *args, **kwargs):
        """Handle POST request for queries."""
        return self.handle_query(request)

    def get(self, request, *args, **kwargs):
        """Handle GET request for queries."""
        return self.handle_query(request)

    def handle_query(self, request):
        """
        Main query handler.

        Validates authentication, parses query spec, and executes query.
        """
        # Check authentication
        if not self.check_auth(request):
            return FlexResponse.error("PERMISSION_DENIED", "Authentication required").to_json_response()

        # Get model
        model = self.get_model()
        if model is None:
            return FlexResponse.error("MODEL_NOT_FOUND", "Model not configured").to_json_response()

        # Get query spec
        query_spec = self.get_query_spec(request)
        if query_spec is None:
            return FlexResponse.error("INVALID_FILTER", "Invalid query specification").to_json_response()

        # Determine action
        action = "get" if "id" in query_spec else "list"
        if action not in self.allowed_actions:
            return FlexResponse.error("PERMISSION_DENIED", f"Action '{action}' not allowed").to_json_response()

        # Check rate limit
        user = self.get_user(request)
        permissions = self.get_permissions()
        permissions_dict = self._build_permissions_dict(permissions) if permissions else None

        from django_flex.ratelimit import check_rate_limit

        model_name = model.__name__.lower()
        allowed, retry_after = check_rate_limit(user, model_name, action, permissions_dict, request)

        if not allowed:
            response = JsonResponse(
                {"error": "Rate limit exceeded", "retry_after": retry_after},
                status=429,
            )
            response["Retry-After"] = str(retry_after)
            return response

        # Execute query
        query = FlexQuery(model)
        if permissions_dict:
            query.set_permissions(permissions_dict)

        result = query.execute(query_spec, user=user, action=action)

        return result.to_json_response()

    def _build_permissions_dict(self, flex_permissions):
        """Build a permissions dict compatible with the permission system."""
        model_name = self.get_model().__name__.lower()
        return {model_name: flex_permissions}


class FlexModelView(FlexQueryView):
    """
    Model-specific view with URL-based model selection.

    Allows querying multiple models from a single endpoint based on
    the URL parameter.

    Example:
        # urls.py
        urlpatterns = [
            path('api/<str:model_name>/', FlexModelView.as_view(), name='flex-query'),
        ]

        # Requests:
        # POST /api/booking/ -> query Booking model
        # POST /api/customer/ -> query Customer model
    """

    # List of allowed model names (security measure)
    allowed_models = []

    def get_model(self):
        """Get model from URL."""
        model_name = self.kwargs.get("model_name", "")

        # Security check: only allow configured models
        if self.allowed_models and model_name.lower() not in [m.lower() for m in self.allowed_models]:
            return None

        from django_flex.query import get_model_by_name

        return get_model_by_name(model_name)
