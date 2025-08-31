import os
import json
import firebase_admin
from firebase_admin import credentials, firestore

def initialize_firebase_app():
    """
    Initializes the Firebase Admin SDK.
    """
    sdk_json = os.environ.get('FIREBASE_ADMIN_SDK_JSON')
    if not sdk_json:
        raise ValueError("FIREBASE_ADMIN_SDK_JSON environment variable not set.")

    cred_json = json.loads(sdk_json)
    cred = credentials.Certificate(cred_json)
    
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)

def get_firestore_client():
    """
    Returns a Firestore client.
    """
    if not firebase_admin._apps:
        initialize_firebase_app()
    return firestore.client()
