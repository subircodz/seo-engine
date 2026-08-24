"""Versioned SEO diagnosis prompt for LLM reasoning.

This module builds the system and user prompts that instruct the LLM to
reason over deterministic Phase 5A evidence and produce structured
interpretations.  The prompt is versioned so it can evolve independently
of the engine code.
"""

from __future__ import annotations

import json

from sie.domain.models.diagnosis import DiagnosisResult

PROMPT_VERSION = "1.0.0"

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
    """Build the user prompt from a DiagnosisResult."""
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

    return USER_PROMPT_TEMPLATE.format(
        run_id=result.run_id,
        total_issues=result.total_issues,
        issues_by_priority=json.dumps(result.issues_by_priority),
        issues_by_severity=json.dumps(result.issues_by_severity),
        issues_by_category=json.dumps(result.issues_by_category),
        top_affected_pages=json.dumps(list(result.top_affected_pages)),
        issues_json=json.dumps(issues_data, indent=2),
    )
