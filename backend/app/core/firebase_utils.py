
import firebase_admin
from firebase_admin import credentials, messaging
from app.core.config import settings
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
        cred = credentials.Certificate(cred_path)
        _firebase_app = firebase_admin.initialize_app(cred)
        return _firebase_app
        
    # Fallback: Check if credentials are properly set in ENV var as JSON string
    firebase_creds_json = settings.FIREBASE_CREDENTIALS_JSON
    if firebase_creds_json:
        try:
            cred_dict = json.loads(firebase_creds_json)
            cred = credentials.Certificate(cred_dict)
            _firebase_app = firebase_admin.initialize_app(cred)
            return _firebase_app
        except Exception as e:
            print(f"Error loading Firebase creds from JSON: {e}")
            
    return None

def send_push_notification(token: str, title: str, body: str, data: dict = None):
    """
    Send a push notification to a single device.
    """
    app = get_firebase_app()
    if not app:
        print("Firebase app not initialized. Skipping notification.")
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
        return True
    except Exception as e:
        print(f"Error sending push notification: {e}")
        return False
