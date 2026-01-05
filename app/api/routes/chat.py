import uuid
from typing import Any, List

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Query
from sqlmodel import Session, select, col

from app.api.deps import get_current_user, get_current_active_superuser, SessionDep
from app.chat_manager import manager
from app.chat_models import ChatMessage, ChatSession, ChatSessionPublic, ChatMessagePublic
from app.models import User

router = APIRouter()

# --- HTTP Endpoints ---

@router.get("/sessions", response_model=List[ChatSessionPublic], dependencies=[Depends(get_current_active_superuser)])
def get_chat_sessions(session: SessionDep) -> Any:
    """
    Get all chat sessions for admin.
    """
    # Join with User to get details
    statement = select(ChatSession, User).join(User, ChatSession.user_id == User.id).order_by(col(ChatSession.updated_at).desc())
    results = session.exec(statement).all()
    
    sessions_public = []
    for chat_session, user in results:
        # Get last message
        last_msg = session.exec(select(ChatMessage).where(ChatMessage.session_id == chat_session.id).order_by(col(ChatMessage.created_at).desc()).limit(1)).first()
        
        sessions_public.append(ChatSessionPublic(
            **chat_session.model_dump(),
            user_email=user.email,
            user_name=user.full_name,
            last_message=last_msg.content if last_msg else None
        ))
    
    return sessions_public

@router.get("/sessions/{session_id}/messages", response_model=List[ChatMessagePublic])
def get_session_messages(session_id: uuid.UUID, session: SessionDep, current_user: User = Depends(get_current_user)) -> Any:
    """
    Get messages for a specific session.
    Users can only access their own sessions. Admins can access any.
    """
    chat_session = session.get(ChatSession, session_id)
    if not chat_session:
        # Or return 404
        return []

    if not current_user.is_superuser and chat_session.user_id != current_user.id:
        return []

    messages = session.exec(select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at)).all()
    return messages

@router.post("/sessions/{session_id}/assign", dependencies=[Depends(get_current_active_superuser)])
async def assign_session(session_id: uuid.UUID, session: SessionDep, current_user: User = Depends(get_current_active_superuser)) -> Any:
    """
    Assign a session to the current admin.
    """
    chat_session = session.get(ChatSession, session_id)
    if chat_session:
        chat_session.assigned_admin_id = current_user.id
        session.add(chat_session)
        session.commit()
        session.refresh(chat_session)
        
        # Notify admins that session is updated
        # In a real app we might broadcast this event
        
        # Notify USER that admin has joined
        try:
            await manager.send_to_user(chat_session.user_id, {
                "type": "status",
                "assigned": True
            })
        except Exception:
            # User might be disconnected, ignore
            pass
        
    return chat_session

@router.post("/sessions/{session_id}/close", dependencies=[Depends(get_current_user)])
async def close_session(session_id: uuid.UUID, session: SessionDep, current_user: User = Depends(get_current_user)) -> Any:
    """
    Close a chat session. User or Admin can close.
    """
    chat_session = session.get(ChatSession, session_id)
    if not chat_session:
        # 404
        return {"error": "Session not found"}
        
    # Permission check: User owns it OR Admin
    if not current_user.is_superuser and chat_session.user_id != current_user.id:
        # 403
        return {"error": "Not authorized"}
        
    chat_session.status = "closed"
    session.add(chat_session)
    session.commit()
    
    # Notify User & Admin via WS
    
    # Notify User
    try:
        await manager.send_to_user(chat_session.user_id, {
            "type": "status",
            "status": "closed",
            "assigned": False
        })
    except Exception:
        pass
    
    # Notify Admins (Broadcast update)
    try:
        await manager.broadcast_to_admins({
            "type": "session_closed",
            "session_id": str(chat_session.id)
        })
    except Exception:
        pass
    
    return {"message": "Session closed"}

# --- WebSocket Endpoints ---

@router.websocket("/ws/user")
async def websocket_endpoint_user(
    websocket: WebSocket,
    token: str = Query(...),
):
    # Retrieve user from token (Manual verification or dependency trick)
    # For simplicity, we assume we can get user.
    # NOTE: Parsing token in WS is tricky. We'll simplify and valid via a separate function if needed
    # Or rely on a custom dependency.
    pass 
    # **Wait, SessionDep and conventional Depends don't work well with @websocket** specifically if they rely on request state.
    # We will implement a simpler token check or trust for now, REVISIT security.
    
    # We need a way to get the session inside WS.
    # Let's import the engine/sessionmaker directly or use a localized helper
    from app.core.db import engine
    
    conn_user_id = None
    
    # Verify token Logic (Simplified placeholder)
    # from app.api.deps import verify_token...
    # For now assume we pass user_id for dev speed if token parsing is complex without `request`.
    # Actually, we can just use `token` and decode it.
    
    import jwt
    from pydantic import ValidationError
    from app.core.config import settings
    from app.core import security
    from app.models import TokenPayload
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[security.ALGORITHM])
        token_data = TokenPayload(**payload)
        conn_user_id = uuid.UUID(token_data.sub)
    except (ValidationError, Exception):
        await websocket.close(code=1008)
        return

    await manager.connect_user(conn_user_id, websocket)

    try:
        with Session(engine) as db_session:
            # Check for existing active session
            chat_session = db_session.exec(select(ChatSession).where(ChatSession.user_id == conn_user_id, ChatSession.status == "active")).first()
            
            if not chat_session:
                chat_session = ChatSession(user_id=conn_user_id)
                db_session.add(chat_session)
                db_session.commit()
                db_session.refresh(chat_session)
                
                # Broadcast new session to admins
                await manager.broadcast_to_admins({
                    "type": "new_session", 
                    "session_id": str(chat_session.id),
                    "user_id": str(conn_user_id)
                })

            current_session_id = chat_session.id
            
            # Send initial status
            await websocket.send_json({
                "type": "status",
                "assigned": chat_session.assigned_admin_id is not None,
                "session_id": str(chat_session.id)
            })
            
            # Fetch and send history
            history_msgs = db_session.exec(
                select(ChatMessage)
                .where(ChatMessage.session_id == chat_session.id)
                .order_by(ChatMessage.created_at)
            ).all()
            
            if history_msgs:
                await websocket.send_json({
                    "type": "history",
                    "messages": [
                        {
                            "role": "assistant" if msg.sender_type == "admin" else "user",
                            "content": msg.content
                        } for msg in history_msgs
                    ]
                })

        while True:
            data = await websocket.receive_text()
            # User sent a message
            # Save to DB
            with Session(engine) as db_session:
                # Re-fetch session to check status
                chat_session = db_session.get(ChatSession, current_session_id)
                
                # Check if session is closed, if so, start a NEW one
                if not chat_session or chat_session.status != "active":
                    chat_session = ChatSession(user_id=conn_user_id)
                    db_session.add(chat_session)
                    db_session.commit()
                    db_session.refresh(chat_session)
                    
                    current_session_id = chat_session.id
                    
                    # Notify Admins of NEW session
                    import asyncio
                    try:
                        await manager.broadcast_to_admins({
                            "type": "new_session", 
                            "session_id": str(chat_session.id),
                            "user_id": str(conn_user_id)
                        })
                    except: pass
                    
                    # Notify User of NEW session ID (silent update or status)
                    try:
                        await websocket.send_json({
                            "type": "status",
                            "assigned": False,
                            "session_id": str(chat_session.id)
                        })
                    except: pass

                msg = ChatMessage(
                    session_id=current_session_id,
                    sender_type="user",
                    sender_id=conn_user_id,
                    content=data
                )
                db_session.add(msg)
                
                # Update timestamp on session
                chat_session.updated_at = msg.created_at
                db_session.add(chat_session)
                
                db_session.commit()
                
                # If assigned to admin, send to admin
                if chat_session.assigned_admin_id and chat_session.assigned_admin_id in manager.active_admin_connections:
                     admin_ws = manager.active_admin_connections[chat_session.assigned_admin_id]
                     await admin_ws.send_json({
                        "type": "message",
                        "session_id": str(chat_session.id),
                        "content": data,
                        "sender": "user"
                     })
                else:
                    # Broadcast to ALL admins that there is a new message in unassigned chat
                    await manager.broadcast_to_admins({
                        "type": "message",
                        "session_id": str(chat_session.id),
                        "content": data,
                        "sender": "user",
                        "unassigned": chat_session.assigned_admin_id is None
                    })
                    
    except WebSocketDisconnect:
        manager.disconnect_user(conn_user_id, websocket)


@router.websocket("/ws/admin")
async def websocket_endpoint_admin(
    websocket: WebSocket,
    token: str = Query(...)
):
    from app.core.db import engine
    import jwt
    from app.core.config import settings
    from app.core import security
    from app.models import TokenPayload
    
    conn_admin_id = None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[security.ALGORITHM])
        token_data = TokenPayload(**payload)
        conn_admin_id = uuid.UUID(token_data.sub)
        
        # Verify is superuser?
        with Session(engine) as db:
            u = db.get(User, conn_admin_id)
            if not u or not u.is_superuser:
                await websocket.close(code=1008)
                return
                
    except Exception:
        await websocket.close(code=1008)
        return

    await manager.connect_admin(conn_admin_id, websocket)
    
    try:
        while True:
            data = await websocket.receive_json()
            # Admin sent data: { session_id: "...", content: "..." }
            
            target_session_id = data.get("session_id")
            content = data.get("content")
            
            if target_session_id and content:
                with Session(engine) as db_session:
                    chat_session = db_session.get(ChatSession, uuid.UUID(target_session_id))
                    if chat_session:
                        # STRICT: Only allow reply if assigned to THIS admin
                        if chat_session.assigned_admin_id != conn_admin_id:
                             # Send error back to admin? Or just ignore?
                             # Let's ignore for now or log
                             continue

                        msg = ChatMessage(
                            session_id=chat_session.id,
                            sender_type="admin",
                            sender_id=conn_admin_id,
                            content=content
                        )
                        db_session.add(msg)
                        db_session.commit()
                        
                        # Send to user
                        await manager.send_to_user(chat_session.user_id, {
                            "role": "assistant", # Frontend expects role
                            "content": content
                        })

    except WebSocketDisconnect:
        manager.disconnect_admin(conn_admin_id)


@router.post("/internal/broadcast")
async def broadcast_message(message: dict) -> Any:
    """
    Internal endpoint to broadcast messages to users/admins via WebSocket.
    """
    msg_type = message.get("type")
    
    if msg_type == "new_assignment":
        # Target specific provider (User)
        provider_user_id = message.get("user_id")
        if provider_user_id:
            try:
                # The connection manager keys are user_ids (UUIDs)
                await manager.send_to_user(uuid.UUID(provider_user_id), message)
            except Exception:
                pass 
                
    elif msg_type == "session_update":
        # Broadcast to admins
        pass
        
    return {"success": True}
