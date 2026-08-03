# poop_mart

## Project layout

```
backend/         # API server
  app/
    api/         # routes
    auth/        # authentication
    config/      # settings / env loading
    db/          # database access
    middleware/  # request middleware
    utils/       # shared helpers
  requirements.txt
frontend/         # static frontend (HTML/JS/CSS)
tests/            # test suite (pytest)
scripts/          # one-off / maintenance scripts
```

## Setup

```
cp .env.example .env   # fill in local secrets
pip install -r backend/requirements.txt
```

## Testing

```
pytest
```

## Deployment

Configured for Docker-based deployment (see `Railway.toml`).
