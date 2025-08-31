import unittest
from unittest.mock import patch, Mock

# Target for patching should be the absolute path to the module
# This ensures that the mocks are applied correctly
FIREBASE_CLIENT_PATH = 'libs.firebase.client'

class TestFirebase(unittest.TestCase):

    @patch(f'{FIREBASE_CLIENT_PATH}.firebase_admin.initialize_app')
    @patch(f'{FIREBASE_CLIENT_PATH}.firebase_admin.credentials.Certificate')
    @patch(f'{FIREBASE_CLIENT_PATH}.os.environ.get')
    def test_initialize_firebase_app_success(self, mock_getenv, mock_certificate, mock_initialize_app):
        # Arrange
        mock_getenv.return_value = '{}'
        
        # Act
        from libs.firebase.client import initialize_firebase_app
        initialize_firebase_app()

        # Assert
        mock_getenv.assert_called_once_with('FIREBASE_ADMIN_SDK_JSON')
        mock_certificate.assert_called_once_with({})
        mock_initialize_app.assert_called_once()

    @patch(f'{FIREBASE_CLIENT_PATH}.initialize_firebase_app')
    @patch(f'{FIREBASE_CLIENT_PATH}.firestore.client')
    def test_get_firestore_client(self, mock_firestore_client, mock_initialize_app):
        # Arrange
        from libs.firebase.client import get_firestore_client

        # Act
        client = get_firestore_client()

        # Assert
        mock_initialize_app.assert_called_once()
        mock_firestore_client.assert_called_once()
        self.assertIsNotNone(client)

if __name__ == '__main__':
    unittest.main()
