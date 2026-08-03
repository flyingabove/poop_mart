"""App-wide settings. Keep this small — most config lives close to the module
that uses it (e.g. backend/app/db/database.py owns its own DB path fallback)."""
import os

APP_TITLE = "PoopMart API"
APP_VERSION = "0.1.0"

# CORS: no cookie-based auth yet, so a wide-open origin list is safe. Tighten
# this once backend/app/auth/ ships real sessions.
CORS_ORIGINS = ["*"]

PORT = int(os.getenv("PORT", "8000"))
