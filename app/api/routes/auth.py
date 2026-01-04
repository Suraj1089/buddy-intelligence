"""
Authentication routes - register, login, logout, token refresh.
Replaces Supabase Auth with FastAPI-native authentication.
"""
import uuid
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlmodel import Session, select

from app import crud
from app.booking_models import ProfileDB
from app.core import security
from app.core.config import settings
from app.core.db import get_session
from app.models import User, UserCreate

router = APIRouter(prefix="/auth", tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")


# ============== Schemas ==============

class RegisterRequest(BaseModel):
    """User registration request."""
    email: EmailStr
    password: str
    full_name: str
    phone: str | None = None
    address: str | None = None


class LoginRequest(BaseModel):
    """Login request."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict


class UserResponse(BaseModel):
    """User response."""
    id: str
    email: str
    full_name: str | None = None
    phone: str | None = None
    is_active: bool
    is_provider: bool = False
    is_superuser: bool = False


class MessageResponse(BaseModel):
    """Generic message response."""
    message: str


# ============== Helper Functions ==============

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session)
) -> User:
    """Get current user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = security.decode_token(token)
        if payload is None:
            raise credentials_exception

        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except Exception:
        raise credentials_exception

    user = session.exec(select(User).where(User.id == uuid.UUID(user_id))).first()

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    return user


def get_profile(session: Session, user_id: uuid.UUID) -> ProfileDB | None:
    """Get user profile."""
    return session.exec(
        select(ProfileDB).where(ProfileDB.user_id == user_id)
    ).first()


def is_provider(session: Session, user_id: uuid.UUID) -> bool:
    """Check if user is a provider."""
    from app.booking_models import ProviderDB
    provider = session.exec(
        select(ProviderDB).where(ProviderDB.user_id == user_id)
    ).first()
    return provider is not None


# ============== Routes ==============

@router.post("/register", response_model=TokenResponse)
def register(
    request: RegisterRequest,
    session: Session = Depends(get_session)
) -> Any:
    """
    Register a new user.
    Creates user account and profile.
    """
    # Check if user already exists
    existing_user = crud.get_user_by_email(session=session, email=request.email)
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="A user with this email already exists."
        )

    # Create user
    user_create = UserCreate(
        email=request.email,
        password=request.password,
        full_name=request.full_name,
    )
    user = crud.create_user(session=session, user_create=user_create)

    # Create profile
    profile = ProfileDB(
        id=uuid.uuid4(),
        user_id=user.id,
        full_name=request.full_name,
        phone=request.phone,
    )
    session.add(profile)
    session.commit()

    # Generate token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        user.id, expires_delta=access_token_expires
    )

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user={
            "id": str(user.id),
            "email": user.email,
            "full_name": request.full_name,
            "is_provider": False,
            "is_superuser": user.is_superuser,
        }
    )


@router.post("/login", response_model=TokenResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session)
) -> Any:
    """
    Login with email and password.
    Returns JWT access token.
    """
    user = crud.authenticate(
        session=session,
        email=form_data.username,
        password=form_data.password
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    # Get profile and provider status
    profile = get_profile(session, user.id)
    provider_status = is_provider(session, user.id)

    # Generate token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        user.id, expires_delta=access_token_expires
    )

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user={
            "id": str(user.id),
            "email": user.email,
            "full_name": profile.full_name if profile else None,
            "is_provider": provider_status,
            "is_superuser": user.is_superuser,
        }
    )


@router.post("/login/json", response_model=TokenResponse)
def login_json(
    request: LoginRequest,
    session: Session = Depends(get_session)
) -> Any:
    """
    Login with JSON body (alternative to form-based login).
    """
    user = crud.authenticate(
        session=session,
        email=request.email,
        password=request.password
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    # Get profile and provider status
    profile = get_profile(session, user.id)
    provider_status = is_provider(session, user.id)

    # Generate token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        user.id, expires_delta=access_token_expires
    )

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user={
            "id": str(user.id),
            "email": user.email,
            "full_name": profile.full_name if profile else None,
            "is_provider": provider_status,
            "is_superuser": user.is_superuser,
        }
    )


@router.get("/me", response_model=UserResponse)
def get_me(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
) -> Any:
    """
    Get current user information.
    """
    profile = get_profile(session, current_user.id)
    provider_status = is_provider(session, current_user.id)

    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        full_name=profile.full_name if profile else None,
        phone=profile.phone if profile else None,
        is_active=current_user.is_active,
        is_provider=provider_status,
        is_superuser=current_user.is_superuser,
    )


@router.post("/logout", response_model=MessageResponse)
def logout() -> Any:
    """
    Logout user.
    Note: JWT tokens are stateless, so logout is handled client-side
    by removing the token. This endpoint is for API consistency.
    """
    return MessageResponse(message="Successfully logged out")


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
) -> Any:
    """
    Refresh access token.
    Requires valid current token.
    """
    profile = get_profile(session, current_user.id)
    provider_status = is_provider(session, current_user.id)

    # Generate new token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        current_user.id, expires_delta=access_token_expires
    )

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user={
            "id": str(current_user.id),
            "email": current_user.email,
            "full_name": profile.full_name if profile else None,
            "is_provider": provider_status,
            "is_superuser": current_user.is_superuser,
        }
    )
