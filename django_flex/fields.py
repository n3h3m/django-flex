"""
Django-Flex Field Utilities

Handles field parsing, expansion, and model introspection for
flexible queries.

Features:
- Parse comma-separated field strings
- Expand wildcards (* and relation.*)
- Model field introspection
- Relation extraction for select_related optimization
"""

from django_flex.conf import flex_settings


def parse_fields(fields_str):
    """
    Parse comma-separated field string into list of field specs.

    Args:
        fields_str: Comma-separated field string (e.g., "name, email")

    Returns:
        List of field specs

    Examples:
        >>> parse_fields("name, email")
        ['name', 'email']
        >>> parse_fields("id, customer.name, customer.email")
        ['id', 'customer.name', 'customer.email']
        >>> parse_fields("*, customer.*")
        ['*', 'customer.*']
        >>> parse_fields("")
        ['*']
        >>> parse_fields(None)
        ['*']
    """
    if not fields_str:
        return ["*"]  # Default to all fields

    return [f.strip() for f in fields_str.split(",") if f.strip()]


def get_model_fields(model):
    """
    Get list of concrete field names for a model.

    Only returns fields with database columns (excludes reverse relations,
    many-to-many through tables, etc.).

    Args:
        model: Django model class

    Returns:
        List of field names

    Example:
        >>> get_model_fields(User)
        ['id', 'email', 'username', 'first_name', 'last_name', ...]
    """
    fields = []
    for field in model._meta.get_fields():
        # Only include concrete fields (not relations or reverse relations)
        if hasattr(field, "column") and field.column:
            fields.append(field.name)
    return fields


def get_json_fields(model):
    """
    Get list of JSONField names for a model.

    Args:
        model: Django model class

    Returns:
        List of JSONField names

    Example:
        >>> get_json_fields(Customer)
        ['metadata']
    """
    from django.db.models import JSONField

    json_fields = []
    for field in model._meta.get_fields():
        if isinstance(field, JSONField):
            json_fields.append(field.name)
    return json_fields


def is_json_field_path(model, field_path):
    """
    Check if field_path starts with a JSONField.

    Args:
        model: Django model class
        field_path: Dot-notation field path (e.g., "metadata.settings.theme")

    Returns:
        Tuple of (is_json, json_field_name, json_key_path)
        - is_json: True if path starts with a JSONField
        - json_field_name: Name of the JSONField (or None)
        - json_key_path: Remaining path after the JSONField (or None)

    Examples:
        >>> is_json_field_path(Customer, "metadata.settings.theme")
        (True, "metadata", "settings.theme")
        >>> is_json_field_path(Customer, "metadata")
        (True, "metadata", None)
        >>> is_json_field_path(Customer, "company.name")
        (False, None, None)
    """
    parts = field_path.split(".")
    json_fields = get_json_fields(model)

    if parts[0] in json_fields:
        json_key_path = ".".join(parts[1:]) if len(parts) > 1 else None
        return (True, parts[0], json_key_path)

    return (False, None, None)


def get_model_relations(model):
    """
    Get dict of relation_name -> related_model for a model.

    Only returns forward relations (ForeignKey, OneToOneField) that
    can be used in select_related.

    Args:
        model: Django model class

    Returns:
        Dict mapping relation name to related model class

    Example:
        >>> get_model_relations(Booking)
        {'customer': <class 'Customer'>, 'address': <class 'Address'>}
    """
    relations = {}
    for field in model._meta.get_fields():
        if hasattr(field, "related_model") and field.related_model:
            # Forward relations (ForeignKey, OneToOneField)
            if hasattr(field, "column"):
                relations[field.name] = field.related_model
    return relations


def get_fk_fields(model):
    """
    Get set of ForeignKey field names for a model.

    Args:
        model: Django model class

    Returns:
        Set of FK field names

    Example:
        >>> get_fk_fields(Service)
        {'company', 'created_by', 'updated_by', 'deleted_by'}
    """
    from django.db.models import ForeignKey

    fk_fields = set()
    for field in model._meta.get_fields():
        if isinstance(field, ForeignKey):
            fk_fields.add(field.name)
    return fk_fields


def resolve_fk_values(model, data):
    """
    Convert FK fields from 'company: 1' to 'company_id: 1' pattern.

    For each FK field in data where value is an integer,
    renames the key to use Django's _id suffix pattern.
    This allows passing FK IDs directly without fetching objects.

    Args:
        model: Django model class
        data: Dict of field_name -> value

    Returns:
        New dict with FK fields converted to _id pattern

    Example:
        >>> resolve_fk_values(Service, {'company': 1, 'name': 'Test'})
        {'company_id': 1, 'name': 'Test'}
        >>> resolve_fk_values(Service, {'company': <Company>, 'name': 'Test'})
        {'company': <Company>, 'name': 'Test'}  # Objects left unchanged
    """
    fk_fields = get_fk_fields(model)
    result = {}

    for key, value in data.items():
        if key in fk_fields and isinstance(value, int):
            # FK with integer value -> use _id suffix
            result[f"{key}_id"] = value
        else:
            result[key] = value

    return result


def expand_wildcard(model, prefix=""):
    """
    Expand wildcard into concrete field names.

    Args:
        model: Django model class
        prefix: Optional prefix for nested relations

    Returns:
        List of field names (optionally prefixed)

    Examples:
        >>> expand_wildcard(Customer, "")
        ['id', 'name', 'email', 'phone']
        >>> expand_wildcard(Customer, "customer")
        ['customer.id', 'customer.name', 'customer.email', 'customer.phone']
    """
    fields = get_model_fields(model)
    if prefix:
        return [f"{prefix}.{f}" for f in fields]
    return fields


def filter_safe_wildcard(model_name, fields, permissions=None):
    """
    Remove excluded fields from expanded wildcard list.

    Uses the per-model 'exclude' configuration from permissions to
    prevent sensitive fields from being exposed via wildcard expansion.

    Args:
        model_name: Model name for looking up exclusions
        fields: List of field names to filter
        permissions: Optional permissions dict (uses settings if not provided)

    Returns:
        List with excluded fields removed
    """
    if permissions is None:
        permissions = flex_settings.PERMISSIONS

    model_name = model_name.lower()
    if model_name not in permissions:
        return fields

    exclude = permissions[model_name].get("exclude", [])
    return [f for f in fields if f not in exclude]


def expand_fields(model, field_specs, model_name=None, permissions=None):
    """
    Expand field specs, handling wildcards and nested relations.

    Args:
        model: Django model class
        field_specs: List of field specs (e.g., ["*", "customer.name"])
        model_name: Model name for exclude lookup (uses model.__name__ if not provided)
        permissions: Optional permissions dict

    Returns:
        List of fully qualified field paths (deduplicated, excluded fields removed)

    Examples:
        >>> expand_fields(Booking, ["*"])
        ['id', 'status', 'customer_id', 'created_at', ...]
        >>> expand_fields(Booking, ["id", "customer.*"])
        ['id', 'customer.id', 'customer.name', 'customer.email', ...]
    """
    if model_name is None:
        model_name = model.__name__

    if permissions is None:
        permissions = flex_settings.PERMISSIONS

    # H5 fix: Get max depth for validation
    max_depth = flex_settings.MAX_RELATION_DEPTH

    expanded = []
    relations = get_model_relations(model)

    for spec in field_specs:
        if spec == "*":
            # Expand base wildcard to model's concrete fields (minus excluded ones)
            base_fields = get_model_fields(model)
            safe_fields = filter_safe_wildcard(model_name, base_fields, permissions)
            expanded.extend(safe_fields)
        elif spec.endswith(".*"):
            # Relation wildcard: customer.* -> customer.id, customer.name, etc.
            relation_path = spec[:-2]
            parts = relation_path.split(".")

            # H5 fix: Check depth before expanding relation wildcard
            # The depth is the number of parts (each adds one level of nesting)
            # Plus 1 for the field that will be expanded (e.g., customer.* -> customer.id)
            if len(parts) > max_depth:
                raise ValueError(f"Relation wildcard '{spec}' exceeds max relation depth of {max_depth}")

            # Navigate to the related model
            current_model = model
            for part in parts:
                rel_map = get_model_relations(current_model)
                if part in rel_map:
                    current_model = rel_map[part]
                else:
                    break
            else:
                # Successfully navigated, expand the relation's fields (minus excluded ones)
                rel_fields = get_model_fields(current_model)
                # Use the related model's name for exclusion lookup
                safe_rel_fields = filter_safe_wildcard(current_model.__name__, rel_fields, permissions)
                expanded.extend([f"{relation_path}.{f}" for f in safe_rel_fields])
        else:
            # Regular field or dotted field path
            # H5 fix: Check depth for dotted fields
            if "." in spec:
                depth = spec.count(".")
                if depth > max_depth:
                    raise ValueError(f"Field '{spec}' exceeds max relation depth of {max_depth}")
            expanded.append(spec)

    # Deduplicate while preserving order
    return list(dict.fromkeys(expanded))


def extract_relations(field_paths):
    """
    Extract relation paths from field paths for select_related.

    This enables automatic N+1 prevention by identifying which relations
    need to be eagerly loaded.

    Args:
        field_paths: List of field paths (may include nested paths)

    Returns:
        Set of relation paths for select_related (using Django's __ notation)

    Examples:
        >>> extract_relations(["id", "status"])
        set()
        >>> extract_relations(["id", "customer.name"])
        {'customer'}
        >>> extract_relations(["id", "customer.address.city"])
        {'customer__address'}
    """
    relations = set()
    for path in field_paths:
        parts = path.split(".")
        if len(parts) > 1:
            # Convert customer.address.city -> customer__address (exclude last part which is the field)
            relation_path = "__".join(parts[:-1])
            relations.add(relation_path)
    return relations
