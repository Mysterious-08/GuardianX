from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.user import User
from app.security.hashing import hash_password


class UserService:
    """Persistence-only service for managing GuardianX users.

    This service is intentionally limited to SQLAlchemy-backed database operations.
    Authentication concerns such as JWT issuance, login workflows, and token
    validation remain outside this class.
    """

    def __init__(self, db: Session):
        """Initialize the service with a SQLAlchemy session via dependency injection."""
        self.db = db

    def create_user(
        self,
        *,
        username: str,
        email: str,
        password: str,
        is_active: bool = True,
    ) -> User:
        """Create and persist a new user after hashing the supplied password."""
        normalized_username = username.strip().lower()
        normalized_email = email.strip().lower()

        user = User(
            username=normalized_username,
            email=normalized_email,
            hashed_password=hash_password(password),
            is_active=is_active,
        )

        try:
            self.db.add(user)
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise ValueError("Username or email already exists.")

        self.db.refresh(user)
        return user

    def get_user_by_id(self, user_id: UUID) -> User | None:
        """Retrieve a user by primary key, returning ``None`` when absent."""
        return self.db.get(User, user_id)

    def get_user_by_username(self, username: str) -> User | None:
        """Retrieve a user by normalized username, returning ``None`` when absent."""
        normalized_username = username.strip().lower()
        statement = select(User).where(User.username == normalized_username)
        return self.db.scalar(statement)

    def get_user_by_email(self, email: str) -> User | None:
        """Retrieve a user by normalized email address, returning ``None`` when absent."""
        normalized_email = email.strip().lower()
        statement = select(User).where(User.email == normalized_email)
        return self.db.scalar(statement)

    def get_user_by_identifier(self, identifier: str) -> User | None:
        """Retrieve a user by either normalized username or normalized email."""
        normalized_identifier = identifier.strip().lower()
        statement = select(User).where(
            (User.username == normalized_identifier) | (User.email == normalized_identifier)
        )
        return self.db.scalar(statement)

    def username_exists(self, username: str) -> bool:
        """Check whether a normalized username is already present in the database."""
        normalized_username = username.strip().lower()
        statement = select(User.id).where(User.username == normalized_username).limit(1)
        return self.db.scalar(statement) is not None

    def email_exists(self, email: str) -> bool:
        """Check whether a normalized email address is already present in the database."""
        normalized_email = email.strip().lower()
        statement = select(User.id).where(User.email == normalized_email).limit(1)
        return self.db.scalar(statement) is not None
