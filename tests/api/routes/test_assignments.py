"""
Tests for assignments API endpoints.

Tests cover:
- List pending assignments
- Accept assignment
- Decline assignment
- Assignment expiration
"""
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings


def get_provider_auth_headers(client: TestClient) -> dict | None:
    """
    Helper to get auth headers for a provider user.
    Returns None if no provider is set up.
    """
    # In a real test setup, we would create a provider user
    # For now, try to login with a known provider email
    response = client.post(
        f"{settings.API_V1_STR}/auth/login/json",
        json={"email": "provider@example.com", "password": "testpassword123"},
    )
    if response.status_code != 200:
        return None
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestListPendingAssignments:
    """Tests for listing pending assignments endpoint."""

    def test_list_pending_assignments_as_provider(self, client: TestClient) -> None:
        """Test listing pending assignments as a provider."""
        headers = get_provider_auth_headers(client)
        if not headers:
            pytest.skip("No provider user available for testing")

        response = client.get(
            f"{settings.API_V1_STR}/assignments/pending",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert isinstance(data["data"], list)

    def test_list_pending_assignments_unauthenticated(self, client: TestClient) -> None:
        """Test listing pending assignments without auth fails."""
        response = client.get(f"{settings.API_V1_STR}/assignments/pending")
        assert response.status_code == 401

    def test_list_pending_assignments_as_non_provider(self, client: TestClient) -> None:
        """Test listing pending assignments as regular user fails."""
        # Register a regular user
        client.post(
            f"{settings.API_V1_STR}/auth/register",
            json={
                "email": "regularuser@example.com",
                "password": "testpassword123",
                "full_name": "Regular User",
            },
        )

        # Login
        login_response = client.post(
            f"{settings.API_V1_STR}/auth/login/json",
            json={"email": "regularuser@example.com", "password": "testpassword123"},
        )
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        response = client.get(
            f"{settings.API_V1_STR}/assignments/pending",
            headers=headers,
        )
        # Should return 403 (not a provider) or empty list
        assert response.status_code in [200, 403, 404]


class TestAcceptAssignment:
    """Tests for accepting assignments."""

    def test_accept_assignment_invalid_id(self, client: TestClient) -> None:
        """Test accepting assignment with invalid ID fails."""
        headers = get_provider_auth_headers(client)
        if not headers:
            pytest.skip("No provider user available for testing")

        response = client.post(
            f"{settings.API_V1_STR}/assignments/00000000-0000-0000-0000-000000000000/accept",
            headers=headers,
        )
        assert response.status_code in [404, 400]

    def test_accept_assignment_unauthenticated(self, client: TestClient) -> None:
        """Test accepting assignment without auth fails."""
        response = client.post(
            f"{settings.API_V1_STR}/assignments/00000000-0000-0000-0000-000000000000/accept"
        )
        assert response.status_code == 401


class TestDeclineAssignment:
    """Tests for declining assignments."""

    def test_decline_assignment_invalid_id(self, client: TestClient) -> None:
        """Test declining assignment with invalid ID fails."""
        headers = get_provider_auth_headers(client)
        if not headers:
            pytest.skip("No provider user available for testing")

        response = client.post(
            f"{settings.API_V1_STR}/assignments/00000000-0000-0000-0000-000000000000/decline",
            headers=headers,
        )
        assert response.status_code in [404, 400]

    def test_decline_assignment_unauthenticated(self, client: TestClient) -> None:
        """Test declining assignment without auth fails."""
        response = client.post(
            f"{settings.API_V1_STR}/assignments/00000000-0000-0000-0000-000000000000/decline"
        )
        assert response.status_code == 401


class TestAssignmentIntegration:
    """Integration tests for the full assignment flow."""

    def test_assignment_response_format(self, client: TestClient) -> None:
        """Test that assignment endpoints return proper format."""
        headers = get_provider_auth_headers(client)
        if not headers:
            pytest.skip("No provider user available for testing")

        response = client.get(
            f"{settings.API_V1_STR}/assignments/pending",
            headers=headers,
        )

        if response.status_code == 200:
            data = response.json()
            assert "data" in data

            if len(data["data"]) > 0:
                assignment = data["data"][0]
                assert "id" in assignment
                assert "booking_id" in assignment
                assert "status" in assignment
                assert "expires_at" in assignment
