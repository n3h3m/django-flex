# Filtering Examples

This guide provides comprehensive examples of filtering with django-flex.

## Basic Filters

### Simple Equality

```javascript
// Filter by exact value
{
    filters: { status: 'confirmed' }
}

// Multiple conditions (AND)
{
    filters: {
        status: 'confirmed',
        urgent: true
    }
}
```

### Comparison Operators

```javascript
// Less than
{ filters: { 'price.lt': 100 } }

// Less than or equal
{ filters: { 'price.lte': 100 } }

// Greater than
{ filters: { 'price.gt': 50 } }

// Greater than or equal
{ filters: { 'price.gte': 50 } }

// Range (between)
{ filters: { 'price.gte': 50, 'price.lte': 200 } }
```

### List Membership

```javascript
// IN operator
{
    filters: { 'status.in': ['pending', 'confirmed', 'completed'] }
}
```

### Null Checks

```javascript
// Is null
{ filters: { 'assignee.isnull': true } }

// Is not null
{ filters: { 'assignee.isnull': false } }
```

---

## Text Search

### Case-Sensitive

```javascript
// Contains
{ filters: { 'name.contains': 'Khan' } }

// Starts with
{ filters: { 'name.startswith': 'A' } }

// Ends with
{ filters: { 'email.endswith': '@example.com' } }
```

### Case-Insensitive (Recommended)

```javascript
// Contains (case-insensitive)
{ filters: { 'name.icontains': 'khan' } }

// Starts with (case-insensitive)
{ filters: { 'name.istartswith': 'a' } }

// Exact match (case-insensitive)
{ filters: { 'email.iexact': 'John@Example.COM' } }
```

### Regular Expressions

```javascript
// Regex match
{ filters: { 'phone.regex': '^\\+61' } }  // Australian numbers

// Regex match (case-insensitive)
{ filters: { 'name.iregex': '^(john|jane)' } }
```

---

## Date and Time Filters

### Date Comparisons

```javascript
// After a date
{ filters: { 'created_at.gte': '2024-01-01' } }

// Before a date
{ filters: { 'created_at.lte': '2024-12-31' } }

// Date range (this year)
{
    filters: {
        'created_at.gte': '2024-01-01',
        'created_at.lte': '2024-12-31'
    }
}
```

### Date Parts

```javascript
// Filter by year
{ filters: { 'created_at.year': 2024 } }

// Filter by month (1-12)
{ filters: { 'created_at.month': 1 } }

// Filter by day of month (1-31)
{ filters: { 'created_at.day': 15 } }

// Filter by day of week (1=Sunday, 7=Saturday)
{ filters: { 'scheduled_date.week_day': 2 } }  // Monday
```

### Time Parts (for DateTime fields)

```javascript
// Filter by hour (0-23)
{ filters: { 'created_at.hour': 14 } }  // 2 PM

// Filter by minute (0-59)
{ filters: { 'created_at.minute': 30 } }
```

---

## Nested Relation Filters

### Single Level Nesting

```javascript
// Filter by related model field
{ filters: { 'customer.name.icontains': 'khan' } }

// Filter by related model ID
{ filters: { 'customer.id': 123 } }
```

### Multiple Relation Fields

```javascript
{
    filters: {
        'customer.name.icontains': 'khan',
        'customer.vip': true,
        'address.city': 'Sydney'
    }
}
```

### Deep Nesting (up to MAX_RELATION_DEPTH)

```javascript
// Two levels deep
{ filters: { 'customer.address.city.icontains': 'sydney' } }
```

---

## Composable Filters

### OR Conditions

```javascript
// Either condition
{
    filters: {
        or: {
            status: 'pending',
            urgent: true
        }
    }
}

// Multiple OR groups (as list)
{
    filters: {
        or: [
            { status: 'pending' },
            { status: 'confirmed', urgent: true }
        ]
    }
}
```

### AND Conditions (Explicit)

```javascript
// Explicit AND (same as default behavior)
{
    filters: {
        and: {
            status: 'confirmed',
            'scheduled_date.gte': '2024-01-01'
        }
    }
}
```

### NOT Conditions

```javascript
// Exclude cancelled
{
    filters: {
        not: { status: 'cancelled' }
    }
}

// Exclude multiple statuses
{
    filters: {
        not: { 'status.in': ['cancelled', 'no_show'] }
    }
}
```

### Complex Composition

```javascript
// (status = 'confirmed' AND scheduled_date >= today) 
// OR 
// (urgent = true AND NOT cancelled)
{
    filters: {
        or: [
            {
                status: 'confirmed',
                'scheduled_date.gte': '2024-01-10'
            },
            {
                urgent: true,
                not: { status: 'cancelled' }
            }
        ]
    }
}
```

---

## Real-World Examples

### Search Customers

```javascript
const searchCustomers = async (searchTerm) => {
    const response = await fetch('/api/customers/', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            fields: 'id, name, email, phone',
            filters: {
                or: {
                    'name.icontains': searchTerm,
                    'email.icontains': searchTerm,
                    'phone.icontains': searchTerm
                }
            },
            order_by: 'name',
            limit: 20
        })
    });
    return response.json();
};
```

### Upcoming Bookings Dashboard

```javascript
const getUpcomingBookings = async () => {
    const today = new Date().toISOString().split('T')[0];
    const nextWeek = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000)
        .toISOString().split('T')[0];
    
    const response = await fetch('/api/bookings/', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            fields: 'id, status, scheduled_date, customer.name, address.city',
            filters: {
                'scheduled_date.gte': today,
                'scheduled_date.lte': nextWeek,
                'status.in': ['pending', 'confirmed']
            },
            order_by: 'scheduled_date',
            limit: 50
        })
    });
    return response.json();
};
```

### Unassigned Urgent Bookings

```javascript
const getUnassignedUrgent = async () => {
    const response = await fetch('/api/bookings/', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            fields: 'id, status, scheduled_date, customer.name, customer.phone',
            filters: {
                'assignee.isnull': true,
                urgent: true,
                not: { 'status.in': ['completed', 'cancelled'] }
            },
            order_by: 'scheduled_date',
            limit: 100
        })
    });
    return response.json();
};
```

### VIP Customers with Recent Activity

```javascript
const getActiveVIPs = async () => {
    const thirtyDaysAgo = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000)
        .toISOString().split('T')[0];
    
    const response = await fetch('/api/customers/', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            fields: 'id, name, email, last_booking_date, total_bookings',
            filters: {
                vip: true,
                'last_booking_date.gte': thirtyDaysAgo
            },
            order_by: '-total_bookings',
            limit: 20
        })
    });
    return response.json();
};
```

---

## Error Handling

### Permission Denied

If you try to filter on a field that's not allowed:

```javascript
// Request with disallowed filter
{
    filters: { 'internal_notes.icontains': 'secret' }
}

// Response (HTTP 403)
{
    "error": "Filter denied: 'internal_notes.icontains' not allowed for filtering"
}
```

### Invalid Operator

Using an unsupported operator:

```javascript
// Invalid operator
{
    filters: { 'name.fuzzy': 'khan' }  // 'fuzzy' is not a valid operator
}

// This will be treated as a field path, not an operator
// It will try to filter on 'name.fuzzy' field, which likely doesn't exist
```

### Relation Depth Exceeded

```javascript
// Too deep (if MAX_RELATION_DEPTH = 2)
{
    filters: { 'customer.address.country.code.icontains': 'AU' }  // 4 levels
}

// Response (HTTP 403)
{
    "error": "Filter denied: '...' exceeds max relation depth of 2"
}
```
