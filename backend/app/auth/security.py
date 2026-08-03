"""Password hashing + JWT issuance. Stdlib hashing (PBKDF2-HMAC-SHA256) so no
extra native dependency is needed beyond PyJWT for token encode/decode."""
import hashlib
import hmac
import os
import time

import jwt

from backend.app.config.settings import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRY_DAYS

_PBKDF2_ITERATIONS = 200_000


def hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return salt.hex(), digest.hex()


def verify_password(password: str, salt_hex: str, hash_hex: str) -> bool:
    _, candidate_hex = hash_password(password, bytes.fromhex(salt_hex))
    return hmac.compare_digest(candidate_hex, hash_hex)


def create_access_token(user_id: str, email: str) -> str:
    now = int(time.time())
    payload = {"sub": user_id, "email": email, "iat": now, "exp": now + JWT_EXPIRY_DAYS * 86400}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
