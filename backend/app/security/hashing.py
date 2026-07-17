from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

password_hasher = PasswordHash(
    hashers=[
        Argon2Hasher(
            time_cost=3,
            memory_cost=65_536,
            parallelism=4,
            hash_len=32,
            salt_len=16,
        )
    ]
)


def hash_password(password: str) -> str:
    """Hash a plaintext password using a secure Argon2 configuration."""
    return password_hasher.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored hashed password."""
    return password_hasher.verify(password, hashed_password)
