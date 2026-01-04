"""
Tests for authentication API endpoints.

Tests cover:
- User registration
- User login (form and JSON)
- Get current user
- Token refresh
- Logout
"""

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings


class TestAuthRegister:
    """Tests for user registration endpoint."""

    def test_register_new_user(self, client: TestClient) -> None:
        """Test successful user registration."""
        response = client.post(
            f"{settings.API_V1_STR}/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "testpassword123",
                "full_name": "New User",
                "phone": "1234567890",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == "newuser@example.com"
        assert data["user"]["full_name"] == "New User"

    def test_register_existing_email(self, client: TestClient) -> None:
        """Test registration with existing email fails."""
        # First registration
        client.post(
            f"{settings.API_V1_STR}/auth/register",
            json={
                "email": "duplicate@example.com",
                "password": "testpassword123",
                "full_name": "First User",
            },
        )

        # Second registration with same email should fail
        response = client.post(
            f"{settings.API_V1_STR}/auth/register",
            json={
                "email": "duplicate@example.com",
                "password": "anotherpassword",
                "full_name": "Second User",
            },
        )
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    def test_register_invalid_email(self, client: TestClient) -> None:
        """Test registration with invalid email format fails."""
        response = client.post(
            f"{settings.API_V1_STR}/auth/register",
            json={
                "email": "notanemail",
                "password": "testpassword123",
                "full_name": "Test User",
            },
        )
        assert response.status_code == 422  # Validation error


class TestAuthLogin:
    """Tests for user login endpoints."""

    @pytest.fixture(autouse=True)
    def setup_user(self, client: TestClient) -> None:
        """Create a test user before running login tests."""
        client.post(
            f"{settings.API_V1_STR}/auth/register",
            json={
                "email": "logintest@example.com",
                "password": "testpassword123",
                "full_name": "Login Test User",
            },
        )

    def test_login_json_success(self, client: TestClient) -> None:
        """Test successful login with JSON body."""
        response = client.post(
            f"{settings.API_V1_STR}/auth/login/json",
            json={
                "email": "logintest@example.com",
                "password": "testpassword123",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == "logintest@example.com"

    def test_login_form_success(self, client: TestClient) -> None:
        """Test successful login with form data (OAuth2 compatible)."""
        response = client.post(
            f"{settings.API_V1_STR}/auth/login",
            data={
                "username": "logintest@example.com",
                "password": "testpassword123",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data

    def test_login_wrong_password(self, client: TestClient) -> None:
        """Test login with wrong password fails."""
        response = client.post(
            f"{settings.API_V1_STR}/auth/login/json",
            json={
                "email": "logintest@example.com",
                "password": "wrongpassword",
            },
        )
        assert response.status_code == 401
        assert "Incorrect" in response.json()["detail"]

    def test_login_nonexistent_user(self, client: TestClient) -> None:
        """Test login with non-existent user fails."""
        response = client.post(
            f"{settings.API_V1_STR}/auth/login/json",
            json={
                "email": "nonexistent@example.com",
                "password": "testpassword123",
            },
        )
        assert response.status_code == 401


class TestAuthMe:
    """Tests for get current user endpoint."""

    def test_get_me_authenticated(self, client: TestClient) -> None:
        """Test getting current user when authenticated."""
        # Register and get token
        register_response = client.post(
            f"{settings.API_V1_STR}/auth/register",
            json={
                "email": "metest@example.com",
                "password": "testpassword123",
                "full_name": "Me Test User",
            },
        )
        token = register_response.json()["access_token"]

        # Get current user
        response = client.get(
            f"{settings.API_V1_STR}/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "metest@example.com"
        assert data["full_name"] == "Me Test User"

    def test_get_me_unauthenticated(self, client: TestClient) -> None:
        """Test getting current user without token fails."""
        response = client.get(f"{settings.API_V1_STR}/auth/me")
        assert response.status_code == 401

    def test_get_me_invalid_token(self, client: TestClient) -> None:
        """Test getting current user with invalid token fails."""
        response = client.get(
            f"{settings.API_V1_STR}/auth/me",
            headers={"Authorization": "Bearer invalidtoken"},
        )
        assert response.status_code == 401


class TestAuthRefresh:
    """Tests for token refresh endpoint."""

    def test_refresh_token(self, client: TestClient) -> None:
        """Test refreshing access token."""
        # Register and get token
        register_response = client.post(
            f"{settings.API_V1_STR}/auth/register",
            json={
                "email": "refreshtest@example.com",
                "password": "testpassword123",
                "full_name": "Refresh Test User",
            },
        )
        token = register_response.json()["access_token"]

        # Refresh token
        response = client.post(
            f"{settings.API_V1_STR}/auth/refresh",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["access_token"] != token  # Should be new token


class TestAuthLogout:
    """Tests for logout endpoint."""

    def test_logout(self, client: TestClient) -> None:
        """Test logout endpoint."""
        # Register and get token
        register_response = client.post(
            f"{settings.API_V1_STR}/auth/register",
            json={
                "email": "logouttest@example.com",
                "password": "testpassword123",
                "full_name": "Logout Test User",
            },
        )
        token = register_response.json()["access_token"]

        # Logout
        response = client.post(
            f"{settings.API_V1_STR}/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert "logged out" in response.json()["message"].lower()
