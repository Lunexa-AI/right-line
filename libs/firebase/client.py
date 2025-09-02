import os
import json
import firebase_admin
from firebase_admin import credentials
from google.cloud.firestore_v1.async_client import AsyncClient

def initialize_firebase_app():
    """
    Initializes the Firebase Admin SDK if not already initialized.
    This sets up the application default credentials for other Google Cloud libraries.
    """
    if firebase_admin._apps:
        return

    sdk_json_content = os.environ.get('FIREBASE_ADMIN_SDK_JSON')
    sdk_json_path = os.environ.get('FIREBASE_ADMIN_SDK_PATH')

    cred = None
    if sdk_json_content:
        try:
            cred_json = json.loads(sdk_json_content)
            cred = credentials.Certificate(cred_json)
        except json.JSONDecodeError:
            print("Error: FIREBASE_ADMIN_SDK_JSON is not valid JSON.")
            return
    elif sdk_json_path:
        try:
            cred = credentials.Certificate(sdk_json_path)
        except FileNotFoundError:
            print(f"Error: Firebase credentials file not found at {sdk_json_path}")
            return
    
    if cred:
        firebase_admin.initialize_app(cred)
    else:
        print("Warning: Neither FIREBASE_ADMIN_SDK_JSON nor FIREBASE_ADMIN_SDK_PATH are set. Assuming emulator or mock environment.")
        try:
            firebase_admin.initialize_app()
        except ValueError:
            pass
        return

def get_firestore_async_client() -> AsyncClient:
    """
    Returns an asynchronous Firestore client.
    
    It relies on initialize_firebase_app() having been called to set up
    the necessary authentication context.
    """
    initialize_firebase_app()
    return AsyncClient()
