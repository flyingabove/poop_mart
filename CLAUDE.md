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
| `OPENAI_API_KEY` | Only needed once `backend/app/ai/` is wired to a real model — unused by the current seeded-data MVP. | No (yet) |
| `JWT_SECRET` | Only needed once `backend/app/auth/` is implemented. | No (yet) |

Keep this table in sync with reality — if a module in `ingestion/`, `ai/`, or `auth/` starts making real external calls, add its required env vars here **and** to `.env.example` before merging.

### Persistent data

Attach a Railway volume mounted at `/data` (same as `mvp_chat`) so the SQLite DB (seeded catalog + community Shake Guide contributions) survives redeploys. Without it, every deploy resets to the seed data baked into the image.

### Build-time test gate

Like `mvp_chat`, the goal is that `pytest` runs during `docker build` so a broken build never reaches Railway. Keep `tests/` passing before running `railway up`.
