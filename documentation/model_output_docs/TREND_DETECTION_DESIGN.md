# Trend Detection & Ingestion Design

**What this doc is for:** How raw posts from external platforms become "Trending" / "What's Hot" feed cards. Edit this doc if a new source is added, the clustering pipeline changes, or trend scoring changes.

---

## Pipeline

```
[Source connectors] -> [Normalization] -> [Embedding] -> [Clustering] -> [Story scoring] -> [Feed card]
```

### 1. Source Connectors (`backend/app/ingestion/`)

One connector per platform, each producing a normalized `RawPost`:

- TikTok
- Instagram
- YouTube
- Reddit
- Xiaohongshu (小红书)
- Weibo
- X
- Official Pop Mart announcements (highest trust tier — treated as ground truth for drops/restocks)

Each connector is responsible only for polling/streaming its platform and mapping platform-specific fields into the shared `RawPost` shape (see [DATA_MODEL_INVENTORY.md](DATA_MODEL_INVENTORY.md)). Rate limits and auth are per-connector concerns and should not leak into downstream stages.

### 2. Normalization

Strip platform formatting, resolve mentioned figures/series against the canonical figure catalog (fuzzy match + alias table — collector nicknames like "the Forest Party Labubu" need to resolve to the same `figure_id` as the official name), tag language and region.

### 3. Embedding & Clustering

Every normalized post is embedded (see [AI_INTELLIGENCE_DESIGN.md](AI_INTELLIGENCE_DESIGN.md)) and clustered against a rolling window of recent posts about the same figure/series. The goal: 500 near-duplicate videos about the same restock become **one** `ClusteredStory` with a source count, not 500 feed cards.

```
ClusteredStory
  - representative_summary (AI-generated, see AI_INTELLIGENCE_DESIGN.md)
  - figure_id / series_id
  - source_counts: { videos: 47, news: 12, discussions: 6 }
  - sentiment_score
  - trend_delta (discussion volume vs. prior window)
```

### 4. Trend Scoring

A figure/series "trends" when discussion volume or price velocity deviates significantly from its own rolling baseline — not from a fixed global threshold, since a niche figure and a flagship figure have wildly different normal volumes.

```
trend_delta = (current_window_volume - baseline_volume) / baseline_volume
```

Cards fire into the 📈 Trending / 🔥 What's Hot feed lanes above a configurable `trend_delta` threshold, decaying back out once volume normalizes.

---

## Trust Tiers

Used by both feed ranking ([FEED_SYSTEM_DESIGN.md](FEED_SYSTEM_DESIGN.md)) and leak handling:

1. **Official** — Pop Mart's own channels/announcements.
2. **Verified creator** — accounts the platform has confirmed are known collector creators.
3. **Community** — regular user posts/discussions.
4. **Unverified / rumor** — leak sources; always labeled 🕵️ Leak and never conflated with confirmed drops.

---

## Open Questions

- Xiaohongshu and Weibo access typically requires either an approved API partner or scraping with real legal/ToS review — needs a decision before building those two connectors.
- How long does a `ClusteredStory` stay open before a new post starts a new cluster instead of joining it?
