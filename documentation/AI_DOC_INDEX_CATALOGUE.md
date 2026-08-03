# Documentation Index & Catalogue

> **What this doc is for:** The single index of all project documentation. Use this to find the right doc to read or edit. Every doc has a one-line "edit this doc if..." description so you don't have to open every file to figure out where new info goes.

---

## Vision (Human-Owned, Read-Only Unless Asked)

| Doc | Edit this doc if... |
|-----|---------------------|
| [NorthStar.md](human_north_star_docs/NorthStar.md) | ...the long-term product vision or user experience goals change. **Vision only, no technical details.** |

## Core Feed

| Doc | Edit this doc if... |
|-----|---------------------|
| [FEED_SYSTEM_DESIGN.md](model_output_docs/FEED_SYSTEM_DESIGN.md) | ...the card taxonomy, tab structure, or feed ranking inputs change. **Start here — most other systems feed this one.** |

## Trends & Intelligence

| Doc | Edit this doc if... |
|-----|---------------------|
| [TREND_DETECTION_DESIGN.md](model_output_docs/TREND_DETECTION_DESIGN.md) | ...a new ingestion source is added, the clustering pipeline changes, or trend scoring changes. |
| [AI_INTELLIGENCE_DESIGN.md](model_output_docs/AI_INTELLIGENCE_DESIGN.md) | ...the summarization prompt, embedding model, or vision pipeline changes. |

## Marketplace & Pricing

| Doc | Edit this doc if... |
|-----|---------------------|
| [PRICE_TRACKING_DESIGN.md](model_output_docs/PRICE_TRACKING_DESIGN.md) | ...price sourcing, the valuation model, or the marketplace tab changes. |

## Guides

| Doc | Edit this doc if... |
|-----|---------------------|
| [SHAKE_GUIDES_DESIGN.md](model_output_docs/SHAKE_GUIDES_DESIGN.md) | ...guide structure, contribution/voting rules, or the disclaimer policy changes. **The box-shaking technique feature.** |

## Social

| Doc | Edit this doc if... |
|-----|---------------------|
| [USER_PROFILES_AND_SOCIAL_DESIGN.md](model_output_docs/USER_PROFILES_AND_SOCIAL_DESIGN.md) | ...profile structure, badge rules, or the collection model changes. |

## Search

| Doc | Edit this doc if... |
|-----|---------------------|
| [SEARCH_DESIGN.md](model_output_docs/SEARCH_DESIGN.md) | ...the search index schema or per-figure feed logic changes. |

## Notifications

| Doc | Edit this doc if... |
|-----|---------------------|
| [NOTIFICATIONS_DESIGN.md](model_output_docs/NOTIFICATIONS_DESIGN.md) | ...a new notification type is added or delivery rules change. |

## Monetization

| Doc | Edit this doc if... |
|-----|---------------------|
| [MONETIZATION.md](model_output_docs/MONETIZATION.md) | ...a new revenue stream is added or a feature's free/premium boundary changes. |

## Data Model

| Doc | Edit this doc if... |
|-----|---------------------|
| [DATA_MODEL_INVENTORY.md](model_output_docs/DATA_MODEL_INVENTORY.md) | ...any core entity or field is added or changed. Keep in sync with the real DB schema once one exists. |

## Tech Stack & Infrastructure

| Doc | Edit this doc if... |
|-----|---------------------|
| [TECH_STACK_AND_INFRASTRUCTURE.md](model_output_docs/TECH_STACK_AND_INFRASTRUCTURE.md) | ...a technology choice changes, a new infra dependency is added, or the backend module layout changes. |

---

## Reading Order for New Contributors

1. [NorthStar.md](human_north_star_docs/NorthStar.md) — what we're building and why.
2. [FEED_SYSTEM_DESIGN.md](model_output_docs/FEED_SYSTEM_DESIGN.md) — the core surface everything else feeds.
3. [TECH_STACK_AND_INFRASTRUCTURE.md](model_output_docs/TECH_STACK_AND_INFRASTRUCTURE.md) — stack + backend module layout.
4. Whichever domain doc matches the system you're touching.
