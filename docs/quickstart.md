# Quick Start Guide

This guide walks you through creating your first flexible query endpoint.

## Prerequisites

- Django-Flex installed (see [Installation Guide](installation.md))
- An existing Django model to query

## Example Model

Let's assume you have these models:

```python
# models.py
from django.db import models

class Customer(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Booking(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    scheduled_date = models.DateField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

## Step 1: Create a FlexQueryView

```python
# views.py
from django.db.models import Q
from django_flex import FlexQueryView
from .models import Booking

class BookingQueryView(FlexQueryView):
    """API endpoint for querying bookings."""
    
    model = Booking
    require_auth = True  # Require authentication
    
    flex_permissions = {
        'authenticated': {
            # Row filter - users see their team's bookings
            'rows': lambda user: Q(),  # All rows for now (customize later)
            
            # Allowed fields
            'fields': [
                'id', 'status', 'scheduled_date', 'notes',
                'customer.name', 'customer.email', 'customer.phone',
            ],
            
            # Allowed filters
            'filters': [
                'id',
                'status', 'status.in',
                'scheduled_date', 'scheduled_date.gte', 'scheduled_date.lte',
                'customer.name', 'customer.name.icontains',
            ],
            
            # Allowed ordering
            'order_by': [
                'id', '-id',
                'scheduled_date', '-scheduled_date',
                'created_at', '-created_at',
            ],
            
            # Allowed operations
            'ops': ['get', 'query'],
        },
    }
```

## Step 2: Add URL Route

```python
# urls.py
from django.urls import path
from .views import BookingQueryView

urlpatterns = [
    path('api/bookings/', BookingQueryView.as_view(), name='booking-query'),
    path('api/bookings/<int:pk>/', BookingQueryView.as_view(), name='booking-detail'),
]
```

## Step 3: Query from Frontend

### List Bookings

```javascript
// Fetch confirmed bookings with customer info
const response = await fetch('/api/bookings/', {
    method: 'GET',
    headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer your-token',  // If using token auth
    },
    body: JSON.stringify({
        fields: 'id, status, scheduled_date, customer.name, customer.email',
        filters: {
            'status': 'confirmed'
        },
        order_by: '-scheduled_date',
        limit: 10
    })
});

const data = await response.json();
console.log(data);
// {
//     "pagination": {
//         "offset": 0,
//         "limit": 10,
//         "has_more": false
//     },
//     "results": {
//         "1": {
//             "id": 1,
//             "status": "confirmed",
//             "scheduled_date": "2024-01-15",
//             "customer": {
//                 "name": "Aisha Khan",
//                 "email": "aisha@example.com"
//             }
//         },
//         "2": {
//             "id": 2,
//             "status": "confirmed",
//             "scheduled_date": "2024-01-14",
//             "customer": {
//                 "name": "Omar Hassan",
//                 "email": "omar@example.com"
//             }
//         }
//     }
// }
```

### Get Single Booking

```javascript
// Fetch specific booking by ID (via URL)
const response = await fetch('/api/bookings/1/', {
    method: 'GET',
    headers: {
        'Content-Type': 'application/json',
    },
    body: JSON.stringify({
        fields: 'id, status, scheduled_date, notes, customer.name, customer.phone'
    })
});

const data = await response.json();
// {
//     "id": 1,
//     "status": "confirmed",
//     "scheduled_date": "2024-01-15",
//     "notes": "Please call before arriving",
//     "customer": {
//         "name": "Aisha Khan",
//         "phone": "+61 400 123 456"
//     }
// }
```

### Advanced Filtering

```javascript
// Complex query with date range and OR conditions
const response = await fetch('/api/bookings/', {
    method: 'GET',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
        fields: 'id, status, scheduled_date, customer.name',
        filters: {
            'scheduled_date.gte': '2024-01-01',
            'scheduled_date.lte': '2024-01-31',
            'status.in': ['pending', 'confirmed']
        },
        order_by: 'scheduled_date',
        limit: 50
    })
});
```

## Step 4: Handle Pagination

When there are more results, the response includes a `next` cursor:

```javascript
let allResults = {};
let hasMore = true;
let querySpec = {
    fields: 'id, status, customer.name',
    limit: 20
};

while (hasMore) {
    const response = await fetch('/api/bookings/', {
        method: 'GET',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(querySpec)
    });
    
    const data = await response.json();
    
    // Merge results
    Object.assign(allResults, data.results);
    
    // Check for more pages
    hasMore = data.pagination?.has_more || false;
    if (hasMore) {
        querySpec = data.pagination.next;
    }
}

console.log(`Fetched ${Object.keys(allResults).length} bookings`);
```

## What's Next?

- [Permissions Guide](permissions.md) - Set up role-based access control
- [Filtering Guide](examples/filtering.md) - Advanced filtering examples
- [API Reference](api_reference.md) - Complete function and class documentation
