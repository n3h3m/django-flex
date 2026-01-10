"""
Django-Flex Decorators

Provides function decorators for adding flexible query capabilities
to Django views.

Features:
- flex_query decorator for function-based views
- Automatic queryset filtering and field selection
- Permission integration
"""

from functools import wraps
import json

from django.http import JsonResponse

from django_flex.query import FlexQuery
from django_flex.response import FlexResponse


def flex_query(
    model,
    allowed_fields=None,
    allowed_filters=None,
    allowed_ordering=None,
    require_auth=True,
    allowed_actions=None,
):
    """
    Decorator for adding flexible query capabilities to a view.

    The decorated function receives additional arguments:
    - queryset: Pre-filtered queryset based on permissions
    - fields: Validated list of field paths
    - query_spec: The parsed query specification

    Args:
        model: Django model class
        allowed_fields: List of allowed field patterns (default: ["*"])
        allowed_filters: List of allowed filter keys (default: [])
        allowed_ordering: List of allowed order_by values (default: [])
        require_auth: Whether authentication is required (default: True)
        allowed_actions: List of allowed actions (default: ["get", "list"])

    Example:
        from django_flex import flex_query
        from myapp.models import Booking

        @flex_query(
            model=Booking,
            allowed_fields=['id', 'status', 'customer.name'],
            allowed_filters=['status', 'status.in', 'customer.name.icontains'],
            allowed_ordering=['created_at', '-created_at'],
        )
        def booking_list(request, queryset, fields, query_spec):
            # queryset is pre-filtered
            # fields is the validated list of fields
            # Use FlexResponse to build response
            from django_flex import FlexResponse, build_nested_response

            results = {}
            for obj in queryset:
                results[str(obj.pk)] = build_nested_response(obj, fields)

            return JsonResponse(FlexResponse.ok_query(results=results).to_dict())
    """
    allowed_fields = allowed_fields or ["*"]
    allowed_filters = allowed_filters or []
    allowed_ordering = allowed_ordering or []
    allowed_actions = allowed_actions or ["get", "list"]

    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            # Check authentication
            if require_auth:
                if not hasattr(request, "user") or not request.user.is_authenticated:
                    return FlexResponse.error("PERMISSION_DENIED", "Authentication required").to_json_response()

            # Parse query spec
            if request.method == "POST":
                try:
                    query_spec = json.loads(request.body)
                except json.JSONDecodeError:
                    return FlexResponse.error("INVALID_FILTER", "Invalid JSON body").to_json_response()
            else:
                query_spec = _parse_query_params(request)

            # Determine action
            action = "get" if "id" in query_spec else "list"
            if action not in allowed_actions:
                return FlexResponse.error("PERMISSION_DENIED", f"Action '{action}' not allowed").to_json_response()

            # Build permissions for this view
            user = request.user if hasattr(request, "user") else None
            role = _get_user_role(user)

            permissions = {
                model.__name__.lower(): {
                    role: {
                        "rows": lambda u: __import__("django.db.models", fromlist=["Q"]).Q(),
                        "fields": allowed_fields,
                        "filters": allowed_filters,
                        "order_by": allowed_ordering,
                        "ops": allowed_actions,
                    },
                    "exclude": [],
                }
            }

            # Execute query
            query = FlexQuery(model)
            query.set_permissions(permissions)
            result = query.execute(query_spec, user=user, action=action)

            if not result.success:
                return result.to_json_response()

            # If successful, we can also pass the raw queryset and fields to the view
            # for custom processing (optional pattern)
            return view_func(request, result=result, query_spec=query_spec, *args, **kwargs)

        return wrapped_view

    return decorator


def _parse_query_params(request):
    """Parse query specification from GET parameters."""
    spec = {}
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
    return spec


def _get_user_role(user):
    """Get role using Django's built-in auth system."""
    if user is None or not user.is_authenticated:
        return "anonymous"
    if user.is_superuser:
        return "superuser"
    if user.is_staff:
        return "staff"
    # Use Django groups
    if hasattr(user, "groups"):
        group = user.groups.first()
        if group:
            return group.name.lower()
    return "authenticated"
