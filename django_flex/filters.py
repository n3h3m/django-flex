"""
Django-Flex Filter Utilities

Handles filter parsing and Q object construction for flexible queries.

Supports:
- Simple equality filters
- Django ORM operators (lt, gte, icontains, etc.)
- Composable filters (and, or, not)
- Nested relation filtering
"""

from django.db.models import Q


# Django ORM operators supported in filters
OPERATORS = {
    # Comparisons
    "lt",
    "lte",
    "gt",
    "gte",
    "exact",
    "iexact",
    "in",
    "isnull",
    "range",
    # Text
    "contains",
    "icontains",
    "startswith",
    "istartswith",
    "endswith",
    "iendswith",
    "regex",
    "iregex",
    # Date/Time
    "date",
    "year",
    "month",
    "day",
    "week_day",
    "hour",
    "minute",
    "second",
}


def parse_filter_key(key):
    """
    Parse a filter key into (field_path, operator).

    Converts dot notation to Django's double underscore format and
    extracts any operator suffix.

    Args:
        key: Filter key string (e.g., "customer.name.icontains")

    Returns:
        Tuple of (field_path, operator) where operator may be None

    Examples:
        >>> parse_filter_key("status")
        ('status', None)
        >>> parse_filter_key("customer.name")
        ('customer__name', None)
        >>> parse_filter_key("customer.name.icontains")
        ('customer__name', 'icontains')
        >>> parse_filter_key("customer.address.zip.lt")
        ('customer__address__zip', 'lt')
    """
    parts = key.split(".")

    # Check if last part is an operator
    if parts[-1] in OPERATORS:
        operator = parts[-1]
        field_parts = parts[:-1]
    else:
        operator = None
        field_parts = parts

    # Convert dot notation to Django's double underscore
    field_path = "__".join(field_parts)

    return field_path, operator


def build_q_object(filters):
    """
    Build Django Q object from filter specification.

    Supports:
    - Simple equality: {"status": "confirmed"}
    - Operators: {"status.in": ["confirmed", "completed"]}
    - Composable: {"or": {...}, "and": {...}, "not": {...}}
    - Mixed combinations of the above

    Args:
        filters: Dict of filter specifications

    Returns:
        Django Q object representing the filter

    Examples:
        >>> build_q_object({"status": "confirmed"})
        <Q: (AND: ('status', 'confirmed'))>

        >>> build_q_object({"price.gte": 100, "price.lte": 500})
        <Q: (AND: ('price__gte', 100), ('price__lte', 500))>

        >>> build_q_object({"or": {"status": "pending", "status": "confirmed"}})
        <Q: (OR: ('status', 'pending'), ('status', 'confirmed'))>
    """
    if not filters:
        return Q()

    q_objects = []

    for key, value in filters.items():
        if key == "or":
            # OR composition
            if isinstance(value, dict):
                sub_q = Q()
                for sub_key, sub_value in value.items():
                    field_path, operator = parse_filter_key(sub_key)
                    if operator:
                        sub_q |= Q(**{f"{field_path}__{operator}": sub_value})
                    else:
                        sub_q |= Q(**{field_path: sub_value})
                q_objects.append(sub_q)
            elif isinstance(value, list):
                # OR as list of conditions
                sub_q = Q()
                for item in value:
                    sub_q |= build_q_object(item)
                q_objects.append(sub_q)
        elif key == "and":
            # AND composition (explicit)
            if isinstance(value, dict):
                sub_q = build_q_object(value)
                q_objects.append(sub_q)
            elif isinstance(value, list):
                sub_q = Q()
                for item in value:
                    sub_q &= build_q_object(item)
                q_objects.append(sub_q)
        elif key == "not":
            # NOT composition
            sub_q = ~build_q_object(value)
            q_objects.append(sub_q)
        else:
            # Regular field filter
            field_path, operator = parse_filter_key(key)
            if operator:
                q_objects.append(Q(**{f"{field_path}__{operator}": value}))
            else:
                q_objects.append(Q(**{field_path: value}))

    # Combine all with AND (default)
    result = Q()
    for q in q_objects:
        result &= q

    return result


def extract_filter_keys(filters, keys=None):
    """
    Recursively extract all filter keys from a filter specification.

    Used for permission validation to ensure all filter keys are allowed.

    Args:
        filters: Dict of filter specification
        keys: Running list of keys (internal use)

    Returns:
        List of filter keys (e.g., ["name", "status.in", "company.name.icontains"])

    Examples:
        >>> extract_filter_keys({"name": "Test", "status": "active"})
        ['name', 'status']
        >>> extract_filter_keys({"or": {"name": "A", "status": "B"}})
        ['name', 'status']
    """
    if keys is None:
        keys = []

    if not filters:
        return keys

    for key, value in filters.items():
        if key in ("or", "and"):
            # Handle dict or list of sub-filters
            if isinstance(value, dict):
                extract_filter_keys(value, keys)
            elif isinstance(value, list):
                for item in value:
                    extract_filter_keys(item, keys)
        elif key == "not":
            # NOT composition
            extract_filter_keys(value, keys)
        else:
            # Regular filter key
            keys.append(key)

    return keys
