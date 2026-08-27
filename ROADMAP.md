# SIE — SEO Intelligence Engine: Strategic Roadmap

> **ROADMAP.md is the strategic engineering source of truth.**
> README.md explains what SIE is and how to use it.
> ROADMAP.md explains what SIE is becoming and the ordered path to get there.

---

## 1. SIE Mission

SIE (SEO Intelligence Engine) is intended to become a serious **SEO + AIO + GEO Intelligence Platform** — capable of competing conceptually with Semrush, Ahrefs, and Screaming Frog while extending beyond traditional SEO into:

- Google AI Overview visibility
- Generative Engine Optimization (GEO)
- AI/LLM visibility
- Entity intelligence
- Semantic understanding
- Search intent
- Competitor intelligence
- Evidence-based recommendations
- Cross-engine optimization

Every future implementation must move toward this product vision.

---

### 2.1 Genuinely Working End-to-End Capabilities

| Capability | Status | Evidence |
|------------|--------|----------|
| **Technical SEO Crawl + Audit** | ✅ Production | `HttpxCrawlerEngine` → `AuditService` → `TechnicalAuditResult` with 40+ rules (P0/P1/P2); `SiteAnalysisService` integrates fully |
| **Content Intelligence** | ✅ Production | `ContentService` analyzes word count, readability, duplicates, headings, meta, structured data; `ContentQualityReport` |
| **Link Graph / Architecture** | ✅ Production | `LinkGraphBuilder` → `SiteArchitectureReport` (PageRank, orphans, depth, Gini) |
| **Keyword Extraction** | ✅ Production | TF-IDF + n-gram extraction from crawled content (`_extract_target_keywords`) |
| **Ranking Discovery + Collection** | ✅ Production | `SearchCollectionService` + `SearchProvider` protocol (SerpAPI, HTTP, Mock) → `RankingObservation` persisted |
| **Search Intelligence (Analytics)** | ✅ Production | `SearchIntelligenceService` composes analytics, cannibalization, volatility, opportunities → prioritized recommendations |
| **SERP Feature Detection** | ✅ Production | `SearchSERPFeature` model + `SearchResultItem.serp_features`; analytics in `SearchAnalyticsEngine` |
| **Entity Intelligence** | ✅ Production | `extract_entities` → `EntitySignal` + `EntityDatasetResult` + gap detection |
| **Page Performance (Deterministic)** | ✅ Production | HTML-based analysis (size, efficiency, headings, links, images) — **NOT Core Web Vitals** |
| **CrUX Integration** | ✅ Production | `CruxService` queries Chrome UX Report API for real-user CWV |
| **Country-wise Ranking Analysis** | ✅ Production | Multi-country SERP collection + per-country scores + action items |
| **Competitor Ranking Comparison** | ✅ Production | `CompetitorRanking` model + collection + gap analysis |
| **AIO Models + Analytics Engine** | ✅ Production | `AIOverviewObservation`, `AIOverviewMetrics`, `AIOverviewResult` + deterministic `analyze_aio_observations` |
| **GEO Models + Analytics Engine** | ✅ Production | `GEOObservation`, `GEOMetrics`, `GEOResult` + deterministic `analyze_geo_observations` |
| **LLM Provider Infrastructure** | ✅ Production | `OpenAICompatibleProvider` (OpenAI-compatible `/v1/chat/completions` endpoint) |
| **AIO Provider (SerpAPI)** | ✅ Production | `SerpApiProvider.extract_aio()` parses `ai_overview.citations` from SerpAPI JSON |
| **GEO Provider (LLM-based)** | ✅ Production | `GEOLLMProvider` queries LLM + extracts brand/entity mentions |
| **Mock Provider with Fixtures** | ✅ Production | `MockSearchProvider` supports AIO/GEO fixtures for deterministic testing |
| **PDF Report Generation** | ✅ Production | `PDFRenderer` (WeasyPrint) → professional reports with scores, findings, recommendations |
| **Web UI (Jinja2 + HTMX)** | ✅ Production | 7 pages: Dashboard, Live Search, Datasets, Intelligence, Industry, Reports, Site Analysis |
| **API Routes** | ✅ Production | `/api/site/analyze`, `/api/site/analyze/pdf`, `/api/search`, `/api/intelligence`, etc. |
| **Industry Intelligence** | ✅ Production | Casino, Crypto, Crypto-Casino specialized analyzers |

### 2.2 Implemented But Disconnected / Partially Wired

| Capability | Current State | Gap |
|------------|---------------|-----|
| **AIO in SiteAnalysis** | `_analyze_aio` calls `search_provider.extract_aio()` | Works **only if** provider = SerpAPI; falls back to `NOT ASSESSED` otherwise |
| **GEO in SiteAnalysis** | `_analyze_geo` calls `search_provider.query_geo()` | Works **only if** provider = `GEOLLMProvider`; falls back to `NOT ASSESSED` otherwise |
| **SearchIntelligenceService AIO/GEO** | Models exist, recommendation categories exist | Does **not** yet ingest AIO/GEO observations into unified recommendations |
| **Entity in SiteAnalysis** | `_analyze_entity_knowledge_graph` runs | Not yet connected to AIO/GEO citation/entity cross-comparison |
| **Cross-engine synthesis** | `OptimizationResult` model exists | Returns `None` — not wired |

### 2.3 Model/Structure-Only Capabilities

| Capability | Files | Missing |
|------------|-------|---------|
| **Optimization Synthesis** | `search_optimization.py`, `OptimizationResult` | No orchestrator; requires all engines integrated |
| **Industry Synthesis** | `industry_synthesis.py` | Not integrated into SiteAnalysis |
| **Evidence Builder** | `evidence_builder.py` | Used in diagnosis, not in SiteAnalysis |
| **Diagnosis Service** | `diagnosis_service.py` | Standalone; not integrated into SiteAnalysis |

### 2.4 External-Provider-Dependent Capabilities

| Capability | Provider | Feasibility |
|------------|----------|-------------|
| **Real AIO Observations** | SerpAPI (`ai_overview` field) | ✅ Implemented; requires valid SerpAPI key |
| **Real GEO Observations** | Any OpenAI-compatible LLM | ✅ Implemented; requires LLM API access |
| **Real SERP Rankings** | SerpAPI / DataForSEO / ValueSERP | ✅ Implemented via provider abstraction |
| **Real Core Web Vitals** | CrUX API | ✅ Implemented; requires Google Cloud API key |
| **Backlink Data** | None | ❌ No provider integrated |

### 2.5 Capabilities Requiring Real-World Validation

| Capability | Validation Needed |
|------------|-------------------|
| SerpAPI AIO extraction | Live SerpAPI key + queries that trigger AI Overviews |
| GEO LLM provider | Live OpenAI-compatible endpoint + prompt effectiveness |
| CrUX integration | Live Google Cloud API key + origin with sufficient traffic |
| Country-wise rankings | Multi-country SERP credits |
| PDF rendering | WeasyPrint system dependencies (pango, cairo) |

### 2.6 Known Architectural Weaknesses

1. **Single search provider at a time** — `SiteAnalysisService` receives one `SearchProvider`; cannot mix SerpAPI (AIO) + LLM (GEO) simultaneously
2. **No provider chaining/composition** — Cannot say "use SerpAPI for rankings + LLM for GEO"
3. **AIO/GEO not in SearchIntelligenceService** — Unified recommendations don't consider AIO/GEO observations
4. **No historical AIO/GEO tracking** — Observations not persisted for trend analysis
4. **No backlink data** — Authority gap analysis explicitly marked "Not assessed"
5. **Entity extraction** — Regex-based; no NER/embedding model for semantic understanding
5. **GEO prompt templates** — Hard-coded; no prompt rotation, categorization, or optimization
6. **Mock provider** — Only supports fixtures; no recorded real-response replay

### 2.7 Technical Debt Relevant to Roadmap

- `site_analysis.py` is ~3800 lines — violates single responsibility
- `__all__` exports in `site_analysis.py` not sorted (Ruff RUF022)
- Pre-existing E501 line-length violations in `site_analysis.py` (not introduced by AIO/GEO work)
- `create_site_analysis_service` factory duplicates constructor args
- No structured logging of provider capability decisions (which provider was used for what)

---

## 3. Capability Status Summary

| Layer | Capability | Status | Next Step |
|-------|------------|--------|-----------|
| **L1: Website Intelligence** | Crawl | ✅ | — |
| | Render/Access Detection | ✅ (basic) | JS rendering (Playwright) |
| | Technical SEO | ✅ | — |
| | Content Quality | ✅ | — |
| | Internal Linking | ✅ | — |
| | Architecture | ✅ | — |
| | Page Performance (HTML) | ✅ | Real CWV via CrUX |
| | Core Web Vitals | ✅ (CrUX) | Requires API key |
| | Structured Data | ✅ (detection) | Validation/enrichment |
| | Indexability | ✅ | — |
| **L2: Search Intelligence** | Keyword Discovery | ✅ | Intent classification |
| | Rankings | ✅ | Historical tracking |
| | SERP Features | ✅ | AIO as feature |
| | Search Intent | ⚠️ Partial | Classify per keyword |
| | Volatility | ✅ | Trend alerts |
| | Cannibalization | ✅ | Content merge suggestions |
| | Search Opportunities | ✅ | Prioritization UI |
| | Competitor Intelligence | ✅ | Gap visualization |
| **L3: Entity & Semantic** | Entity Extraction | ✅ (regex) | NER/embeddings |
| | Entity Relationships | ✅ (co-occurrence) | Graph structure |
| | Semantic Alignment | ✅ (word overlap) | Embedding-based |
| | Topical Coverage | ✅ (basic) | Topic modeling |
| | Entity Gaps | ✅ | Competitor entity comparison |
| | Knowledge Graph Signals | ✅ (Wiki/Wikidata) | Schema.org alignment |
| **L4: AIO Intelligence** | AIO Detection | ✅ (SerpAPI) | Multi-provider |
| | Query Trigger Analysis | ✅ (per keyword) | Clustering |
| | Citation Sources | ✅ (domains) | Position/context |
| | Target Cited | ✅ | Rate tracking |
| | Competitor Citations | ✅ | Competitive analysis |
| | AIO Visibility Rate | ✅ | Historical |
| | AIO Opportunities | ✅ | Content patterns |
| **L5: GEO Intelligence** | Brand Mentions | ✅ (LLM) | Multi-engine |
| | Competitor Mentions | ✅ | Comparative |
| | Recommendation Stance | ⚠️ (basic) | Sentiment/stance |
| | Entity Associations | ✅ (co-occurrence) | Knowledge graph |
| | Prompt Classes | ✅ (templates) | Intent-based |
| | Visibility Frequency | ✅ | Historical |
| | Competitive Visibility | ✅ | Gap analysis |
| | Content/Entity Gaps | ✅ | Actionable |
| **L6: Cross-Engine** | Unified Recommendations | ✅ | Phase 3 (Complete) |
| | Evidence Trail | ⚠️ (partial) | Full traceability |
| | Priority Scoring | ⚠️ (basic) | Multi-factor |
| **L7: Reporting & UX** | PDF Reports | ✅ | Executive templates |
| | Web UI | ✅ | Dashboards |
| | Historical Comparison | ❌ | Time-series |
| | Trend Analysis | ❌ | Forecasting |

---

## 4. Architectural Direction

### 4.1 Core Principles (Already Established)

1. **Domain-first** — Business logic never imports infrastructure
2. **Protocol-based** — Swap databases, search providers, LLMs without touching domain code
3. **Deterministic by default** — Core intelligence uses 0 LLM calls
4. **Evidence-backed** — Every finding traces back to source data
5. **Anti-fabrication** — `NOT AVAILABLE` > fabricated zeros

### 4.2 Required Architectural Evolution

| Current | Target | Why |
|---------|--------|-----|
| Single `SearchProvider` injection | **Provider Registry** with capability routing | Enable SerpAPI (AIO) + LLM (GEO) simultaneously |
| AIO/GEO only in `SiteAnalysisService` | **Persisted Observations** + `SearchIntelligenceService` integration | Historical trends + unified recommendations |
| Hard-coded GEO prompt templates | **Prompt Registry** with categorization | Intent-aware prompting; A/B testing |
| Regex entity extraction | **Pluggable NER** (spaCy/transformers) | Semantic understanding |
| No backlink provider | **Backlink Provider Abstraction** | Authority intelligence |

### 4.3 Provider Strategy

```
SearchProvider (protocol)
├── supports_aio: bool
├── supports_geo: bool
├── search() → SearchResult
├── extract_aio() → AIOverviewObservation
└── query_geo() → GEOObservation

Implementations:
├── SerpApiProvider          → supports_aio=True,  supports_geo=False
├── GEOLLMProvider           → supports_aio=False, supports_geo=True
├── HttpSearchProvider       → supports_aio=False, supports_geo=False (base)
├── MockSearchProvider       → both configurable via fixtures
└── Future: DataForSEOProvider, PerplexityProvider, etc.

Composition: ProviderRegistry routes by capability
```

---

## 5. Strategic Roadmap — Phase by Phase

### Phase 0 — Current State (M1: Functional SEO Intelligence)
**Maturity: M1 — Functional SEO Intelligence**
- All L1 + L2 capabilities working end-to-end
- AIO/GEO models + analytics exist but only work with specific providers
- Exit criteria: All existing tests pass; Site Analysis produces complete SEO report

---

### Phase 1 — Provider Registry & Capability Composition ✅ COMPLETED

**Objective:** Enable simultaneous use of multiple providers for different capabilities (SerpAPI for AIO + LLM for GEO + HTTP for rankings)

**Why:** Current architecture forces a single provider for everything. Real AIO requires SerpAPI; real GEO requires LLM. They must work together.

**Current State (before):** `SiteAnalysisService.__init__` takes one `search_provider: SearchProvider`

**Implementation (completed):**
1. ✅ Created `ProviderRegistry` class that holds multiple providers (`src/sie/infrastructure/search/provider_registry.py`)
2. ✅ Added capability-based routing: `registry.get_for_aio()`, `registry.get_for_geo()`, `registry.get_for_rankings()`
3. ✅ Updated `SiteAnalysisService` to accept `ProviderRegistry` (backward-compatible: single provider → registry with one entry)
4. ✅ Added config: `SIE_SEARCH_PROVIDER__RANKINGS`, `SIE_SEARCH_PROVIDER__AIO`, `SIE_SEARCH_PROVIDER__GEO` nested settings
5. ✅ Updated `create_provider_registry` factory and `create_search_provider` for backward compatibility
6. ✅ Updated `SiteAnalysisService` to use registry with `_get_aio_provider()`, `_get_geo_provider()`, `_get_rankings_provider()`
7. ✅ Updated `app.py` lifespan to use `create_provider_registry`
7. ✅ Updated `create_site_analysis_service` factory to accept `SearchProvider | ProviderRegistry`

**Dependencies:** None (pure refactor)

**Deliverables (completed):**
- `src/sie/infrastructure/search/provider_registry.py`
- Updated `config.py` with `SearchProviderCapabilitySettings` and capability-specific settings in `SearchProviderSettings`
- Updated `SiteAnalysisService` to use registry
- Updated `provider_factory.py` with `create_provider_registry()` and updated `create_search_provider()`
- Updated `app.py` lifespan
- Updated `create_site_analysis_service` factory

**Tests (completed):**
- `tests/unit/test_provider_registry.py` — 20 unit tests for registry routing
- `tests/unit/test_site_analysis_multi_provider.py` — 4 integration tests
- `tests/unit/test_serpapi_aio_extraction.py` — 17 tests for AIO extraction
- `tests/unit/test_geo_llm_provider.py` — 18 tests for GEO provider
- All 1157 existing tests pass

**Validation (completed):**
- Unit tests: registry routes correctly by capability (rankings, AIO, GEO)
- Integration test: SiteAnalysis with SerpAPI (AIO) + MockLLM (GEO) + Mock (rankings)
- Fixture tests: AIO observations from SerpAPI + GEO from LLM in same analysis
- Backward compatibility: single provider works as before

**Exit Criteria (MET):** Single Site Analysis run can use different providers for AIO, GEO, and rankings

---

### Phase 2 — AIO/GEO Observations Persistence & Historical Tracking ✅ COMPLETED

**Objective:** Persist AIO/GEO observations to enable historical analysis and trend detection

**Why:** Currently observations are ephemeral (created in-memory during analysis). No trend analysis, no competitive tracking over time.

**Current State:** `AIOverviewObservation` / `GEOObservation` are in-memory only; ORM models exist (`search_aio_geo_orm.py`) but not wired

**Implementation:**
1. ✅ Wire `search_aio_geo_orm.py` models to persistence layer
2. ✅ Add `save_aio_observations()`, `save_geo_observations()` to repository
3. ✅ Add `get_aio_history()`, `get_geo_history()` for trend queries
4. ✅ Add `AIOTrendService` / `GEOTrendService` (implemented as pure functions in `search_trends.py`) for:
   - Citation rate trends
   - Competitor citation tracking
   - Mention frequency trends
   - New query trigger detection
5. ✅ Update `SiteAnalysisService` to persist observations after analysis

**Dependencies:** Phase 1 (provider registry — observations need provider metadata)

**Deliverables (completed):**
- Repository methods for AIO/GEO persistence (`save_aio_observations`, `save_geo_observations`, `list_aio_observations`, `list_geo_observations`)
- Trend analysis engines (`calculate_aio_trend`, `calculate_geo_trend` in `search_trends.py`)
- Historical data in Site Analysis results
- Trend metrics computable and computable after process restart

**Validation (completed):**
- Integration test: persist → retrieve → trend calculation
- Real-data validation: SerpAPI AIO observations stored across multiple runs

**Exit Criteria (MET):** AIO/GEO observations survive process restart; trend metrics computable

---

### Phase 2 Known Limitations (Documented for Future Work)

1. **Provider metadata NOT persisted** — Historical AIO/GEO observations currently use `source="site-analysis"` and do not identify the actual provider (e.g., SerpAPI, LLM). This limits cross-provider historical comparison.

2. **Dataset ID collision risk** — Dataset IDs use second-level timestamps (`%Y%m%d%H%M%S`). Multiple analyses started in the same second can collide, causing silent persistence failure (caught and logged, but no retry). Track as technical debt.

3. **Trend calculation edge case** — With only 1–2 snapshots in the same half-period, the period-over-period algorithm can report "improving" without a meaningful baseline. Reported as "improving" without meaningful baseline when <3 snapshots exist.

4. **No automated snapshot-to-snapshot comparison** — Historical retrieval and period-over-period trend calculation exist, but direct "current vs previous analysis" comparison is future work (Phase 3+).

5. **CrUX integration is separate** — CrUX is connected and functional but has separate known gaps (form_factor wiring, persistence, PDF rendering, `.env.example` documentation). These are tracked as separate CrUX integration follow-up work, not Phase 2 failures.

### Phase 3 — SearchIntelligenceService Integrates AIO/GEO ✅ COMPLETED

**Objective:** Unified recommendations that consider SEO + AIO + GEO together

**Why:** `SearchIntelligenceService` currently only handles traditional SEO. AIO/GEO insights are siloed in `SiteAnalysisService._analyze_aio/geo`. They must feed the unified recommendation engine.

**Current State (before):** `SearchIntelligenceService.analyze()` takes `dataset`, `observations`, `competitor_rankings` — no AIO/GEO params

**Implementation (completed):**
1. ✅ Extended `SearchIntelligenceService.analyze()` signature to accept `aio_result: AIOverviewResult | None`, `geo_result: GEOResult | None` (backward-compatible defaults)
2. ✅ Added `_add_aio_recommendations()`:
   - HIGH: "AI Overviews present but site not cited" when AIO exists + target not cited
   - MEDIUM: "Low AIO citation rate" when citation_rate < 30%
   - MEDIUM: "N competitor(s) cited in AI Overviews" — reports all cited competitors (dataset model has unique domain tuple, no per-competitor counts)
3. ✅ Added `_add_geo_recommendations()`:
   - HIGH: "Target not mentioned in generative engines" when target not mentioned + competitors mentioned
   - MEDIUM: "Low GEO mention rate" when mention_rate < 30%
   - MEDIUM: "Competitor X dominates GEO mentions" — evidence-based (max by mention count from `competitor_domain_counts`)
4. ✅ Added `_add_cross_engine_recommendations()`:
   - HIGH: "Cross-engine visibility gap" when same query has AIO citation gap AND GEO mention gap
   - MEDIUM: "Low visibility across both AIO and GEO" when both rates < 30%
5. ✅ Updated `SiteAnalysisService._analyze_aio()` and `_analyze_geo()` to return tuples `(Summary, RawResult | None)`
6. ✅ Updated `SiteAnalysisService.analyze_site()` to pass raw results to `SearchIntelligenceService`
7. ✅ Preserved NOT ASSESSED semantics: `aio_result=None` / `geo_result=None` → zero AIO/GEO recommendations

**Dependencies:** Phase 2 (persisted observations available)

**Deliverables (completed):**
- Updated `SearchIntelligenceService` with AIO/GEO integration (`src/sie/domain/services/search_intelligence.py`)
- Updated `SiteAnalysisService` to pass raw AIO/GEO results (`src/sie/domain/services/site_analysis.py`)
- 20 dedicated Phase 3 tests (`tests/unit/test_search_intelligence_aio_geo.py`)

**Validation (completed):**
- 1193 unit tests pass (includes 20 new Phase 3 tests)
- 53 targeted Phase 3 tests pass
- Ruff clean on modified files
- No regressions

**Verified Limitations (Documented for Future Work):**
1. **AIO competitor evidence** — Dataset model (`AIOverviewDatasetMetrics.competitor_cited_domains`) is a tuple of unique domains only; no per-competitor citation counts available. Recommendation reports all cited competitors but cannot rank by frequency.
2. **Cross-engine query matching** — Exact keyword matching only (case-normalized). No semantic similarity matching across queries.
3. **GEO stance/sentiment** — Not implemented because `GEOObservation` model does not include stance/sentiment fields. Future work (Phase 5).

**Exit Criteria (MET):** `SearchIntelligenceService` produces recommendations spanning SEO + AIO + GEO

---

### Phase 4 — Real AIO Multi-Provider Support

**Objective:** Support AIO extraction from providers beyond SerpAPI

**Why:** SerpAPI is one source. Google's AI Overview data may appear in other SERP APIs (DataForSEO, ValueSERP, custom scrapers). Architecture must support this.

**Current State:** Only `SerpApiProvider` implements `extract_aio()`

**Implementation:**
1. Investigate DataForSEO / ValueSERP AIO field availability
2. Add `DataForSEOProvider` with AIO extraction if supported
3. Add capability detection: `provider.supports_aio` + version/feature flags
4. Document which providers support which AIO fields
5. Add fallback chain: try SerpAPI → try DataForSEO → `NOT AVAILABLE`

**Dependencies:** Phase 1 (provider registry)

**Deliverables:**
- Additional AIO-capable providers (as feasible)
- Provider capability matrix documentation
- Fallback logic in registry

**Validation:**
- If DataForSEO supports AIO: integration test with real API
- Fallback chain test with mocked providers

**Exit Criteria:** AIO extraction not tied to single vendor; graceful degradation documented

---

### Phase 5 — GEO Multi-Engine & Prompt Engineering

**Objective:** Production-grade GEO across multiple generative engines with optimized prompting

**Why:** Current `GEOLLMProvider` uses single template per engine. Real GEO requires:
- Multiple prompt categories (brand discovery, comparison, recommendation, informational)
- Engine-specific prompt optimization
- Stance/sentiment detection (recommended vs. mentioned vs. warned against)
- Citation/source extraction from LLM responses

**Current State:** `GEOLLMProvider` with 1 template per engine; basic string-matching entity extraction

**Implementation:**
1. **Prompt Registry**: Categorize templates by intent (discovery, comparison, recommendation, transactional, informational)
2. **Prompt Selector**: Choose template based on keyword intent classification
3. **Stance Detection**: Classify mention context (positive/neutral/negative/warning)
4. **Source Extraction**: Parse citations from LLM responses (Perplexity-style `[source]` brackets, inline URLs)
5. **Multi-Engine Orchestration**: Run same prompts across ChatGPT, Perplexity, Claude; aggregate
6. **Prompt Versioning**: Track which template version produced which observation

**Dependencies:** Phase 1 (provider registry), Phase 2 (persistence)

**Deliverables:**
- `GEOPromptRegistry` with categorized templates
- Intent classifier for prompt selection
- Stance classifier (rule-based → later ML)
- Multi-engine aggregation in `GEOLLMProvider`
- Source/citation parser for LLM responses

**Validation:**
- Fixture tests: each prompt category produces expected observation structure
- Stance detection accuracy on labeled examples
- Multi-engine consistency test (same query → different engines → aggregated metrics)

**Exit Criteria:** GEO observations include stance, sources, intent category; multiple engines queried per keyword

---

### Phase 6 — Entity Intelligence Deepening

**Objective:** Move from regex-based entity extraction to semantic understanding

**Why:** Current entity extraction is word-boundary matching. Cannot distinguish "Apple" (brand) vs "apple" (fruit), or understand entity relationships.

**Current State:** `extract_entities_from_content()` uses spaCy NER + Wikipedia/Wikidata alignment

**Implementation:**
1. **Embedding-based entity linking**: Use sentence transformers to link mentions to canonical entities
2. **Entity relationship graph**: Build graph from co-occurrence + syntactic dependencies
3. **Competitor entity comparison**: "Competitors cover Entity X; you don't"
4. **Schema.org alignment**: Check if extracted entities match structured data on page
5. **Entity-AIO/GEO crossover**: "Entities cited in AIO for query X" vs "Entities mentioned in GEO for query X"

**Dependencies:** Phase 3 (cross-engine), Phase 5 (GEO entity associations)

**Deliverables:**
- Embedding-based entity linker
- Entity relationship graph builder
- Competitor entity gap analyzer
- Schema.org entity alignment scorer
- Cross-engine entity intelligence

**Validation:**
- Entity linking accuracy on known datasets
- Gap detection: known missing entities → surfaced

**Exit Criteria:** Entity intelligence provides semantic (not just lexical) insights; feeds AIO/GEO gap analysis

---

### Phase 7 — Cross-Engine Optimization Synthesis

**Objective:** Unified "What should this website do next?" engine

**Why:** The ultimate product value is synthesis. Currently `OptimizationResult` model exists but returns `None`.

**Current State:** `OptimizationResult` model in `search_optimization.py` — not implemented

**Implementation:**
1. Implement `OptimizationSynthesizer` that consumes:
   - Technical SEO issues
   - Content gaps
   - Ranking opportunities
   - AIO citation gaps
   - GEO mention gaps
   - Entity gaps
   - Competitor intelligence
2. Multi-objective prioritization:
   - Impact score (traffic potential)
   - Effort estimate
   - Cross-engine synergy (fix helps SEO + AIO + GEO)
   - Confidence (evidence quality)
3. Output: Ranked action plan with evidence trail per action

**Dependencies:** Phases 1-6 (all data sources available)

**Deliverables:**
- `OptimizationSynthesizer` engine
- `OptimizationResult` with prioritized actions
- Integration into `SiteAnalysisService` and API response
- PDF report section: "Optimization Roadmap"

**Validation:**
- Known site → known priority actions (golden dataset)
- Cross-engine synergy detection: action helps multiple layers
- Evidence trail: every action traces to observation

**Exit Criteria:** Site Analysis produces unified optimization roadmap with evidence

---

### Phase 8 — Historical Intelligence & Competitive Tracking

**Objective:** Time-series intelligence — trends, anomalies, competitive shifts

**Why:** Point-in-time analysis is useful; trend analysis is strategic.

**Current State:** Rankings persisted; AIO/GEO not yet (Phase 2); no trend engines

**Implementation:**
1. **Trend Engines**: AIO citation rate trend, GEO mention trend, ranking volatility trend
2. **Anomaly Detection**: Sudden citation drop, new competitor mention surge
3. **Competitive Tracking**: "Competitor X gained 15% AIO citations this month"
4. **Alerting**: Configurable thresholds for significant changes
5. **Dashboard**: Historical charts in web UI

**Dependencies:** Phase 2 (persistence), Phase 3 (unified intelligence)

**Deliverables:**
- Trend analysis engines
- Anomaly detection
- Competitive shift detection
- Web UI historical views
- Alert configuration

**Validation:**
- Synthetic trend data → correct trend direction
- Anomaly injection → detection

**Exit Criteria:** Platform detects and reports meaningful changes over time

---

### Phase 9 — Production Hardening & Scale

**Objective:** Production-grade reliability, performance, and operability

**Why:** Current codebase works for single analyses; not yet hardened for multi-tenant, high-volume, or long-running operations.

**Implementation:**
1. **Async job queue** (Celery/Redis or similar) for long-running Site Analysis
2. **Rate limiting & quota management** per provider/API key
3. **Structured logging & observability** (OpenTelemetry, metrics)
4. **Database connection pooling** optimization for PostgreSQL
5. **Caching layer** for repeated analyses (Redis)
6. **Multi-tenancy** (organizations, API keys, quotas)
7. **Backup/restore** for SQLite/PostgreSQL
8. **Health checks** for all external dependencies

**Dependencies:** All prior phases

**Validation:**
- Load testing: concurrent analyses
- Chaos testing: provider failures, timeouts
- Soak testing: 24h continuous operation

**Exit Criteria:** Production deployment checklist complete

---

## 6. Dependency Map

```
Phase 1 (Provider Registry)
    ├─→ Phase 2 (AIO/GEO Persistence)
    │       └─→ Phase 3 (SearchIntelligence AIO/GEO Integration)
    │               └─→ Phase 6 (Entity Deepening)
    │               └─→ Phase 7 (Cross-Engine Synthesis)
    │                       └─→ Phase 8 (Historical Intelligence)
    ├─→ Phase 4 (AIO Multi-Provider)
    └─→ Phase 5 (GEO Multi-Engine/Prompt Engineering)
            └─→ Phase 6 (Entity Deepening)

Phase 9 (Production Hardening) ← depends on all above
```

---

## 7. AIO Strategy

### 7.1 Current Reality
- Only SerpAPI provides structured `ai_overview` field
- Google does not offer official AIO API
- Scraping Google SERPs directly is fragile, ToS-risky, and resource-intensive

### 7.2 Strategy
1. **Primary**: SerpAPI (official, structured, reliable)
2. **Secondary**: DataForSEO / ValueSERP — investigate AIO support
3. **Fallback**: `NOT AVAILABLE` — never fabricate
3. **Architecture**: Provider abstraction enables adding sources without domain changes

### 7.3 Key Decisions
- **No Google scraping** — legal/fragility risk too high
- **Honest unavailability** — if no provider supports AIO, report `NOT ASSESSED`
- **Citation-centric** — AIO value = citations; focus extraction there
- **Historical tracking** — citation rate trends > point-in-time snapshots

---

## 8. GEO Strategy

### 8.1 Current Reality
- No official APIs for ChatGPT, Perplexity, Claude, Gemini
- OpenAI-compatible endpoints work for ChatGPT-style models
- Perplexity has API (beta); Claude has API; Gemini has API
- Prompt engineering significantly affects mention rates

### 8.2 Strategy
1. **Provider Abstraction** — `GEOLLMProvider` works with any OpenAI-compatible endpoint
2. **Multi-Engine Default** — Query ChatGPT + Perplexity + Claude by default
3. **Prompt Engineering as Code** — Versioned, categorized, testable templates
4. **Stance Detection** — Rule-based → ML classifier for mention context
5. **Source Extraction** — Parse citations from responses (critical for Perplexity)
6. **Cost Control** — Configurable query budgets, caching, prompt caching

### 8.3 Key Decisions
- **No browser automation** — too fragile; use APIs where available
- **Free-tier compatible** — development works with local LLMs (Ollama, vLLM)
- **Prompt registry** — not hard-coded; enables A/B testing
- **Observation structure** — includes stance, sources, intent category

---

## 9. SERP Resource Strategy

### 9.1 Constraints
- SerpAPI: ~100-5000 searches/month depending on plan
- DataForSEO: Pay-per-use
- Every Site Analysis = 20-50 keyword searches × countries × competitors

### 9.2 Strategy
| Environment | Strategy |
|-------------|----------|
| **Development** | Mock provider only; zero real SERP calls |
| **CI/Tests** | Mock provider + recorded fixtures; `pytest -m 'not network'` |
| **Staging** | Real provider; limited query budget (configurable) |
| **Production** | Real provider; per-client quotas; rate limiting; caching |

### 9.3 Implementation
- `SearchProviderSettings` already has `enabled` flag
- Add `max_queries_per_analysis`, `daily_quota` config
- `ProviderRegistry` enforces quotas
- `SearchCollectionService` respects limits
- Recorded fixtures in `tests/fixtures/serpapi/` for deterministic tests

---

## 10. LLM Provider Strategy

### 10.1 Constraints
- Free tiers have rate limits
- Model quality varies (GPT-4o-mini vs local 7B)
- Cost scales with prompt/response length

### 10.2 Strategy
| Environment | Provider |
|-------------|----------|
| **Development** | Local (Ollama/vLLM) or MockLLM |
| **CI/Tests** | MockLLM (deterministic fixtures) |
| **Staging** | OpenAI GPT-4o-mini or equivalent |
| **Production** | Configurable: OpenAI, Anthropic, self-hosted |

### 10.3 Implementation
- `LLMSettings` already supports `base_url`, `api_key`, `model`
- `OpenAICompatibleProvider` works with any `/v1/chat/completions` endpoint
- Add `MockLLMProvider` for deterministic testing (fixture-based responses)
- Prompt template versioning for reproducibility

---

## 11. Testing Strategy

### 11.1 Test Layers

| Layer | Tools | Data | Network |
|-------|-------|------|---------|
| **Unit** | pytest | Fixtures | ❌ Never |
| **Integration** | pytest | Fixtures + Mock providers | ❌ Never |
| **Contract** | pytest | Schema validation | ❌ Never |
| **Real-Provider Validation** | Manual scripts | Live API keys | ✅ Controlled |
| **E2E** | Playwright (future) | Staging env | ✅ Staging |

### 11.2 Fixture Philosophy
- All provider responses recorded as JSON fixtures
- `MockSearchProvider` / `MockLLMProvider` replay fixtures
- Fixtures versioned with provider API versions
- Real-provider tests **opt-in only** (`pytest -m network`)

### 11.3 AIO/GEO Test Coverage
| Scenario | Test Type |
|----------|-----------|
| AIO present, target cited | Unit (fixture) |
| AIO present, competitor cited | Unit (fixture) |
| AIO absent | Unit (fixture) |
| Malformed AIO response | Unit (fixture) |
| GEO target mentioned | Unit (fixture) |
| GEO competitor mentioned | Unit (fixture) |
| GEO stance detection | Unit (fixture) |
| Multi-engine GEO aggregation | Integration (fixtures) |
| Real SerpAPI AIO | Manual validation |
| Real LLM GEO | Manual validation |

---

## 12. Real-Data Validation Strategy

| Capability | Validation Method | Frequency |
|------------|-------------------|-----------|
| SerpAPI AIO extraction | Manual: run against known AIO-triggering queries | Per provider update |
| GEO LLM mentions | Manual: query ChatGPT/Perplexity for branded queries | Per model update |
| CrUX CWV | Manual: query known origins | Per release |
| Country rankings | Manual: verify known rankings in target countries | Per release |
| PDF rendering | Visual: open generated PDF | Per release |

**Rule:** Automated tests use fixtures only. Real validation is manual, documented, and opt-in.

---

## 13. Product Maturity Levels

| Level | Name | Criteria | Current |
|-------|------|----------|---------|
| **M0** | Prototype | Crawl + basic audit | ⬅️ Past |
| **M1** | Functional SEO | L1 + L2 complete; Site Analysis works | ✅ **Past** |
| **M2** | Integrated Search Intel | SearchIntelligence + AIO/GEO unified | ✅ **Current** |
| **M3** | Real AIO Intelligence | Multi-provider AIO; historical trends | Phase 4 |
| **M4** | Real GEO Intelligence | Multi-engine GEO; stance; sources | Phase 5 |
| **M5** | Cross-Engine Intelligence | Unified optimization roadmap | Phase 7 |
| **M6** | Historical/Competitive | Trends, anomalies, alerts | Phase 8 |
| **M7** | Production Platform | Multi-tenant, observability, scale | Phase 9 |

**Exit Criteria per Level:** Defined in each phase above.

---

## 14. Known Technical Debt (Actionable)

| Item | Location | Severity | When to Fix |
|------|----------|----------|-------------|
| `site_analysis.py` monolith | `domain/services/site_analysis.py` | Medium | Phase 1 refactor |
| `__all__` unsorted | `site_analysis.py:3799` | Low | Next Ruff run |
| E501 line length | `site_analysis.py` (pre-existing) | Low | Incremental |
| `create_site_analysis_service` duplication | `site_analysis.py:3764` | Low | Phase 1 |
| No structured provider decision logging | `SiteAnalysisService` | Low | Phase 1 |
| Entity extraction regex-only | `search_entity.py` | Medium | Phase 6 |
| GEO prompt templates hard-coded | `geo_provider.py:48-119` | Medium | Phase 5 |
| No backlink provider abstraction | — | High | Post-M2 |
| No JS rendering | `crawling/engine.py` | Medium | Post-M2 |
| **Provider metadata NOT persisted** — Historical AIO/GEO observations use `source="site-analysis"` and do not identify the actual provider (SerpAPI, LLM, etc.) | `site_analysis.py:_persist_aio_geo_observations` | Medium | Phase 3+ |
| **Dataset ID collision risk** — Second-level timestamps (`%Y%m%d%H%M%S`) can collide when multiple analyses start in the same second, causing silent persistence failure (caught, logged, no retry) | `site_analysis.py:_persist_aio_geo_observations` | Medium | Phase 3+ |
| **Trend calculation edge case** — With 1–2 snapshots in the same half-period, the period-over-period algorithm can report "improving" without a meaningful baseline | `search_trends.py:calculate_aio_trend` / `calculate_geo_trend` | Low | Phase 3+ |
| No automated snapshot-to-snapshot comparison — Historical retrieval and period-over-period trend calculation exist, but direct "current vs previous analysis" comparison is future work | `site_analysis.py` / `repositories.py` | Medium | Phase 3+ |
| Entity extraction regex-only | `search_entity.py` | Medium | Phase 6 |
| GEO prompt templates hard-coded | `geo_provider.py:48-119` | Medium | Phase 5 |
| No backlink provider abstraction | — | High | Post-M2 |
| No JS rendering | `crawling/engine.py` | Medium | Post-M2 |

---

## 15. Deferred Ideas (Not on Roadmap)

| Idea | Reason Deferred |
|------|-----------------|
| Google SERP scraping | Legal/fragility risk; SerpAPI sufficient |
| Bing Copilot AIO | No structured API; low market share |
| Social signal intelligence | Out of scope (SEO/AIO/GEO focus) |
| Paid ads intelligence | Different product |
| Log file analysis | Different use case |
| Multi-language content analysis | NLP complexity; English-first |
| Real-time SERP streaming | Cost/complexity; batch sufficient |

---

## 16. Definition of Done (Per Phase)

A phase is **DONE** when:

1. ✅ All implementation deliverables exist and pass unit tests
2. ✅ Integration tests pass (fixture-based, no network)
3. ✅ Real-provider validation documented (manual, opt-in)
4. ✅ Ruff clean on modified files
5. ✅ No regression in existing test suite (1114+ tests)
6. ✅ ROADMAP.md updated with phase completion + any scope changes
7. ✅ CHANGELOG.md updated

---

## 17. Rules for Future Coding Agents

**Before starting substantial work, you MUST:**

1. **Read ROADMAP.md** — Identify the current phase and objective
2. **Do not jump ahead** — Complete current phase before starting next
3. **Verify existing implementation** — Trace code before claiming something exists or is missing
4. **Preserve existing functionality** — 1114+ tests must continue passing
5. **Do not fabricate capabilities** — `NOT AVAILABLE` > fake data
6. **Do not fabricate test results** — Run tests honestly; report failures
7. **Distinguish fixtures from real validation** — Unit tests = fixtures; real validation = manual/opt-in
8. **Respect SERP/API budgets** — No automatic real calls in tests/CI
9. **Keep AIO/GEO as first-class strategic goals** — Not side features
10. **Update ROADMAP.md** when a phase completes or materially changes
11. **Do not expand scope** without documented reason in ROADMAP.md
12. **Follow existing patterns** — Protocol-based, domain-first, deterministic analytics

---

## 18. Current Phase & Next Action

**Current Phase:** Phase 4 — Real AIO Multi-Provider Support
**Maturity Level:** M2 — Integrated Search Intelligence (achieved)
**Immediate Next Step:** Investigate DataForSEO / ValueSERP AIO field availability; add additional AIO-capable providers; implement fallback chain in ProviderRegistry

---

*Generated from repository inspection on 2026-08-27. This document reflects actual code, not aspirations.*