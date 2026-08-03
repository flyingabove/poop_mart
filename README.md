# poop_mart

A single feed for the Pop Mart collector world — trending figures, new drops, price tracking, and community box-shaking guides. See [`documentation/human_north_star_docs/NorthStar.md`](documentation/human_north_star_docs/NorthStar.md) for the product vision and [`documentation/AI_DOC_INDEX_CATALOGUE.md`](documentation/AI_DOC_INDEX_CATALOGUE.md) for the full design doc index.

## Project layout

```
backend/         # API server
  app/
    api/            # routes
    auth/           # authentication
    config/         # settings / env loading
    db/             # database access
    middleware/     # request middleware
    utils/          # shared helpers
    feed/           # feed assembly + ranking
    ingestion/      # per-platform source connectors (TikTok, Reddit, etc.)
    trends/         # clustering + trend scoring
    pricing/        # price aggregation + collection valuation
    guides/         # Shake Guides + other how-to content
    ai/             # summarization, sentiment, vision, embeddings
    search/         # search indexing/query
    notifications/  # alert rules + delivery
  requirements.txt
frontend/         # static frontend (HTML/JS/CSS)
documentation/    # design docs — start at AI_DOC_INDEX_CATALOGUE.md
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
