# Permissions Guide

Django-Flex uses a **deny-by-default** security model. Users have no access unless explicitly granted.

## Django Auth Integration

Django-Flex integrates natively with Django's built-in auth system:

- **User.is_superuser** → bypasses all permission checks
- **User.is_staff** → gets `staff` role
- **User.groups** → first group name becomes the role
- **Authenticated (no group)** → gets `authenticated` role

### Role Resolution Order

By default, Django-Flex resolves roles using Django's auth system:

```python
# Default role resolution (without ROLE_RESOLVER):
if user.is_superuser:
    role = "superuser"  # Bypasses ALL checks
elif user.is_staff:
    role = "staff"
elif user.groups.exists():
    role = user.groups.first().name.lower()
else:
    role = "authenticated"
```

### Custom Role Resolution (ROLE_RESOLVER)

For custom logic, configure `ROLE_RESOLVER` — a callable that takes `(user, model_name)` and returns:

- **String**: Just the role name
- **Tuple**: `(role_name, row_filter)` for centralized row-level security

```python
# settings.py
from django.db.models import Q

def my_role_resolver(user, model_name):
    """Custom role resolver with optional row-level security."""
    if not user.is_authenticated:
        return 'anon'

    membership = user.company_memberships.filter(is_active=True).first()
    if not membership:
        return 'authenticated'

    # Return (role, row_filter) for centralized security
    company_filter = Q(company_id=membership.company_id)
    return (membership.role.lower(), company_filter)

DJANGO_FLEX = {
    'ROLE_RESOLVER': my_role_resolver,
    ...
}
```

**Resolution Order with ROLE_RESOLVER:**

1. Custom `ROLE_RESOLVER` callable (if configured)
2. superuser → 'superuser' (bypasses all checks)
3. staff → 'staff'
4. First matching group name (lowercase)
5. 'authenticated' if logged in
6. 'anon' if anonymous

## Permission Layers

Django-Flex enforces security at four levels:

1. **Row-Level** — Which database rows can the user see?
2. **Field-Level** — Which fields can the user access on those rows?
3. **Filter-Level** — Which fields can the user filter on?
4. **Operation-Level** — Which actions (get, query, create, update, delete) can the user perform?

## Configuration Structure

### Quick Reference

| Config Value             | Meaning                     |
| ------------------------ | --------------------------- |
| `"*"`                    | **Allow all** (full access) |
| `{}`, `[]`, `""`, `None` | **Deny all** (no access)    |

### The `"*"` Shorthand

Use `"*"` to grant full access to a role:

```python
DJANGO_FLEX = {
    'EXPOSE': {
        'user': {'superuser': '*'},     # Full access
        'booking': {'admin': '*'},      # Full access to bookings
    },
}
```

Expands to:

```python
{'rows': '*', 'fields': ['*'], 'filters': '*', 'order_by': '*', 'ops': ['get', 'list', 'add', 'edit', 'delete']}
```

### Explicit Configuration

```python
# settings.py
DJANGO_FLEX = {
    'EXPOSE': {
        '<model_name>': {
            'exclude': ['password_hash', 'api_secret'],

            '<role_name>': {
                'rows': <callable or "*">,
                'fields': [<field patterns>],
                'filters': [<filter+operator pairs>],  # Each operator explicit!\n                'order_by': [<order values>],
                'ops': [<operations>],
            },
        },
    },
}
```

## Row-Level Security

The `rows` key is a callable that receives the user and returns a Django `Q` object.

```python
from django.db.models import Q

DJANGO_FLEX = {
    'EXPOSE': {
        'article': {
            'staff': {
                # Staff see all articles
                'rows': lambda user: Q(),
                # ...
            },
            'authenticated': {
                # Authenticated users see only published articles
                'rows': lambda user: Q(status='published'),
                # ...
            },
        },
        'profile': {
            'authenticated': {
                # Users can only see their own profile
                'rows': lambda user: Q(user=user),
                # ...
            },
        },
    },
}
```

### Example: Multi-Tenant Isolation

```python
'rows': lambda user: Q(tenant=user.profile.tenant)
```

### Example: Team-Based Access

```python
'rows': lambda user: Q(team__in=user.teams.all())
```

### Row Filter Precedence (with ROLE_RESOLVER)

When using `ROLE_RESOLVER` that returns `(role, row_filter)`, the row filter precedence is:

1. **Config `rows`** (if specified) — takes priority, allows per-model override
2. **Resolver's row_filter** — used if no config `rows` (centralized security)
3. **No filter** — all rows allowed if neither is specified

```python
# ROLE_RESOLVER returns (role, company_filter)
def resolver(user, model_name):
    return ('staff', Q(company_id=user.company_id))

DJANGO_FLEX = {
    'ROLE_RESOLVER': resolver,
    'EXPOSE': {
        'booking': {
            'staff': {
                'fields': ['*'],
                'ops': ['get', 'list'],
                # No 'rows' — uses resolver's company_filter automatically
            },
        },
        'audit_log': {
            'staff': {
                'fields': ['id', 'action'],
                'ops': ['list'],
                'rows': '*',  # Override: allow all rows (admins can see full audit)
            },
        },
    },
}
```

## Field-Level Security

The `fields` list uses pattern matching:

| Pattern              | Matches                         | Example                    |
| -------------------- | ------------------------------- | -------------------------- |
| `*`                  | All direct fields on model      | `id`, `name`, `status`     |
| `<field>`            | Exact field name                | `id`, `status`             |
| `<relation>.*`       | All fields on related model     | `author.id`, `author.name` |
| `<relation>.<field>` | Specific field on related model | `author.name`              |

```python
'staff': {
    # Can access everything including nested relations
    'fields': ['*', 'author.*', 'category.*'],
    # ...
},
'authenticated': {
    # Limited access - specific fields only
    'fields': ['id', 'title', 'content', 'author.name'],
    # ...
},
```

### Excluding Sensitive Fields

Use the `exclude` key to prevent fields from being exposed via wildcards:

```python
'user': {
    'exclude': ['password', 'api_key', 'secret_token'],

    'staff': {
        'fields': ['*'],  # Even with *, excluded fields won't be returned
        # ...
    },
}
```

## Filter-Level Security

The `filters` list specifies which filter+operator combinations are allowed. **Each must be explicitly listed.**

```python
'staff': {
    'filters': [
        # Each filter AND operator must be listed separately
        'status',              # Only exact: status=value
        'status.in',           # status.in=[a,b,c]
        'status.iexact',       # Case-insensitive match

        # Date filters - each operator explicit
        'created_at.gte',      # >= date
        'created_at.lte',      # <= date
        # NOTE: 'created_at' alone does NOT allow 'created_at.gte'!

        # Nested field filters
        'author.id',
        'author.name.icontains',  # Search by name
    ],
    # ...
},
```

> **Important**: `'status'` does NOT auto-allow `'status.in'` or `'status.gte'`. Each filter+operator must be explicitly granted.

## Order-Level Security

The `order_by` list specifies which orderings are allowed:

```python
'authenticated': {
    'order_by': [
        'id', '-id',                    # Ascending and descending
        'created_at', '-created_at',
        'title', '-title',
    ],
    # ...
},
```

**Important**: Include both ascending and descending variants if you want to allow both directions.

## Operation-Level Security

The `ops` list specifies which operations the role can perform:

| Operation | Description                         |
| --------- | ----------------------------------- |
| `get`     | Retrieve single object by ID        |
| `query`   | Query multiple objects with filters |
| `create`  | Create new objects                  |
| `update`  | Update existing objects             |
| `delete`  | Delete objects                      |

```python
'staff': {
    'ops': ['get', 'list', 'add', 'edit', 'delete'],  # Full access
},
'authenticated': {
    'ops': ['get', 'list'],  # Read-only
},
# Roles not listed have NO ACCESS AT ALL
```

## Complete Example

```python
# settings.py
from django.db.models import Q

DJANGO_FLEX = {
    'DEFAULT_LIMIT': 50,
    'MAX_LIMIT': 200,
    'MAX_RELATION_DEPTH': 2,

    'EXPOSE': {
        # =====================
        # ARTICLE MODEL
        # =====================
        'article': {
            'exclude': ['draft_content', 'internal_notes'],

            'staff': {
                'rows': lambda user: Q(),  # All articles
                'fields': ['*', 'author.*', 'category.*'],
                'filters': [
                    'id', 'status', 'status.in',
                    'created_at.gte', 'created_at.lte',
                    'author.id', 'author.name.icontains',
                    'category.id', 'category.name',
                ],
                'order_by': ['id', '-id', 'created_at', '-created_at', 'title', '-title'],
                'ops': ['get', 'list', 'add', 'edit', 'delete'],
            },
            'authenticated': {
                'rows': lambda user: Q(status='published'),  # Only published
                'fields': ['id', 'title', 'content', 'author.name', 'category.name'],
                'filters': [
                    'id', 'category.id',
                    'title.icontains',
                ],
                'order_by': ['created_at', '-created_at', 'title'],
                'ops': ['get', 'list'],
            },
        },

        # =====================
        # USER PROFILE MODEL
        # =====================
        'profile': {
            'exclude': ['ssn', 'internal_id'],

            'staff': {
                'rows': lambda user: Q(),
                'fields': ['*'],
                'filters': ['id', 'user.id', 'user.email.icontains'],
                'order_by': ['id', 'created_at', '-created_at'],
                'ops': ['get', 'list', 'edit'],
            },
            'authenticated': {
                'rows': lambda user: Q(user=user),  # Own profile only
                'fields': ['id', 'bio', 'avatar', 'user.email'],
                'filters': ['id'],
                'order_by': [],
                'ops': ['get', 'edit'],
            },
        },

        # =====================
        # COMMENT MODEL
        # =====================
        'comment': {
            'staff': {
                'rows': lambda user: Q(),
                'fields': ['*', 'author.*', 'article.*'],
                'filters': ['id', 'article.id', 'author.id', 'created_at.gte'],
                'order_by': ['created_at', '-created_at'],
                'ops': ['get', 'list', 'add', 'edit', 'delete'],
            },
            'authenticated': {
                'rows': lambda user: Q(article__status='published'),
                'fields': ['id', 'content', 'author.name', 'created_at'],
                'filters': ['article.id'],
                'order_by': ['-created_at', 'created_at'],
                'ops': ['get', 'list', 'add'],
            },
        },
    },
}
```

## Setting Up Django Groups

Django-Flex uses Django's built-in groups for roles:

```python
# Create groups in a migration or management command
from django.contrib.auth.models import Group

Group.objects.get_or_create(name='Staff')
Group.objects.get_or_create(name='Editor')
Group.objects.get_or_create(name='Viewer')

# Assign user to a group
user.groups.add(Group.objects.get(name='Editor'))
```

Then configure permissions for these group names:

```python
DJANGO_FLEX = {
    'EXPOSE': {
        'article': {
            'staff': {...},     # Users in "Staff" group
            'editor': {...},    # Users in "Editor" group
            'viewer': {...},    # Users in "Viewer" group
            'authenticated': {...},  # Logged in users with no group
        },
    },
}
```

## Security Best Practices

1. **Start Restrictive** — Begin with minimal permissions and expand as needed
2. **Use Exclude** — Always exclude sensitive fields from wildcard expansion
3. **Limit Relation Depth** — Set `MAX_RELATION_DEPTH` to prevent deep traversal
4. **Use Django Groups** — Leverage Django's built-in group system for role management
5. **Test Permissions** — Write tests that verify permission denials, not just grants
