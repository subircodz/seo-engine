"""Intelligence service — orchestrates deterministic diagnosis + LLM reasoning.

This service wraps the Phase 5A deterministic diagnosis engine and optionally
enhances it with LLM-powered reasoning.  The deterministic result is ALWAYS
produced; the LLM layer is additive and never degrades the core output.

Phase 5C adds evidence-package-based reasoning with a richer output schema
including root causes, quick wins, and a prioritized action plan.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import replace

from sie.domain.models.diagnosis import DiagnosisResult
from sie.domain.models.intelligence import (
    ActionPlanItem,
    IntelligenceReport,
    IntelligenceResult,
    LLMReasoningResult,
    PriorityIssue,
    QuickWin,
    RootCause,
    TopIssue,
)
from sie.domain.ports.llm import LLMProvider, LLMProviderError
from sie.domain.prompts.seo_diagnosis import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_user_prompt,
    build_user_prompt_from_evidence,
)
from sie.logging import get_logger

logger = get_logger(__name__)

# Maximum number of issues to send to the LLM (keeps prompt manageable)
_MAX_ISSUES_FOR_LLM = 30

# Valid difficulty levels
_VALID_DIFFICULTIES = {"low", "medium", "high"}
# Valid priority levels
_VALID_PRIORITIES = {"P0", "P1", "P2", "P3"}


class IntelligenceService:
    """Wraps deterministic diagnosis with optional LLM reasoning.

    When the LLM provider is ``None`` or disabled, the service returns
    only the deterministic result with ``llm_available=False``.
    """

    def __init__(
        self,
        llm_provider: LLMProvider | None = None,
        *,
        model_name: str = "",
        provider_name: str = "",
    ) -> None:
        self._llm = llm_provider
        self._model_name = model_name
        self._provider_name = provider_name
        self._results: dict[str, IntelligenceResult] = {}
        self._reports: dict[str, IntelligenceReport] = {}

    # ── Phase 5C: Evidence-based reasoning ──────────────────────────────────

    async def reason_from_evidence(
        self,
        run_id: str,
        diagnosis: DiagnosisResult,
        evidence_package: object,  # EvidencePackage (avoids circular import)
        *,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> IntelligenceResult:
        """Produce an IntelligenceResult using an evidence package.

        This is the Phase 5C entry point.  If the LLM is unavailable or
        fails, the deterministic diagnosis is still returned.
        """
        reasoning = None
        llm_available = False

        if self._llm is not None:
            try:
                reasoning = await self._call_llm_from_evidence(
                    evidence_package,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                llm_available = True
                logger.info(
                    "LLM reasoning for %s: %d root causes, %d top issues, %d actions",
                    run_id,
                    len(reasoning.root_causes),
                    len(reasoning.top_issues),
                    len(reasoning.action_plan),
                )
            except LLMProviderError as exc:
                logger.warning(
                    "LLM reasoning failed for %s, returning deterministic result: %s",
                    run_id,
                    exc,
                )
            except Exception as exc:
                logger.warning("Unexpected LLM error for %s: %s", run_id, exc, exc_info=True)

        result = IntelligenceResult(
            run_id=run_id,
            diagnosis=diagnosis,
            reasoning=reasoning,
            llm_available=llm_available,
        )
        self._results[run_id] = result
        return result

    async def _call_llm_from_evidence(
        self,
        evidence_package: object,
        *,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> LLMReasoningResult:
        """Send evidence package to the LLM and parse the structured response."""
        user_prompt = build_user_prompt_from_evidence(evidence_package)
        raw = await self._llm.generate(  # type: ignore[union-attr]
            SYSTEM_PROMPT,
            user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return self._parse_llm_response_v2(evidence_package.run_id, raw)  # type: ignore[union-attr]

    # ── Phase 5C: Report generation ─────────────────────────────────────────

    async def generate_report(
        self,
        run_id: str,
        diagnosis: DiagnosisResult,
        evidence_package: object,  # EvidencePackage
        *,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> IntelligenceReport:
        """Generate a full intelligence report, optionally using LLM reasoning.

        If the LLM is disabled or fails, returns a report with empty LLM
        fields and the deterministic diagnosis data.
        """
        intelligence_id = f"ir_{uuid.uuid4().hex[:16]}"
        reasoning = None

        if self._llm is not None:
            try:
                reasoning = await self._call_llm_from_evidence(
                    evidence_package,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except Exception as exc:
                logger.warning("LLM failed for report %s: %s", intelligence_id, exc)

        if reasoning is not None:
            report = IntelligenceReport(
                intelligence_id=intelligence_id,
                run_id=run_id,
                diagnosis_run_id=run_id,
                prompt_version=PROMPT_VERSION,
                model_name=self._model_name,
                provider=self._provider_name,
                summary=reasoning.summary,
                overall_assessment=reasoning.overall_assessment,
                root_causes=reasoning.root_causes,
                top_issues=reasoning.top_issues,
                quick_wins=reasoning.quick_wins,
                action_plan=reasoning.action_plan,
                raw_response=reasoning.raw_response,
                generated_at=reasoning.generated_at,
            )
        else:
            # Build a deterministic-only report from the diagnosis
            report = self._build_deterministic_report(
                intelligence_id, run_id, diagnosis
            )

        self._reports[intelligence_id] = report
        logger.info(
            "Intelligence report %s for run %s: %d root causes, %d actions",
            intelligence_id,
            run_id,
            len(report.root_causes),
            len(report.action_plan),
        )
        return report

    def _build_deterministic_report(
        self,
        intelligence_id: str,
        run_id: str,
        diagnosis: DiagnosisResult,
    ) -> IntelligenceReport:
        """Build a report from deterministic diagnosis data only (no LLM)."""
        # Group issues by category for root causes
        issues_by_cat: dict[str, list[str]] = {}
        for issue in diagnosis.issues:
            cat = issue.category.value
            issues_by_cat.setdefault(cat, []).append(issue.explanation)

        root_causes = []
        for cat, explanations in issues_by_cat.items():
            root_causes.append(
                RootCause(
                    title=f"Multiple {cat} issues detected",
                    evidence=tuple(explanations[:5]),
                    confidence=1.0,
                )
            )

        # Build top issues from diagnosis
        top_issues = []
        seen_codes: set[str] = set()
        for issue in diagnosis.issues:
            if issue.rule_code not in seen_codes:
                seen_codes.add(issue.rule_code)
                top_issues.append(
                    TopIssue(
                        issue_code=issue.rule_code,
                        title=issue.rule_code.replace("_", " ").title(),
                        interpretation=issue.explanation,
                        impact=issue.recommendation,
                        confidence=issue.confidence,
                        affected_url_count=1,
                    )
                )

        # Quick wins: P0 issues with high confidence
        quick_wins = [
            QuickWin(
                action=issue.recommendation,
                reason=f"Deterministic detection: {issue.explanation}",
                priority=issue.priority.value,
                difficulty="low",
            )
            for issue in diagnosis.issues
            if issue.priority.value == "P0" and issue.confidence >= 0.9
        ][:5]

        # Action plan from diagnosis
        action_plan = [
            ActionPlanItem(
                order=i + 1,
                action=issue.recommendation,
                reason=issue.explanation,
                priority=issue.priority.value,
                difficulty="low" if issue.confidence >= 0.9 else "medium",
            )
            for i, issue in enumerate(diagnosis.issues[:10])
        ]

        summary_parts = []
        if diagnosis.total_issues > 0:
            summary_parts.append(
                f"Detected {diagnosis.total_issues} SEO issues across "
                f"{len(diagnosis.top_affected_pages)} page(s)."
            )
        p0 = diagnosis.issues_by_priority.get("P0", 0)
        if p0:
            summary_parts.append(f"{p0} critical (P0) issues require immediate attention.")

        return IntelligenceReport(
            intelligence_id=intelligence_id,
            run_id=run_id,
            diagnosis_run_id=run_id,
            prompt_version=PROMPT_VERSION,
            model_name="deterministic",
            provider="none",
            summary=" ".join(summary_parts) or "No issues detected.",
            overall_assessment="OBSERVED: Deterministic analysis completed. "
            "INFERRED: Issues identified by automated rules. "
            "RECOMMENDED: Address P0 issues first, then P1.",
            root_causes=tuple(root_causes),
            top_issues=tuple(top_issues),
            quick_wins=tuple(quick_wins),
            action_plan=tuple(action_plan),
        )

    def get_report(self, intelligence_id: str) -> IntelligenceReport | None:
        return self._reports.get(intelligence_id)

    def get_report_by_run_id(self, run_id: str) -> IntelligenceReport | None:
        for report in self._reports.values():
            if report.run_id == run_id:
                return report
        return None

    # ── Phase 5B: Legacy reasoning (kept for backward compat) ───────────────

    async def reason(
        self,
        run_id: str,
        diagnosis: DiagnosisResult,
        *,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> IntelligenceResult:
        """Produce an IntelligenceResult, optionally enhanced by LLM reasoning.

        If the LLM is unavailable or fails, the deterministic diagnosis is
        still returned with ``reasoning=None`` and ``llm_available=False``.
        """
        reasoning = None
        llm_available = False

        if self._llm is not None:
            try:
                reasoning = await self._call_llm(
                    diagnosis,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                llm_available = True
                logger.info(
                    "LLM reasoning for %s: %d priority issues, %d action items",
                    run_id,
                    len(reasoning.priority_issues),
                    len(reasoning.action_plan),
                )
            except LLMProviderError as exc:
                logger.warning(
                    "LLM reasoning failed for %s, returning deterministic result: %s",
                    run_id,
                    exc,
                )
            except Exception as exc:
                logger.warning("Unexpected LLM error for %s: %s", run_id, exc, exc_info=True)

        result = IntelligenceResult(
            run_id=run_id,
            diagnosis=diagnosis,
            reasoning=reasoning,
            llm_available=llm_available,
        )
        self._results[run_id] = result
        return result

    async def _call_llm(
        self,
        diagnosis: DiagnosisResult,
        *,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> LLMReasoningResult:
        """Send diagnosis evidence to the LLM and parse the structured response."""
        # Truncate issue list if very large
        truncated = diagnosis
        if len(diagnosis.issues) > _MAX_ISSUES_FOR_LLM:
            truncated = replace(
                diagnosis,
                issues=diagnosis.issues[:_MAX_ISSUES_FOR_LLM],
            )

        user_prompt = build_user_prompt(truncated)
        raw = await self._llm.generate(  # type: ignore[union-attr]
            SYSTEM_PROMPT,
            user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return self._parse_llm_response(diagnosis.run_id, raw)

    def _parse_llm_response(self, run_id: str, raw: str) -> LLMReasoningResult:
        """Validate and parse the LLM JSON response into domain models (legacy)."""
        data = self._strip_and_parse_json(raw)

        # Validate required top-level keys
        required_keys = {"summary", "priority_issues", "action_plan"}
        missing = required_keys - set(data.keys())
        if missing:
            raise ValueError(f"LLM response missing keys: {missing}")

        # Parse priority issues
        priority_issues: list[PriorityIssue] = []
        for item in data.get("priority_issues", []):
            if not isinstance(item, dict):
                continue
            priority_issues.append(
                PriorityIssue(
                    issue_code=str(item.get("issue_code", "")),
                    interpretation=str(item.get("interpretation", "")),
                    impact=str(item.get("impact", "")),
                    recommendation=str(item.get("recommendation", "")),
                    confidence=min(1.0, max(0.0, float(item.get("confidence", 0.5)))),
                )
            )

        # Parse action plan (legacy format)
        action_plan: list[ActionPlanItem] = []
        for i, item in enumerate(data.get("action_plan", [])):
            if not isinstance(item, dict):
                continue
            deps = item.get("depends_on", [])
            if not isinstance(deps, list):
                deps = []
            action_plan.append(
                ActionPlanItem(
                    order=item.get("order", i + 1),
                    action=str(item.get("action", "")),
                    reason=str(item.get("reason", "")),
                    priority=str(item.get("priority", "P2")),
                    difficulty=str(item.get("difficulty", "medium")),
                    dependencies=tuple(str(d) for d in deps),
                )
            )

        return LLMReasoningResult(
            run_id=run_id,
            summary=str(data.get("summary", "")),
            overall_assessment=str(data.get("overall_assessment", "")),
            root_causes=(),
            top_issues=(),
            quick_wins=(),
            action_plan=tuple(action_plan),
            priority_issues=tuple(priority_issues),
            raw_response=raw,
            prompt_version=PROMPT_VERSION,
        )

    # ── Phase 5C: New parser ────────────────────────────────────────────────

    def _parse_llm_response_v2(self, run_id: str, raw: str) -> LLMReasoningResult:
        """Validate and parse the Phase 5C LLM JSON response."""
        data = self._strip_and_parse_json(raw)

        # Validate required top-level keys
        required_keys = {"summary", "overall_assessment", "root_causes", "top_issues",
                         "quick_wins", "action_plan"}
        missing = required_keys - set(data.keys())
        if missing:
            raise ValueError(f"LLM response missing keys: {missing}")

        # Parse root causes
        root_causes: list[RootCause] = []
        for item in data.get("root_causes", []):
            if not isinstance(item, dict):
                continue
            evidence = item.get("evidence", [])
            if not isinstance(evidence, list):
                evidence = []
            root_causes.append(
                RootCause(
                    title=str(item.get("title", "")),
                    evidence=tuple(str(e) for e in evidence),
                    confidence=min(1.0, max(0.0, float(item.get("confidence", 0.5)))),
                )
            )

        # Parse top issues
        top_issues: list[TopIssue] = []
        for item in data.get("top_issues", []):
            if not isinstance(item, dict):
                continue
            top_issues.append(
                TopIssue(
                    issue_code=str(item.get("issue_code", "")),
                    title=str(item.get("title", "")),
                    interpretation=str(item.get("interpretation", "")),
                    impact=str(item.get("impact", "")),
                    confidence=min(1.0, max(0.0, float(item.get("confidence", 0.5)))),
                    affected_url_count=int(item.get("affected_url_count", 0)),
                )
            )

        # Parse quick wins
        quick_wins: list[QuickWin] = []
        for item in data.get("quick_wins", []):
            if not isinstance(item, dict):
                continue
            difficulty = str(item.get("difficulty", "medium")).lower()
            if difficulty not in _VALID_DIFFICULTIES:
                difficulty = "medium"
            priority = str(item.get("priority", "P2")).upper()
            if priority not in _VALID_PRIORITIES:
                priority = "P2"
            quick_wins.append(
                QuickWin(
                    action=str(item.get("action", "")),
                    reason=str(item.get("reason", "")),
                    priority=priority,
                    difficulty=difficulty,
                )
            )

        # Parse action plan
        action_plan: list[ActionPlanItem] = []
        for i, item in enumerate(data.get("action_plan", [])):
            if not isinstance(item, dict):
                continue
            deps = item.get("dependencies", [])
            if not isinstance(deps, list):
                deps = []
            difficulty = str(item.get("difficulty", "medium")).lower()
            if difficulty not in _VALID_DIFFICULTIES:
                difficulty = "medium"
            priority = str(item.get("priority", "P2")).upper()
            if priority not in _VALID_PRIORITIES:
                priority = "P2"
            action_plan.append(
                ActionPlanItem(
                    order=int(item.get("order", i + 1)),
                    action=str(item.get("action", "")),
                    reason=str(item.get("reason", "")),
                    priority=priority,
                    difficulty=difficulty,
                    dependencies=tuple(str(d) for d in deps),
                )
            )

        return LLMReasoningResult(
            run_id=run_id,
            summary=str(data.get("summary", "")),
            overall_assessment=str(data.get("overall_assessment", "")),
            root_causes=tuple(root_causes),
            top_issues=tuple(top_issues),
            quick_wins=tuple(quick_wins),
            action_plan=tuple(action_plan),
            raw_response=raw,
            prompt_version=PROMPT_VERSION,
            model_name=self._model_name,
            provider=self._provider_name,
        )

    @staticmethod
    def _strip_and_parse_json(raw: str) -> dict:
        """Strip markdown code fences and parse JSON."""
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            start = 1
            end = len(lines) - 1
            if lines[0].startswith("```json"):
                start = 1
            if lines[-1].strip() == "```":
                end = len(lines) - 1
            cleaned = "\n".join(lines[start:end])

        try:
            return json.loads(cleaned)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"LLM returned invalid JSON: {exc}") from exc

    def get_result(self, run_id: str) -> IntelligenceResult | None:
        return self._results.get(run_id)
