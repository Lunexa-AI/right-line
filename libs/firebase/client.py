import os
import json
import firebase_admin
from firebase_admin import credentials
from google.cloud.firestore_v1.async_client import AsyncClient

from libs.common.settings import Settings, get_settings


def initialize_firebase_app():
    """
    Initializes the Firebase Admin SDK using settings from Pydantic.
    This is the robust way to ensure credentials are loaded correctly.
    """
    if firebase_admin._apps:
        return

    settings = get_settings()
    sdk_json_content = settings.firebase_admin_sdk_json
    sdk_json_path = settings.firebase_admin_sdk_path

    cred = None
    if sdk_json_content:
        try:
            cred_json = json.loads(sdk_json_content)
            cred = credentials.Certificate(cred_json)
        except json.JSONDecodeError:
            print("Error: FIREBASE_ADMIN_SDK_JSON in settings is not valid JSON.")
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
        print("Warning: No Firebase credentials found in settings. Assuming emulator or mock environment.")
        # Attempt to initialize without credentials for emulators
        try:
            firebase_admin.initialize_app()
        except ValueError:
            # Already initialized, which is fine
            pass
        return


def get_firestore_async_client() -> AsyncClient:
    """
    Returns an asynchronous Firestore client.
    
    It relies on initialize_firebase_app() having been called to set up
    the necessary authentication context.
    """
    initialize_firebase_app()
    # Explicitly pass the project ID to the client
    project_id = "gweta-context-state"
    return AsyncClient(project=project_id, database="gweta-context")
