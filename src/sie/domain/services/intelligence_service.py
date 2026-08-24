"""Intelligence service — orchestrates deterministic diagnosis + LLM reasoning.

This service wraps the Phase 5A deterministic diagnosis engine and optionally
enhances it with LLM-powered reasoning.  The deterministic result is ALWAYS
produced; the LLM layer is additive and never degrades the core output.
"""

from __future__ import annotations

import json

from sie.domain.models.diagnosis import DiagnosisResult
from sie.domain.models.intelligence import (
    ActionPlanItem,
    IntelligenceResult,
    LLMReasoningResult,
    PriorityIssue,
)
from sie.domain.ports.llm import LLMProvider, LLMProviderError
from sie.domain.prompts.seo_diagnosis import (
    SYSTEM_PROMPT,
    build_user_prompt,
)
from sie.logging import get_logger

logger = get_logger(__name__)

# Maximum number of issues to send to the LLM (keeps prompt manageable)
_MAX_ISSUES_FOR_LLM = 30


class IntelligenceService:
    """Wraps deterministic diagnosis with optional LLM reasoning.

    When the LLM provider is ``None`` or disabled, the service returns
    only the deterministic result with ``llm_available=False``.
    """

    def __init__(self, llm_provider: LLMProvider | None = None) -> None:
        self._llm = llm_provider
        self._results: dict[str, IntelligenceResult] = {}

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
            from dataclasses import replace

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
        """Validate and parse the LLM JSON response into domain models."""
        # Strip markdown code fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Remove first and last fence lines
            start = 1
            end = len(lines) - 1
            if lines[0].startswith("```json"):
                start = 1
            if lines[-1].strip() == "```":
                end = len(lines) - 1
            cleaned = "\n".join(lines[start:end])

        try:
            data = json.loads(cleaned)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"LLM returned invalid JSON: {exc}") from exc

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

        # Parse action plan
        action_plan: list[ActionPlanItem] = []
        for item in data.get("action_plan", []):
            if not isinstance(item, dict):
                continue
            deps = item.get("depends_on", [])
            if not isinstance(deps, list):
                deps = []
            action_plan.append(
                ActionPlanItem(
                    priority=str(item.get("priority", "P2")),
                    action=str(item.get("action", "")),
                    reason=str(item.get("reason", "")),
                    depends_on=tuple(str(d) for d in deps),
                )
            )

        return LLMReasoningResult(
            run_id=run_id,
            summary=str(data.get("summary", "")),
            priority_issues=tuple(priority_issues),
            action_plan=tuple(action_plan),
            raw_response=raw,
        )

    def get_result(self, run_id: str) -> IntelligenceResult | None:
        return self._results.get(run_id)
