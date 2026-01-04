
import firebase_admin
from firebase_admin import credentials, messaging
from app.core.config import settings
from app.core.logging import logger
import os
import json

_firebase_app = None

def get_firebase_app():
    global _firebase_app
    if _firebase_app:
        return _firebase_app
        
    # Check if credentials path is set
    cred_path = settings.GOOGLE_APPLICATION_CREDENTIALS
    
    if cred_path and os.path.exists(cred_path):
        try:
            cred = credentials.Certificate(cred_path)
            _firebase_app = firebase_admin.initialize_app(cred)
            logger.info({"event_type": "firebase", "event_name": "initialized_from_file", "path": cred_path})
            return _firebase_app
        except Exception as e:
            logger.error({"event_type": "firebase", "event_name": "init_error", "source": "file", "error": str(e)})
        
    # Fallback: Check if credentials are properly set in ENV var as JSON string
    firebase_creds_json = settings.FIREBASE_CREDENTIALS_JSON
    if firebase_creds_json:
        try:
            cred_dict = json.loads(firebase_creds_json)
            cred = credentials.Certificate(cred_dict)
            _firebase_app = firebase_admin.initialize_app(cred)
            logger.info({"event_type": "firebase", "event_name": "initialized_from_json"})
            return _firebase_app
        except Exception as e:
            logger.error({"event_type": "firebase", "event_name": "init_error", "source": "json", "error": str(e)})
            
    logger.warning({"event_type": "firebase", "event_name": "not_initialized", "reason": "no_credentials"})
    return None

def send_push_notification(token: str, title: str, body: str, data: dict = None):
    """
    Send a push notification to a single device.
    """
    app = get_firebase_app()
    if not app:
        logger.error({
            "event_type": "notification",
            "event_name": "firebase_not_initialized",
            "message": "Cannot send push - Firebase not configured"
        })
        return False
        
    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=data or {},
            token=token,
        )
        response = messaging.send(message)
        logger.info({
            "event_type": "notification",
            "event_name": "fcm_send_success",
            "message_id": response
        })
        return True
    except messaging.UnregisteredError:
        logger.warning({
            "event_type": "notification",
            "event_name": "fcm_token_unregistered",
            "message": "FCM token is no longer valid - device may have uninstalled the app"
        })
        return False
    except messaging.SenderIdMismatchError:
        logger.error({
            "event_type": "notification",
            "event_name": "fcm_sender_mismatch",
            "message": "FCM token was created with a different Firebase project"
        })
        return False
    except Exception as e:
        logger.error({
            "event_type": "notification",
            "event_name": "fcm_send_error",
            "error_type": type(e).__name__,
            "error_message": str(e)
        })
        return False

