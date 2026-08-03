# Data Model Inventory

**What this doc is for:** The canonical list of core entities referenced across the other design docs, so schema doesn't drift between them. Edit this doc if any entity or field is added or changed — this should always match the actual DB schema once one exists.

---

## Catalog

```
Series
  - id, name, aliases[]              # alias table shared by search + ingestion normalization
  - brand_line (e.g. Labubu, Crybaby, Skullpanda, Molly, Hirono, Dimoo)
  - release_date
  - regions_available[]

Figure
  - id, series_id
  - name, colorway
  - is_secret_chase (bool)
  - published_pull_rate (nullable)
  - reference_images[]                # used by vision figure-ID, see AI_INTELLIGENCE_DESIGN.md
```

## Feed & Content

```
FeedCard                              # shared envelope, see FEED_SYSTEM_DESIGN.md
  - id, card_type (enum: trending | new_drop | video | community_post |
                          price_change | whats_hot | leak | review |
                          regional_news | shake_guide)
  - figure_id / series_id (nullable)
  - created_at, source_trust_tier
  - body                              # type-specific payload

RawPost                               # ingestion output, see TREND_DETECTION_DESIGN.md
  - id, platform, url
  - author, text, media[]
  - language, region
  - resolved_figure_id / resolved_series_id
  - trust_tier

ClusteredStory                        # AI clustering output, see TREND_DETECTION_DESIGN.md / AI_INTELLIGENCE_DESIGN.md
  - id, figure_id / series_id
  - representative_summary
  - sentiment_score
  - source_counts { videos, news, discussions }
  - trend_delta
```

## Pricing

```
PriceSnapshot                         # see PRICE_TRACKING_DESIGN.md
  - figure_id, timestamp
  - median_price, low, high
  - listing_count
  - source
```

## Guides

```
ShakeGuide / GuideContribution        # see SHAKE_GUIDES_DESIGN.md
```

## Social

```
User
  - id, handle, badges[]

Collection / CollectionItem           # see USER_PROFILES_AND_SOCIAL_DESIGN.md
  - user_id, figure_id, acquired_at, condition, photo (nullable)

Wishlist / WishlistItem
  - user_id, figure_id, alert_threshold (nullable)

Review
  - user_id, figure_id, rating, text

Follow
  - follower_id, followed_id (user or creator)
```

---

## Open Questions

- Does `Figure` need a `variant_group_id` to link colorway variants of the same sculpt for price-comparison purposes?
