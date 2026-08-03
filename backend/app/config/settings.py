"""App-wide settings. Keep this small — most config lives close to the module
that uses it (e.g. backend/app/db/database.py owns its own DB path fallback)."""
import logging
import os
import secrets

APP_TITLE = "PoopMart API"
APP_VERSION = "0.1.0"

# CORS: auth is bearer-token (Authorization header), not cookies, so a wide
# open origin list stays safe (no CSRF surface from allow_credentials).
CORS_ORIGINS = ["*"]

PORT = int(os.getenv("PORT", "8000"))

# --- Auth ---
# Falls back to a random per-process secret if unset, so local dev/tests
# never need setup — but that means tokens stop validating on every restart.
# Railway's beta/prod services have a real persistent JWT_SECRET set via
# `railway variables set` (see CLAUDE.md) so logins survive redeploys there.
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    JWT_SECRET = secrets.token_hex(32)
    logging.getLogger(__name__).warning(
        "JWT_SECRET not set — using a random per-process secret. "
        "Existing tokens will stop working on restart. Set JWT_SECRET in "
        "production (see CLAUDE.md)."
    )
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_DAYS = 365
