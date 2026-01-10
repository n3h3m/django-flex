# Basic Usage Examples

This guide covers common usage patterns for django-flex.

## Single Object Retrieval

### Get by ID

```javascript
// Fetch a specific booking
const response = await fetch('/api/bookings/123/', {
    method: 'GET',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
        fields: 'id, status, customer.name'
    })
});

const data = await response.json();
// {
//     "id": 123,
//     "status": "confirmed",
//     "customer": {"name": "Aisha Khan"}
// }
```

### Get with All Fields

```javascript
{
    id: 123,
    fields: '*'  // All fields on the model
}
```

### Get with Related Fields

```javascript
{
    id: 123,
    fields: 'id, status, customer.*, address.*'
}
// Expands to all customer and address fields
```

---

## List Retrieval

### Basic List

```javascript
const response = await fetch('/api/bookings/', {
    method: 'GET',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
        fields: 'id, status, customer.name'
    })
});

// Returns first 50 results by default
```

### With Pagination

```javascript
{
    fields: 'id, status',
    limit: 20,
    offset: 0
}

// Response includes pagination info:
// {
//     "pagination": {
//         "offset": 0,
//         "limit": 20,
//         "has_more": true,
//         "next": {...}
//     }
// }
```

### With Ordering

```javascript
// Ascending order
{
    fields: 'id, status, scheduled_date',
    order_by: 'scheduled_date'
}

// Descending order
{
    fields: 'id, status, scheduled_date',
    order_by: '-scheduled_date'
}

// Order by related field
{
    fields: 'id, customer.name',
    order_by: 'customer.name'
}
```

---

## Field Selection Patterns

### Minimal Fields (Performance)

```javascript
// Only fetch what you need
{
    fields: 'id, status'
}
```

### Wildcard Expansion

```javascript
// All model fields
{
    fields: '*'
}

// All model fields + specific relation
{
    fields: '*, customer.name'
}

// All relation fields
{
    fields: 'id, customer.*'
}
```

### Deep Nesting

```javascript
// Two levels of relation
{
    fields: 'id, customer.name, customer.address.city'
}
```

---

## Pagination Patterns

### Manual Pagination

```javascript
let offset = 0;
const limit = 20;

const fetchPage = async () => {
    const response = await fetch('/api/bookings/', {
        method: 'GET',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            fields: 'id, status',
            limit,
            offset
        })
    });
    const data = await response.json();
    
    // Move to next page
    if (data.pagination.has_more) {
        offset += limit;
    }
    
    return data.results;
};
```

### Cursor-Based Pagination

```javascript
let currentQuery = {
    fields: 'id, status',
    limit: 20
};

const fetchNextPage = async () => {
    const response = await fetch('/api/bookings/', {
        method: 'GET',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(currentQuery)
    });
    const data = await response.json();
    
    // Use the next cursor for the following request
    if (data.pagination.has_more) {
        currentQuery = data.pagination.next;
    }
    
    return data.results;
};
```

### Fetch All (with batching)

```javascript
const fetchAll = async () => {
    let allResults = {};
    let query = {
        fields: 'id, status',
        limit: 100
    };
    let hasMore = true;
    
    while (hasMore) {
        const response = await fetch('/api/bookings/', {
            method: 'GET',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(query)
        });
        const data = await response.json();
        
        Object.assign(allResults, data.results);
        
        hasMore = data.pagination.has_more;
        if (hasMore) {
            query = data.pagination.next;
        }
    }
    
    return allResults;
};
```

---

## React/Vue Integration

### React Custom Hook

```javascript
import { useState, useCallback } from 'react';

const useFlexQuery = (endpoint) => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    
    const query = useCallback(async (spec) => {
        setLoading(true);
        setError(null);
        
        try {
            const response = await fetch(endpoint, {
                method: 'GET',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(spec)
            });
            const result = await response.json();
            
            if (response.ok) {
                setData(result);
            } else {
                setError(result.error || 'Request failed');
            }
            
            return result;
        } catch (err) {
            setError(err.message);
            throw err;
        } finally {
            setLoading(false);
        }
    }, [endpoint]);
    
    return { data, loading, error, query };
};

// Usage
function BookingList() {
    const { data, loading, error, query } = useFlexQuery('/api/bookings/');
    
    useEffect(() => {
        query({
            fields: 'id, status, customer.name',
            filters: { status: 'confirmed' },
            limit: 20
        });
    }, []);
    
    if (loading) return <div>Loading...</div>;
    if (error) return <div>Error: {error}</div>;
    
    return (
        <ul>
            {Object.entries(data?.results || {}).map(([id, booking]) => (
                <li key={id}>{booking.customer.name} - {booking.status}</li>
            ))}
        </ul>
    );
}
```

### Vue Composable

```javascript
import { ref } from 'vue';

export function useFlexQuery(endpoint) {
    const data = ref(null);
    const loading = ref(false);
    const error = ref(null);
    
    async function query(spec) {
        loading.value = true;
        error.value = null;
        
        try {
            const response = await fetch(endpoint, {
                method: 'GET',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(spec)
            });
            const result = await response.json();
            
            if (response.ok) {
                data.value = result;
            } else {
                error.value = result.error || 'Request failed';
            }
            
            return result;
        } catch (err) {
            error.value = err.message;
            throw err;
        } finally {
            loading.value = false;
        }
    }
    
    return { data, loading, error, query };
}
```

---

## Error Handling

### Check Response Status

```javascript
const response = await fetch('/api/bookings/999999/', {
    method: 'GET',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({fields: 'id'})
});

const data = await response.json();

if (!response.ok) {
    // Use HTTP status to determine error type
    switch (response.status) {
        case 404:
            console.error('Object not found');
            break;
        case 403:
            console.error('Permission denied:', data.error);
            break;
        case 400:
            console.error('Invalid request:', data.error);
            break;
        default:
            console.error('Error:', data.error);
    }
}
```

### Handle Limit Clamping Warning

```javascript
const data = await response.json();

if (data.warning && data.warning_code === 'LIMIT_CLAMPED') {
    console.warn(
        `Requested ${data.requested_limit} items, ` +
        `but server limit is ${data.pagination.limit}`
    );
}
```
