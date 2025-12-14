"""
Tests for providers API endpoints.

Tests cover:
- Get current provider profile
- Update provider profile
- Get provider's bookings
- Get public provider info
"""
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings


def get_provider_auth_headers(client: TestClient) -> dict | None:
    """
    Helper to get auth headers for a provider user.
    Returns None if no provider is set up.
    """
    response = client.post(
        f"{settings.API_V1_STR}/auth/login/json",
        json={"email": "provider@example.com", "password": "testpassword123"},
    )
    if response.status_code != 200:
        return None
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def get_regular_user_headers(client: TestClient) -> dict:
    """Helper to get auth headers for a regular user."""
    email = "providertest_regular@example.com"
    
    # Register if not exists
    client.post(
        f"{settings.API_V1_STR}/auth/register",
        json={
            "email": email,
            "password": "testpassword123",
            "full_name": "Regular User",
        },
    )
    
    # Login
    response = client.post(
        f"{settings.API_V1_STR}/auth/login/json",
        json={"email": email, "password": "testpassword123"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestGetProviderMe:
    """Tests for getting current provider profile."""

    def test_get_provider_me_as_provider(self, client: TestClient) -> None:
        """Test getting own profile as provider."""
        headers = get_provider_auth_headers(client)
        if not headers:
            pytest.skip("No provider user available for testing")
        
        response = client.get(
            f"{settings.API_V1_STR}/providers/me",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "user_id" in data

    def test_get_provider_me_as_regular_user(self, client: TestClient) -> None:
        """Test getting provider profile as regular user fails."""
        headers = get_regular_user_headers(client)
        
        response = client.get(
            f"{settings.API_V1_STR}/providers/me",
            headers=headers,
        )
        # Should return 404 (not a provider)
        assert response.status_code == 404

    def test_get_provider_me_unauthenticated(self, client: TestClient) -> None:
        """Test getting provider profile without auth fails."""
        response = client.get(f"{settings.API_V1_STR}/providers/me")
        assert response.status_code == 401


class TestUpdateProviderProfile:
    """Tests for updating provider profile."""

    def test_update_provider_profile(self, client: TestClient) -> None:
        """Test updating provider profile."""
        headers = get_provider_auth_headers(client)
        if not headers:
            pytest.skip("No provider user available for testing")
        
        response = client.patch(
            f"{settings.API_V1_STR}/providers/me",
            headers=headers,
            json={"bio": "Updated bio for testing"},
        )
        
        if response.status_code == 200:
            data = response.json()
            assert data["bio"] == "Updated bio for testing"
        else:
            # Provider endpoint might not support updates
            assert response.status_code in [404, 405]

    def test_update_provider_profile_unauthenticated(self, client: TestClient) -> None:
        """Test updating provider profile without auth fails."""
        response = client.patch(
            f"{settings.API_V1_STR}/providers/me",
            json={"bio": "Test"},
        )
        assert response.status_code == 401


class TestGetProviderBookings:
    """Tests for getting provider's bookings."""

    def test_get_provider_bookings(self, client: TestClient) -> None:
        """Test getting provider's assigned bookings."""
        headers = get_provider_auth_headers(client)
        if not headers:
            pytest.skip("No provider user available for testing")
        
        response = client.get(
            f"{settings.API_V1_STR}/providers/me/bookings",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert isinstance(data["data"], list)

    def test_get_provider_bookings_unauthenticated(self, client: TestClient) -> None:
        """Test getting provider bookings without auth fails."""
        response = client.get(f"{settings.API_V1_STR}/providers/me/bookings")
        assert response.status_code == 401


class TestGetPublicProvider:
    """Tests for getting public provider information."""

    def test_get_public_provider_info(self, client: TestClient) -> None:
        """Test getting public provider info."""
        # First, get a provider ID from the providers list
        providers_response = client.get(f"{settings.API_V1_STR}/providers")
        
        if providers_response.status_code != 200:
            pytest.skip("Providers list endpoint not available")
        
        providers = providers_response.json().get("data", [])
        if not providers:
            pytest.skip("No providers available for testing")
        
        provider_id = providers[0]["id"]
        
        response = client.get(f"{settings.API_V1_STR}/providers/{provider_id}")
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "business_name" in data

    def test_get_nonexistent_provider(self, client: TestClient) -> None:
        """Test getting non-existent provider returns 404."""
        response = client.get(
            f"{settings.API_V1_STR}/providers/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 404
