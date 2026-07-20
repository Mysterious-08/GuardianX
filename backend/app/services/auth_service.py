from __future__ import annotations

from app.models.user import User
from app.schemas.auth import Token, UserCreate, UserResponse
from app.security.hashing import verify_password
from app.security.jwt import create_access_token
from app.services.user_service import UserService


class AuthenticationError(Exception):
    """Base exception for authentication-related business rule failures."""


class InvalidCredentialsError(AuthenticationError):
    """Raised when supplied credentials are invalid or do not match a user record."""


class UserAlreadyExistsError(AuthenticationError):
    """Raised when registration attempts target a username or email that already exists."""


class AuthService:
    """Framework-independent authentication orchestration service.

    This class coordinates persistence and credential verification without
    depending on FastAPI, SQLAlchemy session creation, or route handlers.
    """

    def __init__(self, user_service: UserService) -> None:
        """Initialize the auth service with a persistence service dependency."""
        self.user_service = user_service

    def register_user(self, user_data: UserCreate) -> UserResponse:
        """Register a new user and return the public user representation.

        Args:
            user_data: Pydantic payload containing the username, email, and password.

        Returns:
            A safe public user payload.

        Raises:
            UserAlreadyExistsError: If the username or email already exists.
        """
        try:
            user = self.user_service.create_user(
                username=user_data.username,
                email=user_data.email,
                password=user_data.password,
            )
        except ValueError as exc:
            raise UserAlreadyExistsError("Username or email already exists.") from exc

        return UserResponse.model_validate(user)

    def authenticate_user(self, *, identifier: str, password: str) -> User:
        """Authenticate a user and return the authenticated user model.

        Args:
            identifier: Username or email supplied by the caller.
            password: Plaintext password used for verification.

        Returns:
            The authenticated user model.

        Raises:
            InvalidCredentialsError: If the identifier does not resolve to a user or
                the password is incorrect.
            AuthenticationError: If the account is inactive.
        """
        user = self.user_service.get_user_by_identifier(identifier)
        if user is None:
            raise InvalidCredentialsError("Invalid username or password.")

        if not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError("Invalid username or password.")

        if not user.is_active:
            raise AuthenticationError("User account is inactive.")

        return user

    def create_access_token_for_user(self, user: User) -> Token:
        """Create a bearer token response for an authenticated user."""
        access_token = create_access_token(subject=str(user.id))
        return Token(access_token=access_token, token_type="bearer")
