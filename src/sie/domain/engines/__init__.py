"""Analysis engines (deterministic, no I/O)."""

from sie.domain.engines.content_comparison import compare_content, find_duplicate_groups
from sie.domain.engines.content_intelligence import analyze_content, analyze_content_batch
from sie.domain.engines.diagnosis import run_diagnosis
from sie.domain.engines.industry_synthesis import (
    generate_industry_intelligence,
    synthesize_industry_findings,
)
from sie.domain.engines.link_graph import (
    build_architecture_report,
    build_link_graph,
    compute_pagerank,
)
from sie.domain.engines.search_analytics import (
    analyze_search_dataset,
    calculate_competitor_metrics,
    calculate_dataset_metrics,
    calculate_keyword_metrics,
    calculate_visibility_score,
)
from sie.domain.engines.search_casino import (
    analyze_casino_content,
    classify_casino_intent,
    detect_casino_content_gaps,
    detect_casino_entity_gaps,
    extract_casino_entities,
)
from sie.domain.engines.search_crypto import (
    analyze_crypto_content,
    classify_crypto_intent,
    detect_crypto_content_gaps,
    detect_crypto_entity_gaps,
    extract_crypto_entities,
)
from sie.domain.engines.search_crypto_casino import (
    analyze_crypto_casino_intersections,
    classify_crypto_casino_intent,
    detect_crypto_casino_opportunities,
    identify_crypto_casino_entities,
)
from sie.domain.engines.search_entity import (
    analyze_entity_visibility,
    detect_entity_gaps,
    extract_entities_from_content,
)
from sie.domain.engines.search_optimization import synthesize_optimization_recommendations
from sie.domain.engines.search_performance import (
    analyze_dataset_performance,
    analyze_page_performance,
)
from sie.domain.engines.search_report import generate_intelligence_report
from sie.domain.engines.technical_seo import run_technical_audit

# Backward-compatible name used by the site-analysis orchestration layer.
# Keep the canonical implementation named ``extract_entities_from_content``.
from sie.domain.engines import search_entity as _search_entity

if not hasattr(_search_entity, "extract_entities"):
    _search_entity.extract_entities = extract_entities_from_content

__all__ = [
    "analyze_casino_content",
    "analyze_content",
    "analyze_content_batch",
    "analyze_crypto_casino_intersections",
    "analyze_crypto_content",
    "analyze_dataset_performance",
    "analyze_entity_visibility",
    "analyze_page_performance",
    "analyze_search_dataset",
    "build_architecture_report",
    "build_link_graph",
    "calculate_competitor_metrics",
    "calculate_dataset_metrics",
    "calculate_keyword_metrics",
    "calculate_visibility_score",
    "classify_casino_intent",
    "classify_crypto_casino_intent",
    "classify_crypto_intent",
    "compare_content",
    "compute_pagerank",
    "detect_casino_content_gaps",
    "detect_casino_entity_gaps",
    "detect_crypto_casino_opportunities",
    "detect_crypto_content_gaps",
    "detect_crypto_entity_gaps",
    "detect_entity_gaps",
    "extract_casino_entities",
    "extract_crypto_entities",
    "extract_entities_from_content",
    "find_duplicate_groups",
    "generate_industry_intelligence",
    "generate_intelligence_report",
    "identify_crypto_casino_entities",
    "run_diagnosis",
    "run_technical_audit",
    "synthesize_industry_findings",
    "synthesize_optimization_recommendations",
]
