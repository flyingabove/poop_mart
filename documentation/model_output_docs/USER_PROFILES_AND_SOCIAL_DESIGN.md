# User Profiles & Social Design

**What this doc is for:** Profiles, collections, follows, and reputation. Edit this doc if profile structure, badge rules, or the collection model changes.

---

## What a Profile Contains

- **Collection showcase** — figures the user owns, optionally with photos (auto-tagged via the vision model, see [AI_INTELLIGENCE_DESIGN.md](AI_INTELLIGENCE_DESIGN.md)).
- **Collection valuation** — sum of current median resale price across owned figures (premium, see [PRICE_TRACKING_DESIGN.md](PRICE_TRACKING_DESIGN.md) and [MONETIZATION.md](MONETIZATION.md)).
- **Unboxings & pulls** — 📷 Community Post cards, chronological on the profile.
- **Reviews** — per-figure star rating + short writeup, rolls up into figure-page review aggregates.
- **Rankings** — user-curated top-N lists ("My Top 10 Labubu colorways").
- **Follows** — other collectors and creators; drives the "For You" feed (see [FEED_SYSTEM_DESIGN.md](FEED_SYSTEM_DESIGN.md)).
- **Badges** — earned reputation markers (see below).

## Badges

Badges are earned, not purchased — they're a trust signal, not a monetization surface.

| Badge | Earned by |
|-------|-----------|
| Verified Creator | Manual/verified-account process for known creators (feeds trust tiers in [TREND_DETECTION_DESIGN.md](TREND_DETECTION_DESIGN.md)). |
| Early Adopter | Account age / early registration cohort. |
| Guide Contributor | Sustained, well-voted contributions to [Shake Guides](SHAKE_GUIDES_DESIGN.md). |
| Top Reviewer | Review volume + helpfulness votes. |

## Collections as Data

A user's collection is a structured list (`figure_id`, acquired date, condition, optional photo), not just a feed of posts — it's the input to valuation, wishlist matching, and profile showcases. See `Collection` / `CollectionItem` in [DATA_MODEL_INVENTORY.md](DATA_MODEL_INVENTORY.md).

---

## Open Questions

- Do reviews require proof of ownership (collection contains the figure) before posting, to cut down on drive-by reviews?
- Should follows be one-directional (Twitter-style) or mutual (friends-style)? One-directional fits the creator-following use case better.
