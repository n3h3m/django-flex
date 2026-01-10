# JSONField Support

Django-Flex provides seamless support for Django's `JSONField`. The frontend can use the same dot notation for both ForeignKey relations and nested JSON data — no special handling required.

## Overview

When a model has a `JSONField`, you can:

1. **Select** nested JSON values with dot notation
2. **Filter** on nested JSON values with all Django operators
3. **Control access** with the same permission patterns

## Example Model

```python
from django.db.models import JSONField

class Customer(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField()
    metadata = JSONField(default=dict, blank=True)
    # Example metadata:
    # {
    #     "settings": {"theme": "dark", "notifications": true},
    #     "tags": ["vip", "premium"],
    #     "level": 5
    # }
```

## Field Selection

Use dot notation to select nested JSON values:

```javascript
// Select specific nested values
{ fields: 'name, metadata.settings.theme, metadata.level' }
// Returns: {
//     "name": "Alice",
//     "metadata": {
//         "settings": {"theme": "dark"},
//         "level": 5
//     }
// }

// Select entire JSONField
{ fields: 'name, metadata' }
// Returns: {
//     "name": "Alice", 
//     "metadata": {"settings": {...}, "tags": [...], "level": 5}
// }

// Works with wildcard expansion
{ fields: '*' }
// Returns all fields including the full metadata dict
```

## Filtering

All Django ORM operators work with JSONField nested values:

```javascript
// Simple equality
{ filters: { 'metadata.settings.theme': 'dark' } }

// Comparison operators
{ filters: { 'metadata.level.gte': 5 } }
{ filters: { 'metadata.level.lt': 10 } }

// Text operators
{ filters: { 'metadata.tags.icontains': 'vip' } }

// Complex filters with OR/AND/NOT
{
    filters: {
        or: [
            { 'metadata.level.gte': 10 },
            { 'metadata.tags.icontains': 'premium' }
        ]
    }
}
```

## Permission Configuration

JSONField paths work with the same permission patterns as regular fields:

```python
DJANGO_FLEX = {
    'EXPOSE': {
        'customer': {
            'staff': {
                'fields': [
                    'name',
                    'email',
                    'metadata',                  # Entire JSONField
                    'metadata.settings',         # Specific key
                    'metadata.settings.*',       # All nested keys (any depth)
                ],
                'filters': [
                    'metadata.settings.theme',   # Filter by theme
                    'metadata.level',            # Filter by level
                    'metadata.tags',             # Filter by tags
                ],
            }
        }
    }
}
```

### Pattern Matching

- `metadata` — allows the entire JSONField
- `metadata.settings` — allows only `metadata.settings` (not deeper)
- `metadata.settings.*` — allows any nested path under `metadata.settings` at any depth

## How It Works

Under the hood, Django-Flex:

1. **Detects JSONFields** via model introspection (`get_json_fields()`)
2. **Converts dot notation** to Django's double-underscore format
3. **Traverses JSON dicts** when building response data

This is transparent to the frontend — the same dot notation works for both ForeignKey relations and JSONField nested keys.

## API Functions

### get_json_fields(model)

Get list of JSONField names for a model.

```python
from django_flex.fields import get_json_fields

get_json_fields(Customer)  # ['metadata']
```

### is_json_field_path(model, field_path)

Check if a field path starts with a JSONField.

```python
from django_flex.fields import is_json_field_path

is_json_field_path(Customer, 'metadata.settings.theme')
# (True, 'metadata', 'settings.theme')

is_json_field_path(Customer, 'name')
# (False, None, None)
```

## Limitations

1. **No wildcard expansion into JSON** — `metadata.*` in fields doesn't auto-expand JSON keys (since JSON structure isn't known at query time). Use explicit paths or request the whole field.

2. **JSON structure must exist** — Filtering on `metadata.settings.theme` will fail if `settings` key doesn't exist in the JSON. Handle with `isnull` operator if needed.

3. **Arrays are treated as values** — `metadata.tags` returns the full array; you can't select individual array indices.
