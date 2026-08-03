# Notifications Design

**What this doc is for:** What pulls a user back into the app. Edit this doc if a new notification type is added or delivery rules change.

---

## Notification Types

| Example | Trigger source |
|---------|-----------------|
| "Labubu V4 announced." | Official-tier post in [TREND_DETECTION_DESIGN.md](TREND_DETECTION_DESIGN.md) matching a followed series. |
| "Your wishlist item dropped 15%." | Price threshold crossed, see [PRICE_TRACKING_DESIGN.md](PRICE_TRACKING_DESIGN.md). |
| "Pop Mart livestream starts in 30 minutes." | Scheduled event, official source. |
| "Restock detected." | Regional availability change, ingestion-sourced. |
| "New Shake Guide confidence update for [series]." | Guide contribution threshold crossed, see [SHAKE_GUIDES_DESIGN.md](SHAKE_GUIDES_DESIGN.md). |

## Delivery Rules

- All notifications are opt-in per category (price alerts, drops, restocks, guide updates, social) — no bundled "all or nothing" toggle.
- Price/restock alerts are rate-limited per figure per user (no more than one push per threshold crossing per cooldown window) to avoid spamming on volatile figures.
- Leak-tier ("🕵️") content never triggers a push notification on its own — only confirmed/official-tier events do. Leaks surface passively in the feed only.

---

## Open Questions

- Push vs. in-app-only for free-tier users — is push a premium perk (see [MONETIZATION.md](MONETIZATION.md)) or available to everyone with reduced frequency?
