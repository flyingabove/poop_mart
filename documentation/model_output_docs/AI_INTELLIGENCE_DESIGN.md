# AI Intelligence Design

**What this doc is for:** The AI layer that turns raw clustered posts into readable summaries, sentiment, and figure identification. This is the primary differentiator from a plain aggregator. Edit this doc if the summarization prompt, embedding model, or vision pipeline changes.

---

## Why This Matters

Anyone can pull posts from six platforms into a list. The differentiator is turning that pile into something a human can read in five seconds:

> "Everyone is talking about the new Labubu Forest Party because supplies appear lower than expected and resale prices jumped 40% in two days."

> "Sentiment is 89% positive. Main complaints are paint defects."

---

## Components

### 1. Story Summarization (LLM)

Input: a `ClusteredStory` (see [TREND_DETECTION_DESIGN.md](TREND_DETECTION_DESIGN.md)) — a set of normalized posts about the same figure/event.

Output: a 1-3 sentence summary in the voice of a knowledgeable collector friend, not a press release. Must cite *why* something is happening when the source posts support a reason (scarcity, defect complaints, influencer push), not just *that* it's happening.

Guardrails:
- Never state a rumor as fact — leak-tier sources get hedged language ("reportedly," "collectors are speculating").
- Never fabricate a price or percentage not present in the underlying data — the summary pulls numbers from [PRICE_TRACKING_DESIGN.md](PRICE_TRACKING_DESIGN.md), it does not invent them.

### 2. Sentiment Analysis

Per-cluster sentiment score (0-100% positive) plus a short extracted list of common complaint/praise themes ("paint defects," "box damage," "great texture"). Feeds the "Reviews" tab and per-figure pages.

### 3. Embedding Model (Clustering)

Shared embedding space for post-to-post similarity, used by the clustering stage in [TREND_DETECTION_DESIGN.md](TREND_DETECTION_DESIGN.md). Must handle mixed-language input (EN/ZH/KO/JA) given the source mix (Xiaohongshu, Weibo, Reddit, etc.).

### 4. Vision Model — Figure Identification from Photos

A user uploads a photo of a figure (in-hand, on a shelf, or a sealed box). The vision model:
- Identifies the series and specific figure/colorway from an in-hand or unboxed photo.
- For sealed boxes, identifies the series and defers to [SHAKE_GUIDES_DESIGN.md](SHAKE_GUIDES_DESIGN.md) for "what might be inside" rather than claiming certainty a photo alone can't provide.

Used for: "what figure is this?" search, auto-tagging collection uploads, and verifying showcase posts actually contain what they claim.

---

## Model Choices (initial)

| Task | Approach |
|------|----------|
| Summarization / sentiment | GPT-class LLM, per [TECH_STACK_AND_INFRASTRUCTURE.md](TECH_STACK_AND_INFRASTRUCTURE.md) |
| Clustering embeddings | General-purpose multilingual embedding model |
| Vision (figure ID) | Vision-capable model, fine-tuned/prompted against a reference image set per figure |

Exact model/provider selection belongs in [TECH_STACK_AND_INFRASTRUCTURE.md](TECH_STACK_AND_INFRASTRUCTURE.md), not here — this doc owns the *pipeline*, not the vendor.

---

## Open Questions

- Reference image set for vision figure-ID: sourced from official product photos, or also crowd-sourced/verified user photos?
- Does sentiment need per-defect-category tagging (paint, box damage, missing accessory) or is a free-text theme list enough for v1?
