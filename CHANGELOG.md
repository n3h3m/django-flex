# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2024-01-10

### Added

- Initial release of django-flex
- Core query engine with field selection and filtering
- Permission system with row-level, field-level, and operation-level access control
- `FlexQueryView` class-based view for easy integration
- `flex_query` decorator for function-based views
- Optional middleware for centralized endpoint
- Comprehensive documentation and examples
- Support for Django 3.2, 4.0, 4.1, 4.2, 5.0, and 6.0
- Support for Python 3.8, 3.9, 3.10, 3.11, 3.12, and 3.14

### CRUD Action Names

- `get` - Retrieve single object by ID
- `query` - Query multiple objects with filters/pagination
- `create` - Create new objects
- `update` - Update existing objects
- `delete` - Delete objects

### Features

- **Field Selection**: Use comma-separated field strings with dot notation for relations
  - Wildcards: `*` for all fields, `customer.*` for all customer fields
  - Nested relations: `customer.address.city`
- **Filtering**: Full Django ORM operator support
  - Comparison: `lt`, `lte`, `gt`, `gte`, `exact`, `in`, `isnull`, `range`
  - Text: `contains`, `icontains`, `startswith`, `endswith`, `regex`
  - Date/Time: `date`, `year`, `month`, `day`, `hour`, `minute`, `second`
  - Composable: `and`, `or`, `not` for complex conditions
- **Pagination**: Limit/offset with smart cursor-based continuation
- **Security**: Principle of least privilege with deny-by-default
- **Performance**: Automatic `select_related` for N+1 prevention
