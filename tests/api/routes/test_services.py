"""
Tests for services API endpoints.

Tests cover:
- List service categories
- List services
- Get service by ID
- Filter services by category
"""

from fastapi.testclient import TestClient

from app.core.config import settings


class TestServiceCategories:
    """Tests for service categories endpoints."""

    def test_list_categories(self, client: TestClient) -> None:
        """Test listing all service categories."""
        response = client.get(f"{settings.API_V1_STR}/services/categories")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "count" in data
        assert isinstance(data["data"], list)

    def test_categories_structure(self, client: TestClient) -> None:
        """Test that categories have required fields."""
        response = client.get(f"{settings.API_V1_STR}/services/categories")
        assert response.status_code == 200
        data = response.json()

        if data["count"] > 0:
            category = data["data"][0]
            assert "id" in category
            assert "name" in category
            assert "description" in category


class TestServices:
    """Tests for services endpoints."""

    def test_list_services(self, client: TestClient) -> None:
        """Test listing all services."""
        response = client.get(f"{settings.API_V1_STR}/services")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "count" in data
        assert isinstance(data["data"], list)

    def test_services_structure(self, client: TestClient) -> None:
        """Test that services have required fields."""
        response = client.get(f"{settings.API_V1_STR}/services")
        assert response.status_code == 200
        data = response.json()

        if data["count"] > 0:
            service = data["data"][0]
            assert "id" in service
            assert "name" in service
            assert "base_price" in service
            assert "duration_minutes" in service

    def test_filter_services_by_category(self, client: TestClient) -> None:
        """Test filtering services by category ID."""
        # First get a category
        categories_response = client.get(f"{settings.API_V1_STR}/services/categories")
        categories = categories_response.json()["data"]

        if len(categories) > 0:
            category_id = categories[0]["id"]
            response = client.get(
                f"{settings.API_V1_STR}/services", params={"category_id": category_id}
            )
            assert response.status_code == 200
            data = response.json()

            # All returned services should belong to this category
            for service in data["data"]:
                assert service["category_id"] == category_id

    def test_get_service_by_id(self, client: TestClient) -> None:
        """Test getting a specific service by ID."""
        # First get a service from the list
        services_response = client.get(f"{settings.API_V1_STR}/services")
        services = services_response.json()["data"]

        if len(services) > 0:
            service_id = services[0]["id"]
            response = client.get(f"{settings.API_V1_STR}/services/{service_id}")
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == service_id

    def test_get_nonexistent_service(self, client: TestClient) -> None:
        """Test getting a non-existent service returns 404."""
        response = client.get(
            f"{settings.API_V1_STR}/services/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 404
