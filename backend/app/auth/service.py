"""Signup/login business logic. Routes in api/auth.py stay thin and just
translate AuthError -> HTTP status codes."""
import time
import uuid

from backend.app.auth.security import create_access_token, hash_password, verify_password
from backend.app.db.database import get_connection


class AuthError(Exception):
    pass


def signup(email: str, password: str) -> dict:
    email = email.strip().lower()
    if not email or "@" not in email or "." not in email.split("@")[-1]:
        raise AuthError("invalid email")
    if len(password) < 8:
        raise AuthError("password must be at least 8 characters")

    conn = get_connection()
    try:
        if conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone():
            raise AuthError("email already registered")

        user_id = str(uuid.uuid4())
        salt, pw_hash = hash_password(password)
        now = int(time.time())
        conn.execute(
            "INSERT INTO users (id, email, password_salt, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, email, salt, pw_hash, now),
        )
        conn.commit()
        return {"user_id": user_id, "email": email, "access_token": create_access_token(user_id, email)}
    finally:
        conn.close()


def login(email: str, password: str) -> dict:
    email = email.strip().lower()
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not row or not verify_password(password, row["password_salt"], row["password_hash"]):
            raise AuthError("invalid email or password")
        return {
            "user_id": row["id"],
            "email": row["email"],
            "access_token": create_access_token(row["id"], row["email"]),
        }
    finally:
        conn.close()


def change_password(user_id: str, current_password: str, new_password: str) -> None:
    if len(new_password) < 8:
        raise AuthError("password must be at least 8 characters")

    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row or not verify_password(current_password, row["password_salt"], row["password_hash"]):
            raise AuthError("current password is incorrect")

        salt, pw_hash = hash_password(new_password)
        conn.execute(
            "UPDATE users SET password_salt = ?, password_hash = ? WHERE id = ?",
            (salt, pw_hash, user_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_user(user_id: str) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT id, email, created_at FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()
