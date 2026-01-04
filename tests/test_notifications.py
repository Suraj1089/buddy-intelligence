
import uuid
from unittest.mock import MagicMock, patch
from sqlmodel import Session, select
from app.api.routes.notifications import register_device, DeviceTokenRequest
from app.models import UserDeviceDB, User
from app.core.firebase_utils import send_push_notification

def test_device_registration_new_token(session: Session):
    # Mock user
    user_id = uuid.uuid4()
    user = User(id=user_id, email=f"test_{uuid.uuid4()}@example.com", full_name="Test User", hashed_password="pw", is_active=True, is_superuser=False)
    session.add(user) # ensure user exists for FK
    session.commit()
    
    request = DeviceTokenRequest(fcm_token="new-token-123", platform="web")
    
    # Call endpoint
    response = register_device(request, session, user)
    
    assert response.message == "Device registered successfully"
    
    # Verify DB
    device = session.exec(select(UserDeviceDB)).first()
    assert device.fcm_token == "new-token-123"
    assert device.user_id == user.id

def test_device_registration_update_existing(session: Session):
    # Setup existing device
    uid1 = uuid.uuid4()
    uid2 = uuid.uuid4()
    user1 = User(id=uid1, email=f"user1_{uuid.uuid4()}@example.com", full_name="U1", hashed_password="pw")
    user2 = User(id=uid2, email=f"user2_{uuid.uuid4()}@example.com", full_name="U2", hashed_password="pw")
    session.add(user1)
    session.add(user2)
    session.commit()
    
    device = UserDeviceDB(user_id=user1.id, fcm_token="existing-token", platform="android")
    session.add(device)
    session.commit()
    
    # User 2 logs in on same device
    request = DeviceTokenRequest(fcm_token="existing-token", platform="web")
    response = register_device(request, session, user2)
    
    assert response.message == "Device token updated"
    
    # Verify DB updated ownership
    updated_device = session.exec(select(UserDeviceDB)).first()
    assert updated_device.user_id == user2.id
    assert updated_device.platform == "android" # Should preserve platform unless updated? Logic says no update on platform currently

@patch("app.core.firebase_utils.get_firebase_app")
@patch("firebase_admin.messaging.send")
def test_send_push_notification(mock_send, mock_get_app):
    mock_get_app.return_value = MagicMock()
    
    token = "test-token"
    title = "Hello"
    body = "World"
    
    result = send_push_notification(token, title, body)
    
    assert result is True
    mock_send.assert_called_once()
    
    # Verify payload
    call_args = mock_send.call_args[0][0] # First arg of first call
    assert call_args.token == token
    assert call_args.notification.title == title
    assert call_args.notification.body == body

@patch("app.core.firebase_utils.get_firebase_app")
def test_send_push_notification_no_app(mock_get_app):
    mock_get_app.return_value = None
    
    result = send_push_notification("token", "title", "body")
    assert result is False
