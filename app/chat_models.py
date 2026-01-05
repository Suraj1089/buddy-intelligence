import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel

from app.models import User

class ChatSessionBase(SQLModel):
    user_id: uuid.UUID = Field(foreign_key="user.id")
    status: str = Field(default="active")  # active, closed
    assigned_admin_id: uuid.UUID | None = Field(default=None, foreign_key="user.id", nullable=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ChatSession(ChatSessionBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    
    user: User = Relationship(sa_relationship_kwargs={"primaryjoin": "ChatSession.user_id==User.id", "lazy": "joined"})
    # We can add admin relationship if needed, but might be circular if not careful.
    messages: list["ChatMessage"] = Relationship(back_populates="session", sa_relationship_kwargs={"lazy": "selectin"})

class ChatSessionPublic(ChatSessionBase):
    id: uuid.UUID
    user_email: str | None = None
    user_name: str | None = None
    last_message: str | None = None

class ChatMessageBase(SQLModel):
    session_id: uuid.UUID = Field(foreign_key="chatsession.id")
    sender_type: str  # "user", "admin", "system"
    sender_id: uuid.UUID | None = None  # user_id or admin_id
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ChatMessage(ChatMessageBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    
    session: ChatSession = Relationship(back_populates="messages")

class ChatMessageCreate(ChatMessageBase):
    pass

class ChatMessagePublic(ChatMessageBase):
    id: uuid.UUID
