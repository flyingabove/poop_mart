# Search Design

**What this doc is for:** Search across figures, series, and content. Edit this doc if the search index schema or per-figure feed logic changes.

---

## Search Surface

Search resolves a query (e.g. "Labubu", "Crybaby", "Skullpanda", "Molly", "Hirono", "Dimoo") to a **series or figure**, which then has its own dedicated feed — every card type from [FEED_SYSTEM_DESIGN.md](FEED_SYSTEM_DESIGN.md) filtered to that entity, plus its price chart ([PRICE_TRACKING_DESIGN.md](PRICE_TRACKING_DESIGN.md)) and its Shake Guide ([SHAKE_GUIDES_DESIGN.md](SHAKE_GUIDES_DESIGN.md)) if one exists.

## Index

Backed by Elasticsearch/OpenSearch (see [TECH_STACK_AND_INFRASTRUCTURE.md](TECH_STACK_AND_INFRASTRUCTURE.md)):

- Figure/series canonical names + alias table (collector nicknames, regional names, transliterations) — same alias table used by ingestion normalization in [TREND_DETECTION_DESIGN.md](TREND_DETECTION_DESIGN.md), so a search hit and a post's resolved figure are guaranteed consistent.
- Free-text search over community posts, reviews, and guide content.
- Typo tolerance / fuzzy matching — collector spelling of figure names is inconsistent across platforms and languages.

## Per-Entity Feed

Landing on a figure or series page is functionally "Trending tab, filtered to one entity" — it reuses the feed ranking logic rather than being a bespoke view.

---

## Open Questions

- Does search need cross-language matching (e.g. a Chinese query resolving an English-named figure) for v1, or is that a v2 concern once the alias table has real coverage?
