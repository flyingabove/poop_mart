# Price Tracking Design

**What this doc is for:** The StockX-like layer — per-figure pricing, history, and the marketplace surface. Edit this doc if price sourcing, the valuation model, or the marketplace tab changes.

---

## Per-Figure Price Data

Every figure carries:

- **Current resale price** — aggregated across resale sources (see Sourcing below).
- **Historical chart** — price over time, same shape as a stock chart.
- **Rarity** — pull rate if published/estimated, secret/chase status.
- **Sell-through rate** — % of listed units that actually sell, a better liquidity signal than list price alone.
- **Regional availability** — which countries/regions currently stock it retail vs. resale-only.

## Sourcing

Resale prices are pulled from public listing data on resale platforms (and, where available, partner APIs). Because resale platforms vary in reliability, price is stored as an **aggregate with a confidence band**, not a single point value — a figure with 3 listings should visually read as less certain than one with 300.

```
PriceSnapshot
  - figure_id
  - timestamp
  - median_price
  - low / high
  - listing_count      # confidence signal
  - source
```

## Collection Valuation

A user's collection (see [USER_PROFILES_AND_SOCIAL_DESIGN.md](USER_PROFILES_AND_SOCIAL_DESIGN.md)) valuation is the sum of current median price across owned figures. This is a **premium feature** (see [MONETIZATION.md](MONETIZATION.md)) — the number itself is gated, though individual figure prices are free to view.

## Marketplace Tab

- **Price tracking** — browse/search figures by price, price movement, rarity.
- **Wishlists** — save figures, get notified on price drops or restocks (see [NOTIFICATIONS_DESIGN.md](NOTIFICATIONS_DESIGN.md)).
- **Sale alerts** — threshold-based alerts ("notify me if under $X").
- **Marketplace affiliate links** — outbound links to resale platforms, monetized via affiliate (see [MONETIZATION.md](MONETIZATION.md)). PoopMart does not host transactions itself in v1 — it is a price/discovery layer, not a marketplace of record.

---

## Open Questions

- Which resale platforms have usable public data vs. require a formal partnership before we can source from them?
- Does sell-through rate need per-region breakdown, or is a single global number sufficient for v1?
