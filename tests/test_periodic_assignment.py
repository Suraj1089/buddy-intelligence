from unittest.mock import MagicMock, patch

from sqlmodel import Session

from app.booking_models import AssignmentQueueDB, BookingDB
from app.tasks.assignment_tasks import process_unassigned_bookings


class TestPeriodicAssignment:
    """Tests for automatic provider assignment via periodic tasks."""

    def test_process_unassigned_bookings_triggers_assignment(self):
        """
        Verify that `process_unassigned_bookings` finds bookings in 'awaiting_provider'
        status with no pending assignments and triggers `process_new_booking`.
        """
        # Mock session and database objects
        mock_session = MagicMock(spec=Session)

        # Create a mock booking that needs assignment
        mock_booking = MagicMock(spec=BookingDB)
        mock_booking.id = "booking-123"
        mock_booking.status = "awaiting_provider"
        mock_booking.provider_id = None

        # Setup mocks to simulate finding this booking
        # First query finds bookings
        # Second query (inside loop) checks for pending assignments -> returns None
        bookings_result = MagicMock()
        bookings_result.all.return_value = [mock_booking]

        pending_result = MagicMock()
        pending_result.first.return_value = None  # No pending assignments found

        # Configure session.exec side effects
        # We expect:
        # 1. select(BookingDB)... -> returns [mock_booking]
        # 2. select(AssignmentQueueDB)... -> returns None
        mock_session.exec.side_effect = [bookings_result, pending_result]

        # Patch the dependencies
        # Patch the dependencies
        with (
            patch("app.tasks.assignment_tasks.Session") as mock_session_cls,
            patch("app.tasks.assignment_tasks.engine"),
            patch(
                "app.tasks.assignment_tasks.process_new_booking"
            ) as mock_process_task,
            patch("app.tasks.assignment_tasks.logger"),
        ):
            # Configure Session context manager
            mock_session = mock_session_cls.return_value.__enter__.return_value
            mock_session.exec.side_effect = [bookings_result, pending_result]

            # Execute the function
            result = process_unassigned_bookings()

            # Verify results
            assert result["success"] is True
            assert result["triggered_count"] == 1

            # Verify process_new_booking.delay was called with the booking ID
            mock_process_task.delay.assert_called_once_with(str(mock_booking.id))

    def test_process_unassigned_bookings_skips_if_pending_exists(self):
        """
        Verify that we DO NOT trigger assignment if a pending assignment already exists.
        """
        # Mock session
        mock_session = MagicMock(spec=Session)

        # Mock booking
        mock_booking = MagicMock(spec=BookingDB)
        mock_booking.id = "booking-123"

        # First query finds booking
        bookings_result = MagicMock()
        bookings_result.all.return_value = [mock_booking]

        # Second query finds EXISTING pending assignment
        mock_assignment = MagicMock(spec=AssignmentQueueDB)
        pending_result = MagicMock()
        pending_result.first.return_value = mock_assignment

        mock_session.exec.side_effect = [bookings_result, pending_result]

        with (
            patch("app.tasks.assignment_tasks.Session") as mock_session_cls,
            patch("app.tasks.assignment_tasks.engine"),
            patch(
                "app.tasks.assignment_tasks.process_new_booking"
            ) as mock_process_task,
            patch("app.tasks.assignment_tasks.logger"),
        ):
            # Configure Session context manager
            mock_session = mock_session_cls.return_value.__enter__.return_value
            mock_session.exec.side_effect = [bookings_result, pending_result]

            # Execute
            result = process_unassigned_bookings()

            # Verify
            assert result["success"] is True
            assert result["triggered_count"] == 0

            # Should NOT have been called
            mock_process_task.delay.assert_not_called()
