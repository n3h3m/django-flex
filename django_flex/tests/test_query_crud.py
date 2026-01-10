"""
Tests for FlexQuery CRUD operations.

Tests _execute_edit, _execute_add, _execute_delete methods
and their helper functions.
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from django.db.models import Q


class TestCheckActionPermission:
    """Tests for _check_action_permission helper method."""

    def test_returns_row_filter_on_success(self):
        """Should return row_filter when permission check passes."""
        from django_flex.query import FlexQuery

        query = FlexQuery("testmodel")
        query.model = MagicMock()
        user = MagicMock()
        user.is_authenticated = True

        with patch("django_flex.query.check_permission") as mock_check:
            mock_check.return_value = (Q(owner=user), [])

            result = query._check_action_permission(user, "edit", {})

            assert result == Q(owner=user)
            mock_check.assert_called_once()

    def test_returns_none_when_no_user(self):
        """Should return None when user is None."""
        from django_flex.query import FlexQuery

        query = FlexQuery("testmodel")
        query.model = MagicMock()

        result = query._check_action_permission(None, "edit", {})

        assert result is None

    def test_raises_permission_error_on_failure(self):
        """Should raise PermissionError when check fails."""
        from django_flex.query import FlexQuery

        query = FlexQuery("testmodel")
        query.model = MagicMock()
        user = MagicMock()
        user.is_authenticated = True

        with patch("django_flex.query.check_permission") as mock_check:
            mock_check.side_effect = PermissionError("Access denied")

            with pytest.raises(PermissionError):
                query._check_action_permission(user, "edit", {})


class TestGetObjectById:
    """Tests for _get_object_by_id helper method."""

    def test_returns_object_when_found(self):
        """Should return (obj, None) when object is found."""
        from django_flex.query import FlexQuery

        mock_model = MagicMock()
        mock_obj = MagicMock()
        mock_obj.pk = 1
        mock_model.objects.all.return_value.get.return_value = mock_obj
        mock_model.DoesNotExist = Exception

        query = FlexQuery("testmodel")
        query.model = mock_model

        obj, error = query._get_object_by_id({"id": 1}, None)

        assert obj == mock_obj
        assert error is None

    def test_returns_error_when_no_id(self):
        """Should return error when id not in query_spec."""
        from django_flex.query import FlexQuery

        query = FlexQuery("testmodel")
        query.model = MagicMock()

        obj, error = query._get_object_by_id({}, None)

        assert obj is None
        assert error is not None
        assert "id" in str(error.to_dict())

    def test_returns_not_found_when_object_missing(self):
        """Should return NOT_FOUND error when object doesn't exist."""
        from django_flex.query import FlexQuery

        mock_model = MagicMock()
        mock_model.DoesNotExist = Exception
        mock_model.objects.all.return_value.get.side_effect = mock_model.DoesNotExist()

        query = FlexQuery("testmodel")
        query.model = mock_model

        obj, error = query._get_object_by_id({"id": 999}, None)

        assert obj is None
        assert error is not None

    def test_applies_row_filter(self):
        """Should apply row_filter to queryset when provided."""
        from django_flex.query import FlexQuery

        mock_model = MagicMock()
        mock_obj = MagicMock()
        mock_queryset = MagicMock()
        mock_filtered = MagicMock()
        mock_model.objects.all.return_value = mock_queryset
        mock_queryset.filter.return_value = mock_filtered
        mock_filtered.get.return_value = mock_obj
        mock_model.DoesNotExist = Exception

        query = FlexQuery("testmodel")
        query.model = mock_model

        row_filter = Q(owner_id=5)
        obj, error = query._get_object_by_id({"id": 1}, row_filter)

        mock_queryset.filter.assert_called_once_with(row_filter)
        mock_filtered.get.assert_called_once_with(pk=1)


class TestGetAllowedFields:
    """Tests for _get_allowed_fields helper method."""

    def test_returns_star_when_no_permissions(self):
        """Should return ['*'] when no permissions configured."""
        from django_flex.query import FlexQuery

        query = FlexQuery("testmodel")
        query.model = MagicMock()

        result = query._get_allowed_fields(None, None)

        assert result == ["*"]

    def test_returns_configured_fields(self):
        """Should return configured fields for user's role."""
        from django_flex.query import FlexQuery

        query = FlexQuery("testmodel")
        query.model = MagicMock()

        user = MagicMock()
        user.is_authenticated = True
        user.is_superuser = False
        user.is_staff = False
        user.groups.first.return_value = None

        permissions = {
            "testmodel": {
                "authenticated": {
                    "fields": ["id", "name", "email"],
                    "ops": ["get", "edit"],
                }
            }
        }

        result = query._get_allowed_fields(user, permissions)

        assert result == ["id", "name", "email"]


class TestExecuteEdit:
    """Tests for _execute_edit method."""

    def test_edit_success(self):
        """Should successfully update object fields."""
        from django_flex.query import FlexQuery

        mock_model = MagicMock()
        mock_obj = MagicMock()
        mock_obj.pk = 1
        mock_model.objects.all.return_value.get.return_value = mock_obj
        mock_model.DoesNotExist = Exception

        query = FlexQuery("testmodel")
        query.model = mock_model
        query.model_name = "testmodel"

        query_spec = {"id": 1, "name": "Updated Name"}

        with patch.object(query, "_check_action_permission", return_value=None):
            with patch.object(query, "_get_allowed_fields", return_value=["*"]):
                result = query._execute_edit(query_spec, MagicMock(), {})

        assert result.success
        assert result.data.get("updated") is True
        mock_obj.save.assert_called_once()

    def test_edit_without_id_fails(self):
        """Should return error when id not provided."""
        from django_flex.query import FlexQuery

        query = FlexQuery("testmodel")
        query.model = MagicMock()
        query.model_name = "testmodel"

        with patch.object(query, "_check_action_permission", return_value=None):
            result = query._execute_edit({"name": "Test"}, MagicMock(), {})

        assert not result.success
        assert "id" in str(result.to_dict())

    def test_edit_disallowed_field_fails(self):
        """Should return PERMISSION_DENIED for disallowed field."""
        from django_flex.query import FlexQuery

        mock_model = MagicMock()
        mock_obj = MagicMock()
        mock_obj.pk = 1
        mock_model.objects.all.return_value.get.return_value = mock_obj
        mock_model.DoesNotExist = Exception

        query = FlexQuery("testmodel")
        query.model = mock_model
        query.model_name = "testmodel"

        query_spec = {"id": 1, "secret_field": "hacked"}

        with patch.object(query, "_check_action_permission", return_value=None):
            with patch.object(query, "_get_allowed_fields", return_value=["id", "name"]):
                result = query._execute_edit(query_spec, MagicMock(), {})

        assert not result.success
        assert "not editable" in str(result.to_dict())

    def test_edit_nonexistent_field_fails(self):
        """Should return INVALID_FIELD for nonexistent field."""
        from django_flex.query import FlexQuery

        mock_model = MagicMock()
        mock_obj = MagicMock()
        mock_obj.pk = 1
        # hasattr will return False for nonexistent field
        del mock_obj.nonexistent_field
        mock_model.objects.all.return_value.get.return_value = mock_obj
        mock_model.DoesNotExist = Exception

        query = FlexQuery("testmodel")
        query.model = mock_model
        query.model_name = "testmodel"

        query_spec = {"id": 1, "nonexistent_field": "value"}

        with patch.object(query, "_check_action_permission", return_value=None):
            with patch.object(query, "_get_allowed_fields", return_value=["*"]):
                with patch("builtins.hasattr", return_value=False):
                    result = query._execute_edit(query_spec, MagicMock(), {})

        assert not result.success
        assert "does not exist" in str(result.to_dict())


class TestExecuteAdd:
    """Tests for _execute_add method."""

    def test_add_success(self):
        """Should successfully create object."""
        from django_flex.query import FlexQuery

        mock_model = MagicMock()
        mock_obj = MagicMock()
        mock_obj.pk = 42
        mock_model.objects.create.return_value = mock_obj

        query = FlexQuery("testmodel")
        query.model = mock_model
        query.model_name = "testmodel"

        query_spec = {"name": "New Item", "status": "active"}

        with patch.object(query, "_check_action_permission", return_value=None):
            result = query._execute_add(query_spec, MagicMock(), {})

        assert result.success
        assert result.code == "CREATED"
        assert result.data.get("id") == 42
        mock_model.objects.create.assert_called_once_with(name="New Item", status="active")

    def test_add_permission_denied(self):
        """Should return PERMISSION_DENIED when user lacks permission."""
        from django_flex.query import FlexQuery

        query = FlexQuery("testmodel")
        query.model = MagicMock()
        query.model_name = "testmodel"

        with patch.object(query, "_check_action_permission", side_effect=PermissionError("No add permission")):
            result = query._execute_add({"name": "Test"}, MagicMock(), {})

        assert not result.success
        assert "No add permission" in str(result.to_dict())

    def test_add_create_failure(self):
        """Should return CREATE_FAILED on database error."""
        from django_flex.query import FlexQuery

        mock_model = MagicMock()
        mock_model.objects.create.side_effect = Exception("Database error")

        query = FlexQuery("testmodel")
        query.model = mock_model
        query.model_name = "testmodel"

        with patch.object(query, "_check_action_permission", return_value=None):
            result = query._execute_add({"name": "Test"}, MagicMock(), {})

        assert not result.success
        assert "Database error" in str(result.to_dict())

    def test_add_debug_mode_includes_full_object(self, settings):
        """When DEBUG=True, add response should include full object under model name key."""
        from django_flex.query import FlexQuery

        settings.DEBUG = True

        mock_model = MagicMock()
        mock_obj = MagicMock()
        mock_obj.pk = 42
        mock_obj.name = "Test Item"
        mock_obj.status = "active"
        mock_model.objects.create.return_value = mock_obj
        mock_model._meta.get_fields.return_value = []

        query = FlexQuery("Service")
        query.model = mock_model
        query.model_name = "Service"

        with patch.object(query, "_check_action_permission", return_value=None):
            result = query._execute_add({"name": "Test Item"}, MagicMock(), {})

        assert result.success
        assert result.code == "CREATED"
        assert result.data.get("id") == 42
        # In DEBUG mode, should include full object under lowercase model name
        assert "service" in result.data

    def test_add_non_debug_mode_excludes_full_object(self, settings):
        """When DEBUG=False, add response should NOT include full object."""
        from django_flex.query import FlexQuery

        settings.DEBUG = False

        mock_model = MagicMock()
        mock_obj = MagicMock()
        mock_obj.pk = 42
        mock_model.objects.create.return_value = mock_obj
        mock_model._meta.get_fields.return_value = []

        query = FlexQuery("Service")
        query.model = mock_model
        query.model_name = "Service"

        with patch.object(query, "_check_action_permission", return_value=None):
            result = query._execute_add({"name": "Test"}, MagicMock(), {})

        assert result.success
        assert result.data.get("id") == 42
        # In non-DEBUG mode, should NOT include full object
        assert "service" not in result.data


class TestExecuteDelete:
    """Tests for _execute_delete method."""

    def test_delete_success(self):
        """Should successfully delete object."""
        from django_flex.query import FlexQuery

        mock_model = MagicMock()
        mock_obj = MagicMock()
        mock_obj.pk = 1
        mock_model.objects.all.return_value.get.return_value = mock_obj
        mock_model.DoesNotExist = Exception

        query = FlexQuery("testmodel")
        query.model = mock_model
        query.model_name = "testmodel"

        with patch.object(query, "_check_action_permission", return_value=None):
            result = query._execute_delete({"id": 1}, MagicMock(), {})

        assert result.success
        assert result.data.get("deleted") is True
        mock_obj.delete.assert_called_once()

    def test_delete_without_id_fails(self):
        """Should return error when id not provided."""
        from django_flex.query import FlexQuery

        query = FlexQuery("testmodel")
        query.model = MagicMock()
        query.model_name = "testmodel"

        with patch.object(query, "_check_action_permission", return_value=None):
            result = query._execute_delete({}, MagicMock(), {})

        assert not result.success
        assert "id" in str(result.to_dict())

    def test_delete_not_found(self):
        """Should return NOT_FOUND when object doesn't exist."""
        from django_flex.query import FlexQuery
        from django_flex.response import FlexResponse

        query = FlexQuery("testmodel")
        query.model = MagicMock()
        query.model_name = "testmodel"

        not_found_error = FlexResponse.error("NOT_FOUND")

        with patch.object(query, "_check_action_permission", return_value=None):
            with patch.object(query, "_get_object_by_id", return_value=(None, not_found_error)):
                result = query._execute_delete({"id": 999}, MagicMock(), {})

        assert not result.success


class TestExecuteActionRouting:
    """Tests for execute() method action routing."""

    def test_routes_edit_action(self):
        """Should route 'edit' action to _execute_edit."""
        from django_flex.query import FlexQuery

        query = FlexQuery("testmodel")
        query.model = MagicMock()

        with patch.object(query, "_execute_edit") as mock_edit:
            mock_edit.return_value = MagicMock(success=True)

            query.execute({"id": 1, "name": "Test"}, action="edit")

            mock_edit.assert_called_once()

    def test_routes_add_action(self):
        """Should route 'add' action to _execute_add."""
        from django_flex.query import FlexQuery

        query = FlexQuery("testmodel")
        query.model = MagicMock()

        with patch.object(query, "_execute_add") as mock_add:
            mock_add.return_value = MagicMock(success=True)

            query.execute({"name": "Test"}, action="add")

            mock_add.assert_called_once()

    def test_routes_delete_action(self):
        """Should route 'delete' action to _execute_delete."""
        from django_flex.query import FlexQuery

        query = FlexQuery("testmodel")
        query.model = MagicMock()

        with patch.object(query, "_execute_delete") as mock_delete:
            mock_delete.return_value = MagicMock(success=True)

            query.execute({"id": 1}, action="delete")

            mock_delete.assert_called_once()

    def test_unknown_action_returns_error(self):
        """Should return error for unknown action."""
        from django_flex.query import FlexQuery

        query = FlexQuery("testmodel")
        query.model = MagicMock()

        result = query.execute({}, action="unknown_action")

        assert not result.success
        assert "Unknown action" in str(result.to_dict())


class TestFKInterchangeability:
    """Tests for ForeignKey interchangeability feature."""

    def test_get_fk_fields_returns_fk_names(self):
        """Should return set of FK field names."""
        from django_flex.fields import get_fk_fields
        from django.db import models

        # Create a mock model with FK fields
        mock_model = MagicMock()

        # Simulate ForeignKey fields
        fk_field = MagicMock(spec=models.ForeignKey)
        fk_field.name = "company"

        regular_field = MagicMock()
        regular_field.name = "name"

        mock_model._meta.get_fields.return_value = [fk_field, regular_field]

        result = get_fk_fields(mock_model)

        assert "company" in result
        assert "name" not in result

    def test_resolve_fk_values_converts_int_to_id_suffix(self):
        """Should convert FK integer values to _id suffix pattern."""
        from django_flex.fields import resolve_fk_values
        from django.db import models

        # Create mock model with FK field
        mock_model = MagicMock()
        fk_field = MagicMock(spec=models.ForeignKey)
        fk_field.name = "company"
        mock_model._meta.get_fields.return_value = [fk_field]

        data = {"company": 1, "name": "Test Service", "price": "50"}
        result = resolve_fk_values(mock_model, data)

        assert "company_id" in result
        assert result["company_id"] == 1
        assert "company" not in result
        assert result["name"] == "Test Service"
        assert result["price"] == "50"

    def test_resolve_fk_values_leaves_objects_unchanged(self):
        """Should leave FK object values unchanged (not convert to _id)."""
        from django_flex.fields import resolve_fk_values
        from django.db import models

        mock_model = MagicMock()
        fk_field = MagicMock(spec=models.ForeignKey)
        fk_field.name = "company"
        mock_model._meta.get_fields.return_value = [fk_field]

        company_obj = MagicMock()
        company_obj.pk = 1
        data = {"company": company_obj, "name": "Test"}
        result = resolve_fk_values(mock_model, data)

        # Object should stay as 'company', not converted to 'company_id'
        assert "company" in result
        assert result["company"] == company_obj
        assert "company_id" not in result

    def test_resolve_fk_values_handles_non_fk_fields(self):
        """Should leave non-FK fields unchanged."""
        from django_flex.fields import resolve_fk_values

        mock_model = MagicMock()
        mock_model._meta.get_fields.return_value = []

        data = {"name": "Test", "price": 100}
        result = resolve_fk_values(mock_model, data)

        assert result == {"name": "Test", "price": 100}

    def test_add_with_fk_as_integer(self):
        """Should successfully create object when FK passed as integer."""
        from django_flex.query import FlexQuery

        mock_model = MagicMock()
        mock_obj = MagicMock()
        mock_obj.pk = 42

        # Setup FK field detection
        from django.db import models

        fk_field = MagicMock(spec=models.ForeignKey)
        fk_field.name = "company"
        mock_model._meta.get_fields.return_value = [fk_field]
        mock_model.objects.create.return_value = mock_obj

        query = FlexQuery("testmodel")
        query.model = mock_model
        query.model_name = "testmodel"

        query_spec = {"company": 1, "name": "Test Service"}

        with patch.object(query, "_check_action_permission", return_value=None):
            result = query._execute_add(query_spec, MagicMock(), {})

        assert result.success
        assert result.code == "CREATED"
        # Verify create was called with company_id (not company)
        mock_model.objects.create.assert_called_once()
        call_kwargs = mock_model.objects.create.call_args[1]
        assert "company_id" in call_kwargs
        assert call_kwargs["company_id"] == 1

    def test_get_field_value_uses_id_column_for_simple_fk(self):
        """Should return raw _id value for simple FK field without fetching object."""
        from django_flex.response import get_field_value

        mock_obj = MagicMock()
        mock_obj.company_id = 5  # Raw FK ID

        # When fk_fields includes 'company', should use _id column
        result = get_field_value(mock_obj, "company", fk_fields={"company"})

        assert result == 5
        # Verify we accessed company_id, not company (which would trigger object fetch)

    def test_get_field_value_fetches_object_for_nested_fk(self):
        """Should fetch related object when accessing nested FK field like company.name."""
        from django_flex.response import get_field_value

        mock_company = MagicMock()
        mock_company.name = "Acme Corp"

        mock_obj = MagicMock()
        mock_obj.company = mock_company

        # For nested access, should traverse to the related object
        result = get_field_value(mock_obj, "company.name", fk_fields={"company"})

        assert result == "Acme Corp"
