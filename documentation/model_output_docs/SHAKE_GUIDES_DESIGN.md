# Shake Guides Design

**What this doc is for:** A dedicated feature for the collector technique of identifying a blind-boxed figure *before* opening it — weight, sound, and box-marking tells. This is a first-class content type (🎲 in the feed, own tab in [FEED_SYSTEM_DESIGN.md](FEED_SYSTEM_DESIGN.md)), not a one-off article. Edit this doc if guide structure, contribution/voting rules, or the disclaimer policy changes.

---

## Why This Is Its Own System

Pop Mart blind boxes don't reveal contents, so collectors have long relied on physical tells — box weight, rattle sound, sticker/seam patterns, printed box codes — to guess what's inside before buying. This knowledge currently lives scattered across TikTok comments, Reddit threads, and Discord pins, is series-specific, goes stale the moment a new series drops, and is never verified against itself. PoopMart is positioned to become the durable, structured, crowd-verified home for it — same treatment as price data, not a buried blog post.

---

## Disclaimer & Etiquette (must ship with the feature, not bolted on later)

- Techniques are **crowd-sourced folklore, not guaranteed** — every guide surfaces a confidence score (see below), never a claim of certainty.
- Some retailers discourage or prohibit shaking/handling sealed boxes in-store. Every guide detail view carries a short, non-preachy etiquette note: *"Some stores don't allow box handling — check before you shake, and always be gentle."*
- Guides describe **non-destructive** techniques only (weight, sound, printed markings). Anything that damages packaging or defeats a physical security seal is out of scope and is a moderation removal reason, not a gray area.

---

## Technique Types

| Type | What it captures |
|------|-------------------|
| ⚖️ Weight | Gram-range signatures per figure within a series, crowd-measured on a kitchen scale. |
| 🔊 Sound / Rattle | Description of rattle character (silent, single click, loose rattle, etc.) tied to specific figures — often correlated with accessory pieces inside. |
| 🔢 Box Code | Publicly printed box/batch codes or barcodes collectors have correlated to specific figures for a given series (only where Pop Mart's own printed codes are the source — not anything requiring tampering). |
| ✂️ Seam / Sticker Pattern | Visual tells in seal sticker placement or box seam that vary by figure. |

A single `ShakeGuide` (scoped to one series) can carry multiple technique types — most useful guides combine weight + sound.

---

## Structure of a Guide

```
ShakeGuide
  - series_id                     # one guide per series
  - technique_summary              # AI-assisted synthesis of contributions, see AI_INTELLIGENCE_DESIGN.md
  - figure_signatures: [
      {
        figure_id,
        weight_range_g,            # crowd-measured, min/max
        sound_description,
        distinguishing_notes,
        confidence_score           # derived from contribution count + agreement
      },
      ...
    ]
  - contributions: [GuideContribution]
  - etiquette_note                 # standard disclaimer, always present
```

```
GuideContribution
  - user_id
  - figure_signature_claim         # what they measured/observed
  - upvotes / downvotes
  - video_url (optional)           # demonstration clip
  - created_at
```

## Confidence Scoring

A figure signature's `confidence_score` grows with agreeing independent contributions and shrinks with disputes — the same shape as the price-confidence band in [PRICE_TRACKING_DESIGN.md](PRICE_TRACKING_DESIGN.md). A signature backed by 2 contributions should never visually read the same as one backed by 40.

## Contribution & Moderation Flow

1. Any user can submit a `GuideContribution` for a series they own/have measured.
2. Community voting (upvote/downvote) surfaces the most reliable claims; the `technique_summary` is periodically re-synthesized from current top contributions (see [AI_INTELLIGENCE_DESIGN.md](AI_INTELLIGENCE_DESIGN.md)).
3. Contributions that violate the non-destructive scope above are removed by moderation, independent of vote count.
4. Guides go stale on new series drops — a `ShakeGuide` starts with zero contributions and an explicit "not enough data yet" state rather than inheriting anything from a prior series.

## Surfaces

- **Feed card (🎲):** fires when a guide for a newly-dropped series crosses a minimum contribution threshold, or when an existing guide's summary meaningfully changes.
- **Guides tab:** browsable by series, searchable (see [SEARCH_DESIGN.md](SEARCH_DESIGN.md)), sorted by confidence/recency.
- **Figure page:** a figure's page links to its series' Shake Guide.

---

## Open Questions

- Should video demonstration clips be hosted natively or embedded from source platform (TikTok/YouTube)?
- Does a `GuideContribution` need photo/scale-reading proof to count toward confidence, or is a text claim + community vote enough for v1?
- Badge/reputation tie-in: does reliably contributing to Shake Guides earn a collector badge (see [USER_PROFILES_AND_SOCIAL_DESIGN.md](USER_PROFILES_AND_SOCIAL_DESIGN.md))?
