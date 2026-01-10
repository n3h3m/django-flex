"""
Django-Flex Core Query Engine

The main query execution engine that ties together field parsing,
filter building, and permission checking.

Provides:
- FlexQuery class for OOP-style queries
- execute_query function for procedural usage
"""

from django.apps import apps

from django_flex.conf import flex_settings
from django_flex.fields import parse_fields, expand_fields, extract_relations, get_json_fields, get_fk_fields, resolve_fk_values
from django_flex.filters import build_q_object, extract_filter_keys
from django_flex.permissions import (
    check_permission,
    check_filter_permission,
    check_order_permission,
)
from django_flex.response import FlexResponse, build_nested_response


def get_model_by_name(model_name):
    """
    Get Django model class by name (case-insensitive).

    Searches all installed apps for a matching model.

    Args:
        model_name: Model name to find (case-insensitive, singular)

    Returns:
        Model class or None if not found
    """
    for app_config in apps.get_app_configs():
        for model in app_config.get_models():
            if model.__name__.lower() == model_name.lower():
                return model
    return None


class FlexQuery:
    """
    Flexible query builder for Django models.

    Provides a fluent interface for building and executing queries
    with field selection, filtering, and pagination.

    Example:
        # Direct usage
        result = FlexQuery(Booking).execute({
            'fields': 'id, customer.name, status',
            'filters': {'status': 'confirmed'},
            'limit': 20,
        }, user=request.user)

        # With model name
        result = FlexQuery('booking').execute({...}, user=request.user)

        # Chained configuration
        query = FlexQuery(Booking)
        query.set_user(request.user)
        query.set_permissions(custom_permissions)
        result = query.execute({...})
    """

    def __init__(self, model):
        """
        Initialize a FlexQuery.

        Args:
            model: Django model class or model name string
        """
        if isinstance(model, str):
            self.model_name = model.lower()
            self.model = get_model_by_name(model)
        else:
            self.model = model
            self.model_name = model.__name__.lower()

        self.user = None
        self.permissions = None

    def set_user(self, user):
        """Set the user for permission checking."""
        self.user = user
        return self

    def set_permissions(self, permissions):
        """Set custom permissions configuration."""
        self.permissions = permissions
        return self

    def execute(self, query_spec, user=None, action=None):
        """
        Execute a query with the given specification.

        Args:
            query_spec: Dict with query parameters (fields, filters, etc.)
            user: Optional user (overrides set_user)
            action: Optional action override (defaults to 'get' for id, 'list' for no id)

        Returns:
            FlexResponse with query results
        """
        user = user or self.user
        permissions = self.permissions

        if self.model is None:
            return FlexResponse.error("MODEL_NOT_FOUND")

        # Determine action
        if action:
            pass
        elif "id" in query_spec:
            action = "get"
        else:
            action = "list"

        # Route to appropriate handler
        if action == "get":
            return self._execute_get(query_spec, user, permissions)
        elif action == "list":
            return self._execute_list(query_spec, user, permissions)
        elif action == "edit":
            return self._execute_edit(query_spec, user, permissions)
        elif action == "add":
            return self._execute_add(query_spec, user, permissions)
        elif action == "delete":
            return self._execute_delete(query_spec, user, permissions)
        else:
            return FlexResponse.error("INVALID_ACTION", f"Unknown action: {action}")

    def _execute_get(self, query_spec, user, permissions):
        """Execute single object retrieval."""
        # Parse fields
        field_specs = parse_fields(query_spec.get("fields", "*"))
        expanded_fields = expand_fields(self.model, field_specs, permissions=permissions)

        # Check permissions
        try:
            if user:
                row_filter, validated_fields = check_permission(user, self.model_name, "get", expanded_fields, permissions)
            else:
                row_filter = None
                validated_fields = expanded_fields
        except PermissionError as e:
            return FlexResponse.error("PERMISSION_DENIED", str(e))

        # Extract relations for select_related (avoid N+1)
        relations = extract_relations(validated_fields)

        # Build queryset
        try:
            queryset = self.model.objects.all()
            if row_filter:
                queryset = queryset.filter(row_filter)
            if relations:
                queryset = queryset.select_related(*relations)
            obj = queryset.get(pk=query_spec["id"])
        except self.model.DoesNotExist:
            return FlexResponse.error("NOT_FOUND")

        # Build response
        json_fields = set(get_json_fields(self.model))
        fk_fields = get_fk_fields(self.model)
        response_data = build_nested_response(obj, validated_fields, json_fields, fk_fields)
        return FlexResponse.ok(**response_data)

    def _execute_list(self, query_spec, user, permissions):
        """Execute paginated query retrieval."""
        # Parse fields
        field_specs = parse_fields(query_spec.get("fields", "*"))
        expanded_fields = expand_fields(self.model, field_specs, permissions=permissions)

        # Check permissions
        try:
            if user:
                row_filter, validated_fields = check_permission(user, self.model_name, "list", expanded_fields, permissions)
            else:
                row_filter = None
                validated_fields = expanded_fields
        except PermissionError as e:
            return FlexResponse.error("PERMISSION_DENIED", str(e))

        # Validate filter keys
        filters = query_spec.get("filters", {})
        try:
            if user:
                filter_keys = extract_filter_keys(filters)
                check_filter_permission(user, self.model_name, filter_keys, permissions)
        except PermissionError as e:
            return FlexResponse.error("PERMISSION_DENIED", str(e))

        # Validate order_by
        order_by = query_spec.get("order_by")
        try:
            if user:
                check_order_permission(user, self.model_name, order_by, permissions)
        except PermissionError as e:
            return FlexResponse.error("PERMISSION_DENIED", str(e))

        # Extract relations for select_related
        relations = extract_relations(validated_fields)

        # Build query
        user_filter = build_q_object(filters)
        queryset = self.model.objects.all()
        if row_filter:
            queryset = queryset.filter(row_filter & user_filter)
        else:
            queryset = queryset.filter(user_filter)

        # Apply select_related
        if relations:
            queryset = queryset.select_related(*relations)

        # Ordering
        if order_by:
            order_by_django = order_by.replace(".", "__")
            queryset = queryset.order_by(order_by_django)

        # Pagination with limit clamping
        requested_limit = query_spec.get("limit", flex_settings.DEFAULT_LIMIT)
        max_limit = flex_settings.MAX_LIMIT
        limit = min(requested_limit, max_limit)
        limit_clamped = requested_limit > max_limit
        offset = query_spec.get("offset", 0)

        # Fetch limit + 1 to check for more results (avoids expensive COUNT query)
        paginated = list(queryset[offset : offset + limit + 1])

        # Determine if there are more results
        has_more = len(paginated) > limit
        if has_more:
            paginated = paginated[:limit]  # Drop the extra row

        # Build results dict keyed by id
        json_fields = set(get_json_fields(self.model))
        fk_fields = get_fk_fields(self.model)
        results = {}
        for obj in paginated:
            obj_data = build_nested_response(obj, validated_fields, json_fields, fk_fields)
            results[str(obj.pk)] = obj_data

        # Build pagination info
        pagination = {
            "offset": offset,
            "limit": limit,
            "has_more": has_more,
        }

        # Build next cursor if more results exist
        if has_more:
            pagination["next"] = {
                "fields": query_spec.get("fields", "*"),
                "filters": filters,
                "limit": limit,
                "offset": offset + limit,
            }
            if order_by:
                pagination["next"]["order_by"] = order_by

        # Return warning if limit was clamped
        if limit_clamped:
            return FlexResponse.warning_response(
                "LIMIT_CLAMPED",
                results=results,
                pagination=pagination,
                requested_limit=requested_limit,
            )

        return FlexResponse.ok_query(results=results, pagination=pagination)

    def _check_action_permission(self, user, action, permissions):
        """Check permission for an action and return row_filter. Raises PermissionError on failure."""
        if user:
            row_filter, _ = check_permission(user, self.model_name, action, [], permissions)
            return row_filter
        return None

    def _get_object_by_id(self, query_spec, row_filter):
        """Retrieve single object by id with optional row_filter. Returns (obj, error_response)."""
        if "id" not in query_spec:
            return None, FlexResponse.error("INVALID_REQUEST", f"Action requires 'id'")

        try:
            queryset = self.model.objects.all()
            if row_filter:
                queryset = queryset.filter(row_filter)
            return queryset.get(pk=query_spec["id"]), None
        except self.model.DoesNotExist:
            return None, FlexResponse.error("NOT_FOUND")

    def _get_allowed_fields(self, user, permissions):
        """Get list of allowed fields for user's role."""
        from django_flex.permissions import get_user_role, normalize_role_config

        if permissions and user:
            model_perms = permissions.get(self.model_name, {})
            role_result = get_user_role(user, self.model_name, permissions)
            role = role_result[0] if isinstance(role_result, tuple) else role_result
            perm = normalize_role_config(model_perms.get(role, {}))
            return perm.get("fields", [])
        return ["*"]

    def _execute_edit(self, query_spec, user, permissions):
        """Execute single object update."""
        try:
            row_filter = self._check_action_permission(user, "edit", permissions)
        except PermissionError as e:
            return FlexResponse.error("PERMISSION_DENIED", str(e))

        obj, error = self._get_object_by_id(query_spec, row_filter)
        if error:
            return error

        allowed_fields = self._get_allowed_fields(user, permissions)
        update_fields = {k: v for k, v in query_spec.items() if not k.startswith("_") and k != "id"}
        update_fields = resolve_fk_values(self.model, update_fields)

        for field_name, value in update_fields.items():
            # Handle _id suffix from FK resolution - check permission against base name
            base_field = field_name[:-3] if field_name.endswith("_id") else field_name
            if allowed_fields != ["*"] and "*" not in allowed_fields:
                if base_field not in allowed_fields and field_name not in allowed_fields:
                    return FlexResponse.error("PERMISSION_DENIED", f"Field '{base_field}' not editable")
            if hasattr(obj, field_name):
                setattr(obj, field_name, value)
            else:
                return FlexResponse.error("INVALID_FIELD", f"Field '{field_name}' does not exist on {self.model_name}")

        try:
            obj.save()
        except Exception as e:
            return FlexResponse.error("SAVE_FAILED", str(e))

        return FlexResponse.ok(id=obj.pk, updated=True)

    def _execute_add(self, query_spec, user, permissions):
        """Execute object creation."""
        from django.conf import settings

        try:
            self._check_action_permission(user, "add", permissions)
        except PermissionError as e:
            return FlexResponse.error("PERMISSION_DENIED", str(e))

        create_fields = {k: v for k, v in query_spec.items() if not k.startswith("_")}
        create_fields = resolve_fk_values(self.model, create_fields)

        try:
            obj = self.model.objects.create(**create_fields)
        except Exception as e:
            return FlexResponse.error("CREATE_FAILED", str(e))

        response_data = {"id": obj.pk}

        # In DEBUG mode, include full created object under model name
        if settings.DEBUG:
            json_fields = set(get_json_fields(self.model))
            fk_fields = get_fk_fields(self.model)
            # Get all field names for the model
            all_fields = [f.name for f in self.model._meta.get_fields() if hasattr(f, "column") or hasattr(f, "attname")]
            obj_data = build_nested_response(obj, all_fields, json_fields, fk_fields)
            response_data[self.model_name.lower()] = obj_data

        return FlexResponse(code="CREATED", **response_data)

    def _execute_delete(self, query_spec, user, permissions):
        """Execute object deletion."""
        try:
            row_filter = self._check_action_permission(user, "delete", permissions)
        except PermissionError as e:
            return FlexResponse.error("PERMISSION_DENIED", str(e))

        obj, error = self._get_object_by_id(query_spec, row_filter)
        if error:
            return error

        obj_id = obj.pk
        obj.delete()

        return FlexResponse.ok(id=obj_id, deleted=True)


def execute_query(model, query_spec, user=None, permissions=None):
    """
    Execute a flexible query on a model.

    Convenience function that wraps FlexQuery.

    Args:
        model: Django model class or model name string
        query_spec: Dict with query parameters
        user: Optional user for permission checking
        permissions: Optional custom permissions

    Returns:
        FlexResponse with query results

    Example:
        result = execute_query(Booking, {
            'fields': 'id, customer.name',
            'filters': {'status': 'confirmed'},
            'limit': 20,
        }, user=request.user)
    """
    query = FlexQuery(model)
    if permissions:
        query.set_permissions(permissions)
    return query.execute(query_spec, user=user)
