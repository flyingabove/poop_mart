# Feed System Design

**What this doc is for:** The core feed — card types, tabs, and ranking. This is the primary surface of the app; almost every other system (trend detection, pricing, guides, notifications) ultimately feeds a card into this feed. Edit this doc if the card taxonomy, tab structure, or ranking inputs change.

---

## Design Principle

The feed should read like a social feed (TikTok/Reddit), not a shopping catalogue. Every card is a *moment* — something happened, changed, or is worth seeing — not a static product listing.

---

## Card Types

| Icon | Card Type | Source system | Example |
|------|-----------|----------------|---------|
| 📈 | Trending | [TREND_DETECTION_DESIGN.md](TREND_DETECTION_DESIGN.md) | "Labubu Macaron series up 18% this week." |
| 🆕 | New Drops | Drop calendar (ingestion + official Pop Mart feed) | New Pop Mart releases worldwide. |
| 🎥 | Videos | Ingestion (TikTok / YouTube Shorts / Instagram Reels) | Short-form content discussing figures. |
| 📷 | Community Posts | [USER_PROFILES_AND_SOCIAL_DESIGN.md](USER_PROFILES_AND_SOCIAL_DESIGN.md) | Collections, pulls, unboxings. |
| 💰 | Price Changes | [PRICE_TRACKING_DESIGN.md](PRICE_TRACKING_DESIGN.md) | Rare figures increasing or decreasing in resale value. |
| 🔥 | What's Hot | [TREND_DETECTION_DESIGN.md](TREND_DETECTION_DESIGN.md) | "Labubu V3 is exploding in Korea." |
| 🕵️ | Leaks | Ingestion (rumor/leak sources, lower trust weight) | Upcoming series and rumors. |
| ⭐ | Reviews | [USER_PROFILES_AND_SOCIAL_DESIGN.md](USER_PROFILES_AND_SOCIAL_DESIGN.md) | Best and worst figures, ranked by collectors. |
| 🌎 | Regional News | Ingestion, tagged by region | China, Japan, Korea, US exclusives. |
| 🎲 | Shake Guides | [SHAKE_GUIDES_DESIGN.md](SHAKE_GUIDES_DESIGN.md) | New or updated technique for a series that hasn't been opened yet. |

Every card type shares a common envelope (see `FeedCard` in [DATA_MODEL_INVENTORY.md](DATA_MODEL_INVENTORY.md)) so the client can render a heterogeneous feed without per-type special-casing beyond the card body.

---

## Tabs

| Tab | Purpose |
|-----|---------|
| **For You** | Personalized ranking blending followed figures/creators, collection overlap, and engagement history. |
| **Trending** | Most-discussed figures right now, unpersonalized, city/region filterable. |
| **News** | Official announcements + regional news cards only. |
| **Videos** | Short-form video cards only. |
| **Collections** | User collection showcases. |
| **Guides** | Shake Guides and other how-to content (see [SHAKE_GUIDES_DESIGN.md](SHAKE_GUIDES_DESIGN.md)). |
| **Marketplace** | Price tracking, wishlists, sale alerts — the StockX-like surface. |

---

## Ranking (v1)

v1 ranking is intentionally simple — a weighted blend, not a learned model:

```
score = w1 * recency_decay
      + w2 * engagement_velocity      # likes/comments/shares per hour
      + w3 * source_trust             # official > verified creator > community > unverified
      + w4 * personalization_match    # followed figures/creators/series overlap
      - w5 * duplicate_penalty        # already-clustered story shown recently
```

A learned ranking model is a v2 concern once there's engagement data to train on — do not build one before the feed has real traffic.

---

## Open Questions

- Does "For You" need an explicit cold-start onboarding step (pick your favorite series) or do we infer from first-session behavior?
- Do Shake Guide cards need a distinct visual treatment (they're instructional, not news) or do they fit the standard card shell?
