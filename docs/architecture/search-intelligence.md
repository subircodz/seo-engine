# Search Intelligence Architecture

## Product boundary

SIE is a **unified search intelligence platform**, not an SEO engine with AEO/GEO add-ons.

The three supported search-visibility surfaces are first-class:

- **SEO** — traditional search visibility: rankings, SERP features, technical health, content, links, competitors, and search analytics.
- **AEO** — AI Overview visibility: AI Overview presence, target citations, cited sources, competitors, and historical visibility.
- **GEO** — generative-engine visibility: target/entity mentions, citations, competitors, answer context, and historical visibility across supported generative engines.

## Shared foundation

All three surfaces consume the same evidence-oriented foundation:

```text
Web / Search / Generative observations
                |
        Provider adapters
                |
        Raw observations
                |
        Normalization + provenance
                |
        Persistent historical data
                |
        Deterministic intelligence
                |
        SEO / AEO / GEO surfaces
                |
        Cross-surface intelligence
                |
        Recommendations / optimization
```

Surface-specific engines must not duplicate crawling, persistence, provider management, caching, provenance, or recommendation infrastructure.

## Evidence rules

A numeric zero is a real observation. Missing data is **not** a zero.

Every surface therefore exposes an explicit status:

- `ASSESSED`
- `NOT_ASSESSED`
- `INSUFFICIENT_DATA`
- `COLLECTION_FAILED`
- `STALE`

A unified score, when requested, is calculated only from assessed surfaces. Unavailable AEO/GEO data must never reduce the SEO score or be represented as a midpoint/default.

## Provider neutrality

The domain layer does not depend on SerpAPI, Google, DataForSEO, or any particular generative provider. Provider adapters collect observations; the intelligence layer reasons over normalized observations.

A provider may be unavailable because credentials are absent, quota is exhausted, or the provider does not support a capability. The system must expose that limitation rather than fabricate observations.

## Cross-surface intelligence

The platform should be able to identify relationships such as:

- ranking well in SEO but receiving poor AEO citation coverage;
- ranking well in SEO but receiving poor GEO mention coverage;
- competitors winning both AEO citations and GEO mentions;
- queries where the target is absent from both AI Overviews and generative answers;
- content/entity gaps that affect multiple search surfaces.

These are cross-surface insights, not separate SEO/AEO/GEO products.

## Implementation boundary

`SearchIntelligenceService` remains the existing deterministic search-analysis service for ranking/SERP intelligence and recommendation generation.

`UnifiedSearchIntelligenceService` is the product-level facade that converts SEO, AEO, and GEO results into a common `UnifiedSearchVisibility` envelope. It performs no network I/O and never invents unavailable data.

The architecture deliberately keeps provider integrations optional so the platform can be developed and tested without every external API credential. Real credentials activate additional evidence; they do not change the domain model.
