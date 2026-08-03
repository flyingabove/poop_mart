"""SQLite database initialization and connection helpers."""
import sqlite3
import asyncio
from pathlib import Path

# Railway provides /data as a persistent volume; fall back to ./data for local dev.
DATA_DIR = Path("/data") if Path("/data").exists() else Path("./data")
DB_PATH = DATA_DIR / "poop_mart.db"

_SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS series (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    aliases         TEXT DEFAULT '',
    brand_line      TEXT NOT NULL,
    release_date    TEXT,
    regions         TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS figures (
    id                    TEXT PRIMARY KEY,
    series_id             TEXT NOT NULL REFERENCES series(id),
    name                  TEXT NOT NULL,
    colorway              TEXT,
    is_secret_chase       INTEGER DEFAULT 0,
    published_pull_rate   REAL,
    image_url             TEXT
);

CREATE INDEX IF NOT EXISTS idx_figures_series ON figures(series_id);

CREATE TABLE IF NOT EXISTS feed_cards (
    id                  TEXT PRIMARY KEY,
    card_type           TEXT NOT NULL,
    figure_id           TEXT REFERENCES figures(id),
    series_id           TEXT REFERENCES series(id),
    title               TEXT NOT NULL,
    body                TEXT NOT NULL,
    source_trust_tier   TEXT DEFAULT 'community',
    source_counts_json  TEXT,
    sentiment_score     REAL,
    region              TEXT,
    created_at          INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_feed_created ON feed_cards(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_feed_type ON feed_cards(card_type);

CREATE TABLE IF NOT EXISTS price_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    figure_id       TEXT NOT NULL REFERENCES figures(id),
    timestamp       INTEGER NOT NULL,
    median_price    REAL NOT NULL,
    low_price       REAL NOT NULL,
    high_price      REAL NOT NULL,
    listing_count   INTEGER NOT NULL,
    source          TEXT DEFAULT 'aggregate'
);

CREATE INDEX IF NOT EXISTS idx_price_figure ON price_snapshots(figure_id, timestamp);

CREATE TABLE IF NOT EXISTS shake_guides (
    id                  TEXT PRIMARY KEY,
    series_id           TEXT NOT NULL UNIQUE REFERENCES series(id),
    technique_summary   TEXT NOT NULL,
    etiquette_note      TEXT NOT NULL DEFAULT
        'Community folklore, not guaranteed. Some stores don''t allow box handling — check before you shake, and always be gentle.',
    created_at          INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS guide_contributions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    guide_id        TEXT NOT NULL REFERENCES shake_guides(id),
    figure_id       TEXT REFERENCES figures(id),
    technique_type  TEXT NOT NULL,
    claim_text      TEXT NOT NULL,
    weight_range_g  TEXT,
    upvotes         INTEGER DEFAULT 0,
    downvotes       INTEGER DEFAULT 0,
    video_url       TEXT,
    created_at      INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_contrib_guide ON guide_contributions(guide_id);
"""


def init_db() -> None:
    """Create tables if they don't exist. Called once at startup."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.executescript(_SCHEMA)
    conn.commit()
    conn.close()


def get_connection() -> sqlite3.Connection:
    """Return a new SQLite connection. Caller is responsible for closing."""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


async def run_sync(fn, *args):
    """Run a synchronous SQLite function in a thread pool."""
    return await asyncio.to_thread(fn, *args)
