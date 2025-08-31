from fastapi import APIRouter, Depends, status, Response
from pydantic import BaseModel

from api.auth import User, get_current_user
from libs.firebase.client import get_firestore_async_client
from libs.firestore.users import get_user_profile, create_user_profile
from libs.models.firestore import FirestoreUser

router = APIRouter()

class CreateUserRequest(BaseModel):
    name: str

@router.post(
    "/v1/users/me",
    response_model=FirestoreUser,
    # The default status code is now 200
    status_code=status.HTTP_200_OK,
    tags=["Users"],
    summary="Create or retrieve user profile",
)
async def create_user_me(
    request: CreateUserRequest,
    response: Response, # Inject the Response object
    current_user: User = Depends(get_current_user),
):
    """
    Creates a user profile if one does not exist for the authenticated user.
    If a profile already exists, it returns the existing profile (idempotent).
    """
    firestore_client = get_firestore_async_client()
    
    # Check if user profile already exists
    existing_profile = await get_user_profile(firestore_client, current_user.uid)
    if existing_profile:
        return existing_profile

    # Create new profile
    new_user_data = FirestoreUser(
        uid=current_user.uid,
        email=current_user.email,
        name=request.name
    )
    created_user = await create_user_profile(firestore_client, new_user_data)
    
    # Set the status code to 201 Created for the new resource
    response.status_code = status.HTTP_201_CREATED
    return created_user
