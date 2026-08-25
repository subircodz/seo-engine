"""Analysis engines (deterministic, no I/O)."""

from sie.domain.engines.content_comparison import compare_content, find_duplicate_groups
from sie.domain.engines.content_intelligence import analyze_content, analyze_content_batch
from sie.domain.engines.diagnosis import run_diagnosis
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

__all__ = [
    "analyze_content",
    "analyze_content_batch",
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
    "compare_content",
    "compute_pagerank",
    "detect_entity_gaps",
    "extract_entities_from_content",
    "find_duplicate_groups",
    "generate_intelligence_report",
    "run_diagnosis",
    "run_technical_audit",
    "synthesize_optimization_recommendations",
]
