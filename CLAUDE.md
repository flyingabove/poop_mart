# CLAUDE.md

Operating instructions for working in this repo. For product vision and system design, start at [`documentation/AI_DOC_INDEX_CATALOGUE.md`](documentation/AI_DOC_INDEX_CATALOGUE.md).

---

## Project layout

Mirrors the sibling `mvp_chat` project's structure (`../mvp_chat`), one level up — same backend layering, same "thin frontend, one Dockerfile" deploy shape. See [`documentation/model_output_docs/TECH_STACK_AND_INFRASTRUCTURE.md`](documentation/model_output_docs/TECH_STACK_AND_INFRASTRUCTURE.md) for the full module map.

```
backend/app/
  api/            # HTTP routes only — thin, delegates to domain services
  auth/           # authentication (not yet implemented)
  config/         # settings / env loading
  db/             # SQLite access + seed data
  middleware/     # request middleware
  utils/          # shared helpers
  feed/, pricing/, guides/, search/    # domain services with real logic against the DB
  ingestion/, trends/, ai/, notifications/  # documented stubs — need external
                                              # API creds (TikTok/Reddit/OpenAI/etc.)
                                              # before they do real work; see their
                                              # matching design doc before filling in.
frontend/         # single-file static HTML/CSS/JS, no build step
documentation/    # design docs — read AI_DOC_INDEX_CATALOGUE.md first
tests/            # pytest, mirrors backend/app/ structure
```

---

## Adding a new backend module

1. Check [`documentation/AI_DOC_INDEX_CATALOGUE.md`](documentation/AI_DOC_INDEX_CATALOGUE.md) for the design doc that owns the feature. If none exists yet, write one in `documentation/model_output_docs/` first — this project designs before it codes.
2. Create `backend/app/<domain>/` with an `__init__.py`. Keep HTTP concerns in `backend/app/api/<domain>.py` (routes only) and business logic in `backend/app/<domain>/service.py`. Routes call services; services touch the DB. Don't put query logic directly in route handlers.
3. Register the router in `backend/app/main.py`: `app.include_router(<domain>_router, prefix="/api")`.
4. Add tests under `tests/backend/app/api/test_<domain>.py` (and `tests/backend/app/<domain>/` for service-level logic) — the Docker build fails closed if tests fail (see Deploy section), so a broken module can't ship.
5. Update `documentation/model_output_docs/DATA_MODEL_INVENTORY.md` if you add or change a table/entity, and `TECH_STACK_AND_INFRASTRUCTURE.md`'s module map if you add a new top-level folder.
6. If the module needs a new env var (API key, etc.), add it to `.env.example` with a comment, and to the Railway service via `railway variables set` (see below) — never commit a real secret.

---

## Local development

```
cp .env.example .env
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload --port 8000
```

SQLite lives at `./data/poop_mart.db` locally (auto-created), or `/data/poop_mart.db` when a Railway volume is mounted at `/data` — same fallback pattern as `mvp_chat`'s `db/database.py`.

```
pytest
```

---

## Branches & deploy flow (same model as `mvp_chat`)

There is **no `main` branch** — it was deleted after the initial scaffold moved to `beta`, same as `mvp_chat`. Two long-lived branches, each auto-deployed by its own Railway service:

| Branch | Deploys to | Purpose |
|--------|-----------|---------|
| `beta` | Railway service `beta` | Default working branch. Push here first. |
| `prod` | Railway service `prod` | Production. Only merge `beta` → `prod` when explicitly asked. |

Workflow:
1. Work on `beta`, commit, `git push origin beta` — this alone triggers the beta deploy (Railway is connected to the GitHub repo, branch-triggered).
2. Verify on the beta URL.
3. Only when told to ship: `git checkout prod && git merge beta && git push origin prod`.
4. Never push straight to `prod` without explicit approval — same rule as `mvp_chat`'s AGENTS.md.

## Deploying to Railway

This project deploys to its **own** Railway project ("poop mart") — separate from `mvp_chat`'s. Docker-based, same shape as `mvp_chat`'s `Dockerfile`/`Railway.toml` (see that project's `documentation/model_output_docs/INFRASTRUCTURE.md` for the pattern this was adapted from), minus anything specific to `mvp_chat`'s story engine. One Railway project, two services (`beta`, `prod`), each linked to the matching GitHub branch above, each with its own `/data` volume.

The Railway CLI is already authenticated on this machine (`railway whoami`). All of this is scriptable — no dashboard clicking required:

```bash
# One-time: create/link the project (already done — project "poop mart")
railway init                      # interactive project creation, or:
railway link                      # link to an existing project by picking it

# Check what's currently linked
railway status
railway whoami

# Set env vars (never put real values in this repo)
railway variables set KEY=value
railway variables                 # list current vars (names + values — treat output as sensitive)

# Deploy the current directory (builds Dockerfile, pushes, deploys)
railway up

# Get/generate the public URL
railway domain

# Tail logs
railway logs
```

### Env vars this service expects

| Variable | Purpose | Required? |
|----------|---------|------------|
| `DATABASE_URL` / SQLite fallback | Not set → uses `/data/poop_mart.db` (Railway volume) or `./data/poop_mart.db` locally. | No |
| `DISABLE_INGESTION` | Set to `1` to skip starting the background Google News (and YouTube/Instagram, if configured) ingestion loops (tests always set this — see `tests/conftest.py`). Leave unset in production so the feed keeps getting new material. | No |
| `INGEST_INTERVAL_SECONDS` | Override the Google News ingestion poll interval (default 600s). | No |
| `YOUTUBE_API_KEY` | YouTube Data API v3 key (free tier, no OAuth). Without it, `backend/app/ingestion/youtube.py`'s loop never starts — no fake data, it just doesn't run. Get one via Google Cloud Console: new project → enable "YouTube Data API v3" → Credentials → Create Credentials → API Key. | No (yet) |
| `YOUTUBE_INGEST_INTERVAL_SECONDS` | Override the YouTube ingestion poll interval (default 7200s / 2h — kept long to stay inside the free 10,000-unit/day quota; see the module docstring for the math). | No |
| `INSTAGRAM_ACCESS_TOKEN` / `INSTAGRAM_BUSINESS_ACCOUNT_ID` | Instagram Graph API long-lived token + our linked IG Business account's user ID. Without both, `backend/app/ingestion/instagram.py`'s loop never starts. Needs a real Instagram Business account, a linked Facebook Page, a Meta Developer app, Business Verification, and App Review for "Instagram Public Content Access" (days-to-weeks, not guaranteed) — see the module docstring for the exact endpoints once you have a token. | No (yet) |
| `INSTAGRAM_INGEST_INTERVAL_SECONDS` | Override the Instagram ingestion poll interval (default 7200s / 2h). | No |
| `OPENAI_API_KEY` | Only needed once `backend/app/ai/` is wired to a real model — unused by the current seeded-data MVP. | No (yet) |
| `JWT_SECRET` | Real auth (`backend/app/auth/`) is live; a random per-process fallback is used if unset, which is fine for local dev/tests but won't survive a restart in production — set a real persistent value on both Railway services. | Recommended |

### Continuous ingestion

`backend/app/ingestion/news.py` polls Google News RSS in a background task (started in `main.py`'s lifespan, immediately on startup and then every `INGEST_INTERVAL_SECONDS`) and inserts new Pop Mart articles as `regional_news` feed cards — this is what keeps the feed populated with new material without a redeploy. See [`documentation/model_output_docs/TREND_DETECTION_DESIGN.md`](documentation/model_output_docs/TREND_DETECTION_DESIGN.md) for why Google News RSS was chosen over Reddit (Reddit's public JSON endpoint hard-blocks datacenter IPs).

`backend/app/ingestion/youtube.py` is a second real connector (also started in `main.py`'s lifespan, only if `YOUTUBE_API_KEY` is set): it polls Pop Mart's official YouTube channel (`@POPMARTOFFICIAL`, tagged `official` trust tier) plus a handful of unboxing/box-opening/new-release search queries (tagged `community` trust tier), inserting new videos as `video` feed cards. Verified against the live API before shipping.

`backend/app/ingestion/instagram.py` is a third connector, real code but **not yet exercised against the live Instagram Graph API** (no token was available at build time — see the module docstring). Same official/community split: Business Discovery on `@popmart` for official-tier posts, a small fixed hashtag list for community-tier posts. Smoke-test carefully the first time `INSTAGRAM_ACCESS_TOKEN` is actually set.

X/Twitter, TikTok, Xiaohongshu, and Weibo remain deliberately unbuilt — X killed its free API tier on 2026-02-06 (now pay-per-use, $0.005/read, no free option); TikTok has no general public search/discovery API; Xiaohongshu and Weibo are enterprise-partnership-only with no self-serve foreign-developer access. Scraping around any of these is a deliberate non-goal, not an oversight — it would violate each platform's ToS and is fragile by design (same reasoning already applied to Reddit above).

Keep this table in sync with reality — if a module in `ingestion/`, `ai/`, or `auth/` starts making real external calls, add its required env vars here **and** to `.env.example` before merging.

### Persistent data

Attach a Railway volume mounted at `/data` (same as `mvp_chat`) so the SQLite DB (seeded catalog + community Shake Guide contributions) survives redeploys. Without it, every deploy resets to the seed data baked into the image.

### Build-time test gate

Like `mvp_chat`, the goal is that `pytest` runs during `docker build` so a broken build never reaches Railway. Keep `tests/` passing before running `railway up`.

### Live deployment (current state)

Railway project **"poop mart"** (project id `2e1f327c-0e41-4452-b3fc-3e494b69ed72`), two environments:

| Environment | Service | URL |
|-------------|---------|-----|
| `beta` | `beta-backend` | https://beta-backend-beta-0e8e.up.railway.app |
| `prod` | `prod-backend` | https://prod-backend-prod-d9d0.up.railway.app |

Both have a `/data` volume attached and `PORT=8000` set.

**Not GitHub-push-triggered yet.** `railway add --repo flyingabove/poop_mart` failed with "repo not found" — Railway's GitHub App isn't installed/authorized on this repo, which requires a one-time interactive click-through in the Railway dashboard (Project → service → Settings → Source → connect GitHub) that couldn't be done from a non-interactive session. Until that's done, deploys are triggered by running `railway up` locally (see commands above), not by `git push`. To wire up real push-to-deploy: connect the repo once via the dashboard for each service, pointing `beta-backend` at the `beta` branch and `prod-backend` at the `prod` branch — after that, this table's workflow becomes automatic.

### Known issue: CLI-created services need `$PORT`, not a hardcoded port

Dashboard-created Railway services typically auto-detect the Dockerfile's `EXPOSE` port for the public domain. Services created via `railway add` (CLI) did not — the container started fine and listened on 8000, but the edge proxy 502'd on every request without ever reaching the app (confirmed via `railway logs`, zero incoming requests logged). Fix: the Dockerfile `CMD` binds to `${PORT:-8000}` (shell form, so the env var expands at container start) and both services have `PORT=8000` set explicitly. If a future service hits the same 502-with-no-app-logs symptom, check this first before assuming an app bug.
