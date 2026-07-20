from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError

from app.core.config import settings


class TokenError(Exception):
    """Base application-level exception for JWT token problems."""


class TokenExpiredError(TokenError):
    """Raised when a JWT token has passed its expiration time."""


class TokenInvalidError(TokenError):
    """Raised when a JWT token cannot be decoded or validated."""


def create_access_token(subject: str | Any, expires_delta: timedelta | None = None) -> str:
    """Create a signed JWT access token for the supplied subject.

    Args:
        subject: Value to encode in the token's ``sub`` claim.
        expires_delta: Optional custom lifetime for the token. When omitted,
            the configured ``ACCESS_TOKEN_EXPIRE_MINUTES`` value is used.

    Returns:
        A compact JWT string signed with the configured algorithm and secret key.
    """
    now = datetime.now(UTC)
    expire_time = now + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {
        "sub": str(subject),
        "exp": expire_time,
        "iat": now,
        "iss": settings.JWT_ISSUER,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate an access token.

    Args:
        token: Encoded JWT string.

    Returns:
        The decoded token payload.

    Raises:
        TokenExpiredError: If the token's expiration claim has been reached.
        TokenInvalidError: If the token is malformed, tampered with, or otherwise
            cannot be validated.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            issuer=settings.JWT_ISSUER,
        )
    except ExpiredSignatureError as exc:
        raise TokenExpiredError("Token has expired.") from exc
    except InvalidTokenError as exc:
        raise TokenInvalidError("Token is invalid or malformed.") from exc

    if not payload.get("sub"):
        raise TokenInvalidError("Missing subject claim.")

    return payload
