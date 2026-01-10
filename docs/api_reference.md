# API Reference

Complete API documentation for django-flex.

## Core Classes

### FlexQuery

The main query execution class.

```python
from django_flex import FlexQuery

# Initialize with model class or name
query = FlexQuery(Booking)
query = FlexQuery('booking')

# Execute a query
result = query.execute({
    'fields': 'id, customer.name',
    'filters': {'status': 'confirmed'},
    'limit': 20,
}, user=request.user)

# Chained configuration
result = (FlexQuery(Booking)
    .set_user(request.user)
    .set_permissions(custom_permissions)
    .execute(query_spec))
```

**Methods:**

| Method | Description |
|--------|-------------|
| `__init__(model)` | Initialize with Django model class or model name string |
| `set_user(user)` | Set user for permission checking, returns self for chaining |
| `set_permissions(permissions)` | Set custom permissions dict, returns self for chaining |
| `execute(query_spec, user=None, action=None)` | Execute query and return `FlexResponse` |

---

### FlexResponse

Response builder class.

```python
from django_flex import FlexResponse

# Create responses
response = FlexResponse.ok(id=1, name='Test')
response = FlexResponse.ok_query(results={'1': {...}}, pagination={...})
response = FlexResponse.error('NOT_FOUND', 'Object not found')
response = FlexResponse.warning_response('LIMIT_CLAMPED', results={...})

# Convert to dict or Django response
data = response.to_dict()
http_response = response.to_json_response()
```

**Class Methods:**

| Method | Description |
|--------|-------------|
| `ok(**data)` | Create successful single-object response |
| `ok_query(results, pagination=None, **data)` | Create successful list response |
| `error(code, message=None)` | Create error response |
| `warning_response(code, **data)` | Create success response with warning flag |

**Instance Methods:**

| Method | Description |
|--------|-------------|
| `to_dict()` | Convert to dictionary for JSON serialization |
| `to_json_response()` | Convert to Django `JsonResponse` |

---

### FlexQueryView

Class-based view for handling flex queries.

```python
from django_flex import FlexQueryView

class BookingQueryView(FlexQueryView):
    model = Booking
    require_auth = True
    allowed_actions = ['get', 'query']
    flex_permissions = {...}
```

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `model` | Model class | Required. The Django model to query |
| `flex_permissions` | dict | Optional. Per-role permissions for this view |
| `require_auth` | bool | Optional. Require authentication (default: True) |
| `allowed_actions` | list | Optional. Allowed actions (default: ['get', 'query']) |

**Override Methods:**

| Method | Description |
|--------|-------------|
| `get_model()` | Override for dynamic model selection |
| `get_permissions()` | Override for dynamic permissions |
| `get_user(request)` | Override for custom user resolution |
| `check_auth(request)` | Override for custom authentication logic |
| `get_query_spec(request)` | Override for custom query parsing |

---

## Decorator

### flex_query

Function decorator for adding flex query capabilities.

```python
from django_flex import flex_query

@flex_query(
    model=Booking,
    allowed_fields=['id', 'status', 'customer.name'],
    allowed_filters=['status', 'status.in'],
    allowed_ordering=['created_at', '-created_at'],
    require_auth=True,
    allowed_actions=['get', 'query'],
)
def booking_list(request, result, query_spec):
    return JsonResponse(result.to_dict())
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `model` | Model class | Required. The Django model to query |
| `allowed_fields` | list | Optional. Allowed field patterns (default: ['*']) |
| `allowed_filters` | list | Optional. Allowed filter keys (default: []) |
| `allowed_ordering` | list | Optional. Allowed order_by values (default: []) |
| `require_auth` | bool | Optional. Require authentication (default: True) |
| `allowed_actions` | list | Optional. Allowed actions (default: ['get', 'query']) |

---

## Field Utilities

### parse_fields

Parse comma-separated field string into list.

```python
from django_flex import parse_fields

parse_fields("name, email")  # ['name', 'email']
parse_fields("id, customer.name")  # ['id', 'customer.name']
parse_fields("*")  # ['*']
parse_fields("")  # ['*']
parse_fields(None)  # ['*']
```

---

### expand_fields

Expand field specs with wildcard handling.

```python
from django_flex import expand_fields

expand_fields(Booking, ['*'])
# ['id', 'status', 'customer_id', 'created_at', ...]

expand_fields(Booking, ['id', 'customer.*'])
# ['id', 'customer.id', 'customer.name', 'customer.email', ...]
```

---

### get_model_fields

Get list of concrete field names for a model.

```python
from django_flex import get_model_fields

get_model_fields(User)  # ['id', 'email', 'username', ...]
```

---

### get_model_relations

Get dict of relation_name -> related_model.

```python
from django_flex import get_model_relations

get_model_relations(Booking)
# {'customer': <class 'Customer'>, 'address': <class 'Address'>}
```

---

### extract_relations

Extract relation paths for `select_related`.

```python
from django_flex import extract_relations

extract_relations(['id', 'status'])
# set()

extract_relations(['id', 'customer.name'])
# {'customer'}

extract_relations(['id', 'customer.address.city'])
# {'customer__address'}
```

---

## Filter Utilities

### parse_filter_key

Parse filter key into field path and operator.

```python
from django_flex import parse_filter_key

parse_filter_key('status')  # ('status', None)
parse_filter_key('customer.name')  # ('customer__name', None)
parse_filter_key('price.gte')  # ('price', 'gte')
parse_filter_key('customer.name.icontains')  # ('customer__name', 'icontains')
```

---

### build_q_object

Build Django Q object from filter specification.

```python
from django_flex import build_q_object

build_q_object({'status': 'confirmed'})
# Q(status='confirmed')

build_q_object({'price.gte': 100, 'price.lte': 500})
# Q(price__gte=100) & Q(price__lte=500)

build_q_object({'or': {'status': 'pending', 'urgent': True}})
# Q(status='pending') | Q(urgent=True)
```

---

### extract_filter_keys

Extract all filter keys from specification (for validation).

```python
from django_flex import extract_filter_keys

extract_filter_keys({'name': 'Test', 'status': 'active'})
# ['name', 'status']

extract_filter_keys({'or': {'name': 'A', 'status': 'B'}})
# ['name', 'status']
```

---

### OPERATORS

Set of supported Django ORM operators.

```python
from django_flex import OPERATORS

print(OPERATORS)
# {'lt', 'lte', 'gt', 'gte', 'exact', 'iexact', 'in', 'isnull', 'range',
#  'contains', 'icontains', 'startswith', 'istartswith', 'endswith', 'iendswith',
#  'regex', 'iregex', 'date', 'year', 'month', 'day', 'week_day', 'hour', 'minute', 'second'}
```

---

## Permission Functions

### check_permission

Check if user has permission for action on model.

```python
from django_flex import check_permission

row_filter, fields = check_permission(
    user=request.user,
    model_name='booking',
    action='query',
    requested_fields=['id', 'status', 'customer.name'],
)

queryset = Booking.objects.filter(row_filter)
```

**Raises:** `PermissionError` if permission denied.

---

### check_filter_permission

Check if user can filter on given keys.

```python
from django_flex import check_filter_permission

check_filter_permission(
    user=request.user,
    model_name='booking',
    filter_keys=['status', 'status.in', 'customer.name.icontains'],
)
```

**Raises:** `PermissionError` if filter key not allowed.

---

### check_order_permission

Check if user can order by given field.

```python
from django_flex import check_order_permission

check_order_permission(
    user=request.user,
    model_name='booking',
    order_by='-created_at',
)
```

**Raises:** `PermissionError` if order_by not allowed.

---

## Response Functions

### build_nested_response

Build nested dict from object and field paths.

```python
from django_flex import build_nested_response

result = build_nested_response(booking, ['id', 'status', 'customer.name'])
# {
#     'id': 1,
#     'status': 'confirmed',
#     'customer': {
#         'name': 'Aisha Khan'
#     }
# }
```

---

## Settings

### flex_settings

Access django-flex settings.

```python
from django_flex import flex_settings

print(flex_settings.DEFAULT_LIMIT)  # 50
print(flex_settings.MAX_LIMIT)  # 200
print(flex_settings.PERMISSIONS)  # {...}
```

**Available Settings:**

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `DEFAULT_LIMIT` | int | 50 | Default pagination limit |
| `MAX_LIMIT` | int | 200 | Maximum pagination limit |
| `MAX_RELATION_DEPTH` | int | 2 | Max depth for nested fields/filters |
| `REQUIRE_AUTHENTICATION` | bool | True | Require auth by default |
| `AUDIT_QUERIES` | bool | False | Log all queries |
| `PERMISSIONS` | dict | {} | Model permissions configuration |

---

## HTTP Status Codes

| Status | Meaning |
|--------|---------|
| `200` | Success - data returned in response body |
| `400` | Bad request - invalid query specification |
| `401` | Unauthorized - authentication required |
| `403` | Forbidden - permission denied |
| `404` | Not found - object not found |
| `500` | Server error - internal error |

The response body contains only data (for success) or `{"error": "..."}` (for errors).
