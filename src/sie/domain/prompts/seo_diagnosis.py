"""Versioned SEO diagnosis prompt for LLM reasoning.

This module builds the system and user prompts that instruct the LLM to
reason over deterministic Phase 5A evidence and produce structured
interpretations.  The prompt is versioned so it can evolve independently
of the engine code.
"""

from __future__ import annotations

import json

from sie.domain.models.diagnosis import DiagnosisResult
from sie.domain.models.intelligence import EvidencePackage

PROMPT_VERSION = "2.0.0"

SYSTEM_PROMPT = """\
You are an SEO diagnosis analyst. You are NOT a search engine. You do NOT \
have Google ranking data. You do NOT have access to Search Console, Bing \
Webmaster Tools, or any live ranking signals.

You must reason ONLY from the supplied evidence. Do not invent facts. Do \
not claim that an observed issue definitely caused a ranking change.

For each issue, separate:
1. Observed evidence — what was actually measured
2. Likely interpretation — what this evidence suggests
3. Recommended action — what to fix and why
4. Confidence — how certain you are (0.0 to 1.0)

Use measured language:
- "potential ranking issue"
- "SEO risk"
- "optimization opportunity"
- "technical obstacle"

Never use:
- "will drop rankings"
- "Google penalty"
- "guaranteed improvement"

You MUST respond with valid JSON matching the required schema. \
No markdown, no code fences, just raw JSON.
"""

USER_PROMPT_TEMPLATE = """\
Analyze the following SEO evidence package and produce a structured \
intelligence report.

== CRAWL STATISTICS ==
- Total pages crawled: {total_pages}
- Status distribution: {status_distribution}
- HTTP problems: {http_problems}

== TECHNICAL SEO FINDINGS ==
- Title missing: {title_missing_count}
- Title duplicates: {title_duplicate_count}
- Meta description missing: {meta_desc_missing_count}
- Canonical missing: {canonical_missing_count}
- Canonical mismatch: {canonical_mismatch_count}
- H1 missing: {h1_missing_count}
- H1 duplicates: {h1_duplicate_count}
- Noindex pages: {robots_noindex_count}
- Mixed content: {mixed_content_count}
- Large HTML: {large_html_count}
- Structured data missing: {structured_data_missing_count}
- Hreflang issues: {hreflang_issues_count}
- Issues by rule: {issues_by_rule}

== SITE ARCHITECTURE ==
- Total internal links: {total_internal_links}
- Avg links per page: {avg_links_per_page}
- Orphan pages: {orphan_count} ({orphan_urls})
- Dead-end pages: {dead_end_count} ({dead_end_urls})
- Max crawl depth: {max_depth}
- Avg crawl depth: {avg_depth}
- Thin connection pages: {thin_connection_count}
- Top PageRank pages: {pagerank_top_5}
- Bottom PageRank pages: {pagerank_bottom_5}

== CONTENT ANALYSIS ==
- Avg word count: {avg_word_count}
- Median word count: {median_word_count}
- Thin content pages: {thin_content_count} ({thin_content_urls})
- Avg quality score: {avg_quality_score}
- Quality distribution: {quality_distribution}
- Duplicate/near-duplicate pairs: {duplicate_pair_count}
- Duplicate details: {duplicate_pairs}
- Avg readability (Flesch): {avg_readability_score}
- Images without alt text: {images_without_alt_count}/{total_images}
- Top keywords: {top_keywords}
- Keyword stuffing detected: {keyword_stuffing_count} page(s)

== DIAGNOSIS SUMMARY ==
- Total deterministic issues: {diagnosis_issue_count}
- Issues by priority: {diagnosis_issues_by_priority}
- Issues by category: {diagnosis_issues_by_category}

== REQUIRED OUTPUT SCHEMA ==
{{
  "summary": "2-4 sentence executive summary of the site's SEO condition",
  "overall_assessment": "Overall assessment using OBSERVED/INFERRED/RECOMMENDED framework",
  "root_causes": [
    {{
      "title": "Group name for related issues",
      "evidence": ["Specific evidence items that form this root cause"],
      "confidence": 0.0
    }}
  ],
  "top_issues": [
    {{
      "issue_code": "rule code from the evidence",
      "title": "Short descriptive title",
      "interpretation": "What this evidence suggests about SEO health",
      "impact": "Potential impact description using measured language",
      "confidence": 0.0,
      "affected_url_count": 0
    }}
  ],
  "quick_wins": [
    {{
      "action": "Specific action to take",
      "reason": "Why this is a quick win",
      "priority": "P0/P1/P2/P3",
      "difficulty": "low/medium/high"
    }}
  ],
  "action_plan": [
    {{
      "order": 1,
      "action": "Specific action to take",
      "reason": "Why this action matters",
      "priority": "P0/P1/P2/P3",
      "difficulty": "low/medium/high",
      "dependencies": []
    }}
  ]
}}

Anti-hallucination rules:
- NEVER invent: Google ranking positions, search volume, backlinks, \
competitors' metrics, traffic, CTR, domain authority, Google penalties, \
algorithmic penalties.
- The report must clearly distinguish: OBSERVED (from evidence), \
INFERRED (logical conclusions from evidence), RECOMMENDED (actions to take).
- If you cannot determine something from the evidence, say so explicitly.
"""


def build_user_prompt_from_evidence(package: EvidencePackage) -> str:
    """Build the user prompt from an EvidencePackage (Phase 5C)."""
    return USER_PROMPT_TEMPLATE.format(
        total_pages=package.crawl.total_pages,
        status_distribution=json.dumps(package.crawl.status_distribution),
        http_problems=json.dumps(list(package.crawl.http_problems)),
        title_missing_count=package.technical.title_missing_count,
        title_duplicate_count=package.technical.title_duplicate_count,
        meta_desc_missing_count=package.technical.meta_desc_missing_count,
        canonical_missing_count=package.technical.canonical_missing_count,
        canonical_mismatch_count=package.technical.canonical_mismatch_count,
        h1_missing_count=package.technical.h1_missing_count,
        h1_duplicate_count=package.technical.h1_duplicate_count,
        robots_noindex_count=package.technical.robots_noindex_count,
        mixed_content_count=package.technical.mixed_content_count,
        large_html_count=package.technical.large_html_count,
        structured_data_missing_count=package.technical.structured_data_missing_count,
        hreflang_issues_count=package.technical.hreflang_issues_count,
        issues_by_rule=json.dumps(package.technical.issues_by_rule),
        total_internal_links=package.architecture.total_internal_links,
        avg_links_per_page=package.architecture.avg_links_per_page,
        orphan_count=package.architecture.orphan_count,
        orphan_urls=list(package.architecture.orphan_urls),
        dead_end_count=package.architecture.dead_end_count,
        dead_end_urls=list(package.architecture.dead_end_urls),
        max_depth=package.architecture.max_depth,
        avg_depth=package.architecture.avg_depth,
        thin_connection_count=package.architecture.thin_connection_count,
        pagerank_top_5=list(package.architecture.pagerank_top_5),
        pagerank_bottom_5=list(package.architecture.pagerank_bottom_5),
        avg_word_count=package.content.avg_word_count,
        median_word_count=package.content.median_word_count,
        thin_content_count=package.content.thin_content_count,
        thin_content_urls=list(package.content.thin_content_urls),
        avg_quality_score=package.content.avg_quality_score,
        quality_distribution=json.dumps(package.content.quality_distribution),
        duplicate_pair_count=package.content.duplicate_pair_count,
        duplicate_pairs=json.dumps(list(package.content.duplicate_pairs)),
        avg_readability_score=package.content.avg_readability_score,
        images_without_alt_count=package.content.images_without_alt_count,
        total_images=package.content.total_images,
        top_keywords=json.dumps(list(package.content.top_keywords)),
        keyword_stuffing_count=package.content.keyword_stuffing_count,
        diagnosis_issue_count=package.diagnosis_issue_count,
        diagnosis_issues_by_priority=json.dumps(package.diagnosis_issues_by_priority),
        diagnosis_issues_by_category=json.dumps(package.diagnosis_issues_by_category),
    )


# ── Legacy prompt (kept for backward compat) ────────────────────────────────

LEGACY_USER_PROMPT_TEMPLATE = """\
Analyze the following SEO diagnosis evidence and produce a structured \
interpretation.

== DIAGNOSIS SUMMARY ==
- Run ID: {run_id}
- Total issues: {total_issues}
- Issues by priority: {issues_by_priority}
- Issues by severity: {issues_by_severity}
- Issues by category: {issues_by_category}
- Top affected pages: {top_affected_pages}

== INDIVIDUAL ISSUES ==
{issues_json}

== REQUIRED OUTPUT SCHEMA ==
{{
  "summary": "Brief overview of the site's SEO health (2-4 sentences)",
  "priority_issues": [
    {{
      "issue_code": "rule code from the evidence",
      "interpretation": "what this evidence suggests about SEO health",
      "impact": "potential impact description using measured language",
      "recommendation": "specific actionable fix",
      "confidence": 0.0
    }}
  ],
  "action_plan": [
    {{
      "priority": "P0/P1/P2/P3",
      "action": "specific action to take",
      "reason": "why this action matters",
      "depends_on": []
    }}
  ]
}}
"""


def build_user_prompt(result: DiagnosisResult) -> str:
    """Build the user prompt from a DiagnosisResult (legacy, kept for compat)."""
    issues_data = []
    for issue in result.issues:
        issues_data.append(
            {
                "rule_code": issue.rule_code,
                "category": issue.category.value,
                "severity": issue.severity.value,
                "priority": issue.priority.value,
                "affected_url": issue.affected_url,
                "explanation": issue.explanation,
                "recommendation": issue.recommendation,
                "evidence": [
                    {
                        "metric_name": e.metric_name,
                        "metric_value": e.metric_value,
                        "threshold": e.threshold,
                        "description": e.description,
                        "source_url": e.source_url,
                    }
                    for e in issue.evidence
                ],
                "confidence": issue.confidence,
                "source_engine": issue.source_engine,
            }
        )

    return LEGACY_USER_PROMPT_TEMPLATE.format(
        run_id=result.run_id,
        total_issues=result.total_issues,
        issues_by_priority=json.dumps(result.issues_by_priority),
        issues_by_severity=json.dumps(result.issues_by_severity),
        issues_by_category=json.dumps(result.issues_by_category),
        top_affected_pages=json.dumps(list(result.top_affected_pages)),
        issues_json=json.dumps(issues_data, indent=2),
    )
