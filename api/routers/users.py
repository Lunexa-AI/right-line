from fastapi import APIRouter, Depends, status, HTTPException
import structlog

from api.auth import User, get_current_user
from api.models import SignupRequest, SignupResponse
from libs.firebase.client import get_firestore_async_client
from libs.firestore.users import get_user_profile
from libs.models.firestore import FirestoreUser
from libs.firebase.auth_service import create_user_with_profile_email, create_user_with_profile_google, check_user_exists

router = APIRouter()
logger = structlog.get_logger(__name__)

@router.get(
    "/v1/users/me",
    response_model=FirestoreUser,
    tags=["Users"],
    summary="Get current user profile",
)
async def get_user_profile_endpoint(
    current_user: User = Depends(get_current_user),
) -> FirestoreUser:
    """
    Retrieve the current user's profile from Firestore.
    
    This endpoint is for authenticated users to get their profile information.
    If no profile exists, it means the user was created outside the normal signup flow.
    
    Returns:
        FirestoreUser: The user's profile information
        
    Raises:
        HTTPException: 404 if user profile not found
    """
    firestore_client = get_firestore_async_client()
    
    # Get user profile
    user_profile = await get_user_profile(firestore_client, current_user.uid)
    
    if not user_profile:
        logger.warning("Profile not found for authenticated user", uid=current_user.uid)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found. Please contact support."
        )
    
    return user_profile


@router.post(
    "/v1/signup",
    response_model=SignupResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Users"],
    summary="Sign up a new user",
)
async def signup_user(request: SignupRequest) -> SignupResponse:
    """
    Create a new user account with Firebase Auth and Firestore profile atomically.
    
    This endpoint supports both email/password and Google OAuth signup methods.
    
    The complete signup process:
    1. Validates the request data based on signup method
    2. For Google: Verifies Google token and extracts user info
    3. Checks if user already exists (by email)
    4. Creates Firebase Auth user (email/password or Google)
    5. Creates Firestore user profile
    6. Rolls back Firebase user if Firestore creation fails
    
    Args:
        request: SignupRequest with method-specific fields
        
    Returns:
        SignupResponse with success status and user details
        
    Raises:
        HTTPException: 
            - 400 if validation fails, user already exists, or invalid Google token
            - 500 if signup fails
            
    Examples:
        Email signup:
        ```bash
        curl -X POST http://localhost:8000/api/v1/signup \\
          -H "Content-Type: application/json" \\
          -d '{"method": "email", "name": "John Doe", "email": "john@example.com", "password": "securepass123"}'
        ```
        
        Google signup:
        ```bash
        curl -X POST http://localhost:8000/api/v1/signup \\
          -H "Content-Type: application/json" \\
          -d '{"method": "google", "name": "John Doe", "firebase_token": "firebase-id-token-here"}'
        ```
    """
    logger.info("Processing signup request", 
                method=request.method, email=request.email, name=request.name,
                request_data=request.model_dump())
    
    try:
        # For email signup, check if user exists by email
        # For Google signup, we'll extract email from token first
        if request.method == "email" and request.email:
            if check_user_exists(request.email):
                logger.warning("Signup attempt for existing user", email=request.email)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"User with email {request.email} already exists"
                )
        
        # Create user with profile atomically based on method
        if request.method == "email":
            if not request.email or not request.password:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email and password are required for email signup"
                )
                
            logger.info("Creating user with email method", email=request.email)
            try:
                firebase_uid, firestore_user = await create_user_with_profile_email(
                    name=request.name,
                    email=request.email,
                    password=request.password
                )
                logger.info("Email signup successful", 
                           firebase_uid=firebase_uid, 
                           firestore_uid=firestore_user.uid,
                           email=request.email)
                signup_email = request.email
            except Exception as e:
                logger.error("Email signup failed", 
                           email=request.email, 
                           error=str(e), 
                           error_type=type(e).__name__,
                           exc_info=True)
                raise
            
        elif request.method == "google":
            if not request.firebase_token:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Firebase token is required for Google signup"
                )
            
            # For Google signup, extract user info from Firebase token
            try:
                from firebase_admin import auth as firebase_auth
                decoded_token = firebase_auth.verify_id_token(request.firebase_token)
                
                firebase_uid = decoded_token.get('uid')
                google_email = decoded_token.get('email')
                
                if not firebase_uid or not google_email:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid Firebase token - missing UID or email"
                    )
                
                logger.info("Firebase token verified for Google signup", 
                           uid=firebase_uid, email=google_email)
                
                # Check if Firestore profile already exists (idempotent)
                firestore_client = get_firestore_async_client()
                existing_profile = await get_user_profile(firestore_client, firebase_uid)
                
                if existing_profile:
                    logger.info("Google user profile already exists", uid=firebase_uid)
                    signup_email = google_email
                    firebase_uid = firebase_uid
                else:
                    # Create Firestore profile for existing Firebase user
                    logger.info("Creating Firestore profile for Google user", 
                               uid=firebase_uid, email=google_email)
                    firebase_uid, firestore_user = await create_user_with_profile_google(
                        name=request.name,
                        firebase_uid=firebase_uid,
                        email=google_email
                    )
                    logger.info("Google user profile creation successful", 
                               firebase_uid=firebase_uid, 
                               firestore_uid=firestore_user.uid,
                               email=google_email)
                    signup_email = google_email
                
            except Exception as e:
                logger.error("Google signup processing failed", 
                           error=str(e), 
                           error_type=type(e).__name__,
                           exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Google signup failed: {str(e)}"
                )
            
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported signup method: {request.method}"
            )
        
        logger.info("User signup completed successfully", 
                   uid=firebase_uid, email=signup_email, method=request.method)
        
        return SignupResponse(
            success=True,
            message="User account created successfully",
            user_id=firebase_uid,
            email=signup_email
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions (like user already exists)
        raise
        
    except Exception as e:
        logger.error("Signup failed", email=request.email, error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user account. Please try again."
        )
