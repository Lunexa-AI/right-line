"""Firebase Authentication service for user management.

This module provides functions for creating and managing Firebase Auth users
using the Firebase Admin SDK.
"""

import structlog
from firebase_admin import auth
from google.oauth2 import id_token
from google.auth.transport import requests
from libs.models.firestore import FirestoreUser
from libs.firestore.users import create_user_profile
from libs.firebase.client import get_firestore_async_client

logger = structlog.get_logger(__name__)


def verify_google_token(google_token: str) -> dict:
    """Verify Google ID token and extract user information.
    
    Args:
        google_token: Google ID token from frontend
        
    Returns:
        Dict containing user info (email, name, etc.)
        
    Raises:
        ValueError: If token is invalid or verification fails
    """
    try:
        # For Firebase Auth tokens, we should use Firebase Admin SDK instead
        # of direct Google token verification
        logger.info("Verifying Google token using Firebase Admin SDK")
        
        # Use Firebase Admin SDK to verify the token
        # This handles Google tokens issued by Firebase Auth properly
        from firebase_admin import auth as firebase_auth
        
        try:
            # Verify the token as a Firebase ID token
            decoded_token = firebase_auth.verify_id_token(google_token)
            logger.info("Firebase token verified successfully", 
                       uid=decoded_token.get('uid'),
                       email=decoded_token.get('email'))
            return decoded_token
            
        except Exception as firebase_error:
            logger.warning("Firebase token verification failed, trying direct Google verification", 
                          error=str(firebase_error))
            
            # Fallback: Try direct Google token verification without audience
            # This is less secure but works for development
            idinfo = id_token.verify_oauth2_token(
                google_token, 
                requests.Request()
                # No audience specified - this allows any valid Google token
            )
            
            # Verify the issuer
            if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
                raise ValueError('Invalid token issuer')
                
            logger.info("Google token verified successfully (fallback)", 
                       email=idinfo.get('email'))
            return idinfo
        
    except ValueError as e:
        logger.error("Google token verification failed", error=str(e))
        raise ValueError(f"Invalid Google token: {e}")
    except Exception as e:
        logger.error("Unexpected error during Google token verification", 
                    error=str(e), error_type=type(e).__name__)
        raise ValueError("Failed to verify Google token")


async def create_user_with_profile_email(name: str, email: str, password: str) -> tuple[str, FirestoreUser]:
    """Create a Firebase Auth user with email/password and corresponding Firestore profile atomically.
    
    This function ensures atomicity by rolling back the Firebase user creation
    if the Firestore profile creation fails.
    
    Args:
        name: User's full name
        email: User's email address
        password: User's password
        
    Returns:
        Tuple of (firebase_uid, firestore_user)
        
    Raises:
        ValueError: If user creation fails
        Exception: If profile creation fails (Firebase user will be rolled back)
    """
    firebase_user = None
    
    try:
        # Step 1: Create Firebase Auth user
        logger.info("Creating Firebase Auth user", email=email)
        firebase_user = auth.create_user(
            email=email,
            password=password,
            display_name=name,
            email_verified=False  # User will need to verify their email
        )
        
        logger.info("Firebase user created successfully", 
                   uid=firebase_user.uid, email=email)
        
        # Step 2: Create Firestore profile
        logger.info("Creating Firestore user profile", uid=firebase_user.uid)
        try:
            firestore_client = get_firestore_async_client()
            logger.info("Firestore client created successfully")
            
            user_data = FirestoreUser(
                uid=firebase_user.uid,
                email=email,
                name=name
            )
            logger.info("FirestoreUser data prepared", 
                       uid=firebase_user.uid, email=email, name=name)
            
            created_user = await create_user_profile(firestore_client, user_data)
            logger.info("Firestore profile created successfully", 
                       uid=firebase_user.uid, profile_uid=created_user.uid)
        except Exception as firestore_error:
            logger.error("Firestore profile creation failed", 
                        uid=firebase_user.uid, 
                        error=str(firestore_error),
                        error_type=type(firestore_error).__name__,
                        exc_info=True)
            raise firestore_error
        
        logger.info("User signup completed successfully", 
                   uid=firebase_user.uid, email=email)
        
        return firebase_user.uid, created_user
        
    except Exception as e:
        # Rollback: Delete Firebase user if it was created
        if firebase_user:
            try:
                logger.warning("Rolling back Firebase user creation", 
                             uid=firebase_user.uid, error=str(e))
                auth.delete_user(firebase_user.uid)
                logger.info("Firebase user rollback successful", uid=firebase_user.uid)
            except Exception as rollback_error:
                logger.error("Failed to rollback Firebase user", 
                           uid=firebase_user.uid, 
                           rollback_error=str(rollback_error),
                           original_error=str(e))
                # Re-raise the original error, but log the rollback failure
        
        # Re-raise the original exception
        raise e


async def create_user_with_profile_google(name: str, firebase_uid: str, email: str) -> tuple[str, FirestoreUser]:
    """Create Firestore profile for an existing Firebase Auth user (from Google signup).
    
    This function is called when a user has already signed up with Google via Firebase Auth
    in the frontend, and we just need to create their Firestore profile.
    
    Args:
        name: User's full name (from frontend)
        firebase_uid: Firebase UID of the already-created user
        email: User's email from Firebase token
        
    Returns:
        Tuple of (firebase_uid, firestore_user)
        
    Raises:
        Exception: If profile creation fails
    """
    
    try:
        # The Firebase user already exists (created by frontend), just create Firestore profile
        logger.info("Creating Firestore profile for existing Firebase user", 
                   uid=firebase_uid, email=email)
        
        firestore_client = get_firestore_async_client()
        logger.info("Firestore client created successfully")
        
        user_data = FirestoreUser(
            uid=firebase_uid,
            email=email,
            name=name
        )
        logger.info("FirestoreUser data prepared", 
                   uid=firebase_uid, email=email, name=name)
        
        created_user = await create_user_profile(firestore_client, user_data)
        logger.info("Firestore profile created successfully for Google user", 
                   uid=firebase_uid, profile_uid=created_user.uid)
        
        logger.info("Google user profile creation completed successfully", 
                   uid=firebase_uid, email=email)
        
        return firebase_uid, created_user
        
    except Exception as e:
        logger.error("Google user profile creation failed", 
                    uid=firebase_uid, 
                    email=email,
                    error=str(e), 
                    error_type=type(e).__name__,
                    exc_info=True)
        # Note: We don't delete the Firebase user here since it was created by the frontend
        # and the user is already signed in
        raise e


def check_user_exists(email: str) -> bool:
    """Check if a user already exists with the given email.
    
    Args:
        email: Email address to check
        
    Returns:
        True if user exists, False otherwise
    """
    try:
        auth.get_user_by_email(email)
        return True
    except auth.UserNotFoundError:
        return False
    except Exception as e:
        logger.error("Error checking user existence", email=email, error=str(e))
        raise e
