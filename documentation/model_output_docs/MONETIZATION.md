# Monetization Design

**What this doc is for:** Revenue surfaces and how they interact with the free experience. Edit this doc if a new revenue stream is added or a feature's free/premium boundary changes.

---

## Streams

| Stream | What's gated |
|--------|---------------|
| Premium trend analytics | Deeper trend history, region breakdowns, raw source lists behind the AI summary (see [TREND_DETECTION_DESIGN.md](TREND_DETECTION_DESIGN.md)). |
| Collection valuation | The rolled-up dollar value of a user's collection (individual figure prices stay free, see [PRICE_TRACKING_DESIGN.md](PRICE_TRACKING_DESIGN.md)). |
| Price alerts | Free tier gets a capped number of active alerts; premium is unlimited. |
| Marketplace affiliate links | Not user-gated — passive revenue on outbound resale-platform clicks. |
| Sponsored creator content | Always clearly labeled as sponsored; never mixed into the trust-tier system in [TREND_DETECTION_DESIGN.md](TREND_DETECTION_DESIGN.md) as if it were organic. |
| Premium news summaries | Faster/deeper AI summaries (see [AI_INTELLIGENCE_DESIGN.md](AI_INTELLIGENCE_DESIGN.md)); the basic summary stays free — paying removes a delay/depth cap, not gates the core "what's happening" value prop. |

## Guiding Rule

The core promise of the app — one feed that tells you what's happening — must stay free. Monetization gates *depth and convenience* (history, valuation, unlimited alerts, speed), never the basic ability to see what's trending or read a Shake Guide. Gating the community-knowledge features (Shake Guides, reviews) would undercut the reason people contribute to them.

---

## Open Questions

- Subscription tier structure (single premium tier vs. multiple) — deferred until there's usage data to size tiers against.
