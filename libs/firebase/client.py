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

    sdk_json = os.environ.get('FIREBASE_ADMIN_SDK_JSON')
    if not sdk_json:
        # In a test or local environment, we might not have this set.
        # The emulators or mocks will handle functionality.
        print("Warning: FIREBASE_ADMIN_SDK_JSON not set. Assuming emulator or mock environment.")
        # Attempt to initialize without explicit credentials, relying on ADC.
        try:
            firebase_admin.initialize_app()
        except ValueError:
            # This will happen if no app is initialized and no credentials can be found.
            # It's okay in a testing context where services are mocked.
            pass
        return

    cred_json = json.loads(sdk_json)
    cred = credentials.Certificate(cred_json)
    firebase_admin.initialize_app(cred)

def get_firestore_async_client() -> AsyncClient:
    """
    Returns an asynchronous Firestore client.
    
    It relies on initialize_firebase_app() having been called to set up
    the necessary authentication context.
    """
    initialize_firebase_app()
    return AsyncClient()
