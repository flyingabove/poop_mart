# Tech Stack & Infrastructure

**What this doc is for:** Stack choices and deployment. Edit this doc if a technology choice changes or a new infra dependency is added.

---

## Frontend

Flutter or React Native — final choice deferred until team's mobile experience is scoped; both support the single-codebase-for-iOS/Android requirement this product needs (feed-heavy, notification-heavy app).

## Backend

- **FastAPI** — API layer, mirrors [`mvp_chat`](../../..)'s backend structure (`backend/app/{api,auth,config,db,middleware,utils}` + domain modules).
- **PostgreSQL** — system of record (catalog, users, collections, price history).
- **Redis** — caching, rate limiting, and (per Feeds below) stream transport.
- **Elasticsearch / OpenSearch** — search index, see [SEARCH_DESIGN.md](SEARCH_DESIGN.md).

## AI

- **GPT-class LLM** — story summaries, sentiment (see [AI_INTELLIGENCE_DESIGN.md](AI_INTELLIGENCE_DESIGN.md)).
- **Vision model** — figure identification from photos.
- **Embedding model** — duplicate/near-duplicate post clustering, see [TREND_DETECTION_DESIGN.md](TREND_DETECTION_DESIGN.md).

## Feeds & Streaming

- **Kafka or Redis Streams** — ingestion connectors publish `RawPost` events; clustering/scoring consume them asynchronously so a slow platform connector never blocks the feed.
- **Ranking pipeline** — similar shape to a social-media feed ranker, see [FEED_SYSTEM_DESIGN.md](FEED_SYSTEM_DESIGN.md).

## Deployment

Docker-based, Railway-hosted (see root `Railway.toml`), matching `mvp_chat`'s deployment shape.

---

## Backend Module Layout

Mirrors `mvp_chat`'s domain-oriented backend structure — generic layers (`api/`, `auth/`, `config/`, `db/`, `middleware/`, `utils/`) plus one folder per product domain:

```
backend/app/
  api/            # HTTP routes
  auth/           # authentication
  config/         # settings / env loading
  db/             # database access
  middleware/     # request middleware
  utils/          # shared helpers
  feed/           # feed assembly + ranking, see FEED_SYSTEM_DESIGN.md
  ingestion/      # per-platform source connectors, see TREND_DETECTION_DESIGN.md
  trends/         # clustering + trend scoring, see TREND_DETECTION_DESIGN.md
  pricing/        # price aggregation + valuation, see PRICE_TRACKING_DESIGN.md
  guides/         # Shake Guides + other how-to content, see SHAKE_GUIDES_DESIGN.md
  ai/             # summarization, sentiment, vision, embeddings, see AI_INTELLIGENCE_DESIGN.md
  search/         # search indexing/query, see SEARCH_DESIGN.md
  notifications/  # alert rules + delivery, see NOTIFICATIONS_DESIGN.md
```

---

## Open Questions

- Flutter vs. React Native — needs a decision before frontend work starts; not blocking backend/design work.
- Managed vs. self-hosted OpenSearch and Kafka for early stages, given team size — likely managed until traffic justifies self-hosting.
