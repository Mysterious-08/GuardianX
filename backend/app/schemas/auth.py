"""Authentication schemas for GuardianX."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)

UsernameField = Annotated[
    str,
    Field(
        min_length=3,
        max_length=50,
        pattern=r"^[A-Za-z0-9_]+$",
    ),
]

PasswordField = Annotated[
    str,
    Field(
        min_length=8,
        max_length=128,
    ),
]


class UserCreate(BaseModel):
    """Payload for creating a GuardianX account."""

    username: UsernameField
    email: EmailStr
    password: PasswordField

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        """Require a reasonably strong password."""
        has_upper = any(char.isupper() for char in value)
        has_lower = any(char.islower() for char in value)
        has_digit = any(char.isdigit() for char in value)

        if not (has_upper and has_lower and has_digit):
            raise ValueError(
                "Password must contain at least one uppercase letter, one lowercase letter, and one digit."
            )

        return value


class UserLogin(BaseModel):
    """Credentials used to authenticate a GuardianX user."""

    identifier: str = Field(
        min_length=3,
        max_length=255,
        description="Username or email address used during login.",
    )
    password: PasswordField


class Token(BaseModel):
    """JWT response returned after successful authentication."""

    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Claims embedded in the JWT payload."""

    username: str | None = None


class UserResponse(BaseModel):
    """Safe public user representation for API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: UsernameField
    email: EmailStr
    is_active: bool
    created_at: datetime
