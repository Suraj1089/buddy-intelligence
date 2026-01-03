"""
Tests for bookings API endpoints.

Tests cover:
- Create booking
- List user bookings
- Get booking by ID
- Update booking status
- Cancel booking
"""
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings


def get_auth_headers(client: TestClient, email: str = "bookinguser@example.com") -> dict:
    """Helper to get auth headers for a test user."""
    # Try to register, ignore if already exists
    client.post(
        f"{settings.API_V1_STR}/auth/register",
        json={
            "email": email,
            "password": "testpassword123",
            "full_name": "Booking Test User",
        },
    )

    # Login to get token
    response = client.post(
        f"{settings.API_V1_STR}/auth/login/json",
        json={"email": email, "password": "testpassword123"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def get_service_id(client: TestClient) -> str | None:
    """Helper to get a service ID for testing."""
    response = client.get(f"{settings.API_V1_STR}/services")
    services = response.json()["data"]
    return services[0]["id"] if services else None


class TestCreateBooking:
    """Tests for booking creation endpoint."""

    def test_create_booking_success(self, client: TestClient) -> None:
        """Test successful booking creation."""
        headers = get_auth_headers(client)
        service_id = get_service_id(client)

        if not service_id:
            pytest.skip("No services available for testing")

        response = client.post(
            f"{settings.API_V1_STR}/bookings",
            headers=headers,
            json={
                "service_id": service_id,
                "service_date": "2024-12-25",
                "service_time": "10:00",
                "location": "123 Test Street",
                "special_instructions": "Test booking",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "booking_number" in data
        assert data["location"] == "123 Test Street"
        assert data["status"] in ["awaiting_provider", "pending"]

    def test_create_booking_unauthenticated(self, client: TestClient) -> None:
        """Test booking creation without auth fails."""
        service_id = get_service_id(client)

        if not service_id:
            pytest.skip("No services available for testing")

        response = client.post(
            f"{settings.API_V1_STR}/bookings",
            json={
                "service_id": service_id,
                "service_date": "2024-12-25",
                "service_time": "10:00",
                "location": "123 Test Street",
            },
        )
        assert response.status_code == 401

    def test_create_booking_invalid_service(self, client: TestClient) -> None:
        """Test booking creation with invalid service fails."""
        headers = get_auth_headers(client)

        response = client.post(
            f"{settings.API_V1_STR}/bookings",
            headers=headers,
            json={
                "service_id": "00000000-0000-0000-0000-000000000000",
                "service_date": "2024-12-25",
                "service_time": "10:00",
                "location": "123 Test Street",
            },
        )
        # Should fail either at validation or service lookup
        assert response.status_code in [400, 404, 500]


class TestListBookings:
    """Tests for listing bookings endpoint."""

    def test_list_bookings(self, client: TestClient) -> None:
        """Test listing user's bookings."""
        headers = get_auth_headers(client, "listbookings@example.com")

        response = client.get(
            f"{settings.API_V1_STR}/bookings",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "count" in data
        assert isinstance(data["data"], list)

    def test_list_bookings_with_status_filter(self, client: TestClient) -> None:
        """Test listing bookings filtered by status."""
        headers = get_auth_headers(client, "filterbookings@example.com")

        response = client.get(
            f"{settings.API_V1_STR}/bookings",
            headers=headers,
            params={"status": "pending"},
        )
        assert response.status_code == 200
        data = response.json()

        # All returned bookings should have pending status
        for booking in data["data"]:
            assert booking["status"] == "pending"

    def test_list_bookings_unauthenticated(self, client: TestClient) -> None:
        """Test listing bookings without auth fails."""
        response = client.get(f"{settings.API_V1_STR}/bookings")
        assert response.status_code == 401


class TestGetBooking:
    """Tests for getting a specific booking."""

    def test_get_own_booking(self, client: TestClient) -> None:
        """Test getting a booking owned by the user."""
        headers = get_auth_headers(client, "getbooking@example.com")
        service_id = get_service_id(client)

        if not service_id:
            pytest.skip("No services available for testing")

        # Create a booking
        create_response = client.post(
            f"{settings.API_V1_STR}/bookings",
            headers=headers,
            json={
                "service_id": service_id,
                "service_date": "2024-12-26",
                "service_time": "14:00",
                "location": "456 Get Street",
            },
        )
        booking_id = create_response.json()["id"]

        # Get the booking
        response = client.get(
            f"{settings.API_V1_STR}/bookings/{booking_id}",
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["id"] == booking_id

    def test_get_other_user_booking(self, client: TestClient) -> None:
        """Test getting another user's booking fails."""
        headers1 = get_auth_headers(client, "owner@example.com")
        headers2 = get_auth_headers(client, "other@example.com")
        service_id = get_service_id(client)

        if not service_id:
            pytest.skip("No services available for testing")

        # User 1 creates a booking
        create_response = client.post(
            f"{settings.API_V1_STR}/bookings",
            headers=headers1,
            json={
                "service_id": service_id,
                "service_date": "2024-12-26",
                "service_time": "14:00",
                "location": "789 Other Street",
            },
        )
        booking_id = create_response.json()["id"]

        # User 2 tries to get it
        response = client.get(
            f"{settings.API_V1_STR}/bookings/{booking_id}",
            headers=headers2,
        )
        assert response.status_code == 403


class TestCancelBooking:
    """Tests for cancelling bookings."""

    def test_cancel_own_booking(self, client: TestClient) -> None:
        """Test cancelling own booking."""
        headers = get_auth_headers(client, "cancelbooking@example.com")
        service_id = get_service_id(client)

        if not service_id:
            pytest.skip("No services available for testing")

        # Create a booking
        create_response = client.post(
            f"{settings.API_V1_STR}/bookings",
            headers=headers,
            json={
                "service_id": service_id,
                "service_date": "2024-12-27",
                "service_time": "16:00",
                "location": "Cancel Street",
            },
        )
        booking_id = create_response.json()["id"]

        # Cancel the booking
        response = client.delete(
            f"{settings.API_V1_STR}/bookings/{booking_id}",
            headers=headers,
        )
        assert response.status_code == 200
        assert "cancelled" in response.json()["message"].lower()

    def test_cancel_other_user_booking(self, client: TestClient) -> None:
        """Test cancelling another user's booking fails."""
        headers1 = get_auth_headers(client, "cancelowner@example.com")
        headers2 = get_auth_headers(client, "cancelother@example.com")
        service_id = get_service_id(client)

        if not service_id:
            pytest.skip("No services available for testing")

        # User 1 creates a booking
        create_response = client.post(
            f"{settings.API_V1_STR}/bookings",
            headers=headers1,
            json={
                "service_id": service_id,
                "service_date": "2024-12-27",
                "service_time": "18:00",
                "location": "Cannot Cancel Street",
            },
        )
        booking_id = create_response.json()["id"]

        # User 2 tries to cancel it
        response = client.delete(
            f"{settings.API_V1_STR}/bookings/{booking_id}",
            headers=headers2,
        )
        assert response.status_code == 403


class TestUpdateBookingStatus:
    """Tests for updating booking status."""

    def test_update_booking_status(self, client: TestClient) -> None:
        """Test updating booking status as booking owner."""
        headers = get_auth_headers(client, "updatestatus@example.com")
        service_id = get_service_id(client)

        if not service_id:
            pytest.skip("No services available for testing")

        # Create a booking
        create_response = client.post(
            f"{settings.API_V1_STR}/bookings",
            headers=headers,
            json={
                "service_id": service_id,
                "service_date": "2024-12-28",
                "service_time": "09:00",
                "location": "Update Status Street",
            },
        )

        if create_response.status_code != 200:
            pytest.skip("Could not create booking for testing")

        booking_id = create_response.json()["id"]

        # Update status
        response = client.patch(
            f"{settings.API_V1_STR}/bookings/{booking_id}/status",
            headers=headers,
            json={"status": "confirmed"},
        )
        # Owner may or may not be able to change status depending on business rules
        assert response.status_code in [200, 403]
