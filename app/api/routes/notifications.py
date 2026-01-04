
from typing import Any
import uuid
import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select, Session

from app.api.deps import SessionDep, get_current_user
from app.models import User, UserDeviceDB, Message
from pydantic import BaseModel

router = APIRouter(prefix="/notifications", tags=["notifications"])

class DeviceTokenRequest(BaseModel):
    fcm_token: str
    platform: str = "web"

@router.post("/device", response_model=Message)
def register_device(
    request: DeviceTokenRequest,
    session: SessionDep,
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Register a device FCM token for push notifications.
    """
    # Check if token already exists
    statement = select(UserDeviceDB).where(UserDeviceDB.fcm_token == request.fcm_token)
    existing_device = session.exec(statement).first()
    
    if existing_device:
        # Update user association if changed
        if existing_device.user_id != current_user.id:
            existing_device.user_id = current_user.id
            
        existing_device.last_updated_at = datetime.datetime.utcnow()
        session.add(existing_device)
        session.commit()
        return Message(message="Device token updated")
        
    # Create new device record
    device = UserDeviceDB(
        user_id=current_user.id,
        fcm_token=request.fcm_token,
        platform=request.platform,
        last_updated_at=datetime.datetime.utcnow()
    )
    session.add(device)
    session.commit()
    
    return Message(message="Device registered successfully")
