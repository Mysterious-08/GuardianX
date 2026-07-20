from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.database.session import DBSessionDep
from app.schemas.auth import Token, UserCreate, UserLogin, UserResponse
from app.services.auth_service import (
    AuthenticationError,
    AuthService,
    InvalidCredentialsError,
    UserAlreadyExistsError,
)
from app.services.user_service import UserService

router = APIRouter(prefix="/auth", tags=["auth"])


def get_auth_service(db: DBSessionDep) -> AuthService:
    """Construct the auth service from the injected database session."""
    return AuthService(user_service=UserService(db=db))


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Create a new GuardianX user account.",
)
def register(
    user_data: UserCreate,
    auth_service: AuthService = Depends(get_auth_service),
) -> UserResponse:
    """Register a new GuardianX account."""
    try:
        return auth_service.register_user(user_data)
    except UserAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post(
    "/login",
    response_model=Token,
    status_code=status.HTTP_200_OK,
    summary="Authenticate user",
    description="Authenticate using a username or email and return a JWT access token.",
)
def login(
    user_data: UserLogin,
    auth_service: AuthService = Depends(get_auth_service),
) -> Token:
    """Authenticate a user and return a bearer token."""
    try:
        user = auth_service.authenticate_user(
            identifier=user_data.identifier,
            password=user_data.password,
        )
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    return auth_service.create_access_token_for_user(user)
