"""Tests for Phase 5C: Evidence package, intelligence reasoning, persistence, API."""

from __future__ import annotations

import json

import httpx
import pytest

from sie.domain.models.diagnosis import (
    DiagnosisCategory,
    DiagnosisEvidence,
    DiagnosisIssue,
    DiagnosisPriority,
    DiagnosisResult,
    DiagnosisSeverity,
)
from sie.domain.models.intelligence import (
    EvidencePackage,
    LLMReasoningResult,
)
from sie.domain.prompts.seo_diagnosis import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_user_prompt_from_evidence,
)
from sie.domain.services.evidence_builder import build_evidence_package
from sie.domain.services.intelligence_service import IntelligenceService
from sie.infrastructure.llm.openai_provider import OpenAICompatibleProvider

# ════════════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════════════


def _make_diagnosis_result(run_id: str = "test-run") -> DiagnosisResult:
    issues = (
        DiagnosisIssue(
            rule_code="DX_TITLE_MISSING",
            category=DiagnosisCategory.META,
            severity=DiagnosisSeverity.CRITICAL,
            priority=DiagnosisPriority.P0,
            affected_url="https://example.com/no-title",
            explanation="Page is missing a <title> tag.",
            recommendation="Add a unique, descriptive title.",
            evidence=(
                DiagnosisEvidence(
                    metric_name="title_present",
                    metric_value=False,
                    description="No <title> element found",
                ),
            ),
            confidence=1.0,
            source_engine="technical_seo",
        ),
        DiagnosisIssue(
            rule_code="DX_THIN_CONTENT",
            category=DiagnosisCategory.CONTENT,
            severity=DiagnosisSeverity.HIGH,
            priority=DiagnosisPriority.P1,
            affected_url="https://example.com/thin",
            explanation="Page has only 50 words (threshold: 150).",
            recommendation="Expand the page with substantive content.",
            evidence=(
                DiagnosisEvidence(
                    metric_name="word_count",
                    metric_value=50,
                    threshold=150,
                    description="Total visible word count",
                ),
            ),
            confidence=1.0,
            source_engine="content_intelligence",
        ),
        DiagnosisIssue(
            rule_code="DX_BROKEN_PAGE",
            category=DiagnosisCategory.STATUS,
            severity=DiagnosisSeverity.CRITICAL,
            priority=DiagnosisPriority.P0,
            affected_url="https://example.com/broken",
            explanation="Page returns HTTP 404.",
            recommendation="Fix or redirect.",
            evidence=(),
            confidence=1.0,
            source_engine="technical_seo",
        ),
    )
    return DiagnosisResult(
        run_id=run_id,
        total_issues=3,
        issues_by_priority={"P0": 2, "P1": 1},
        issues_by_severity={"critical": 2, "high": 1},
        issues_by_category={"meta": 1, "content": 1, "status": 1},
        issues=issues,
        top_affected_pages=("https://example.com/no-title",),
    )


def _make_evidence_package(run_id: str = "test-run") -> EvidencePackage:
    return build_evidence_package(
        run_id=run_id,
        crawled_page_count=50,
        status_distribution={"200": 45, "404": 3, "301": 2},
    )


def _mock_v2_llm_response() -> str:
    return json.dumps(
        {
            "summary": "Critical technical issues require attention.",
            "overall_assessment": (
                "OBSERVED: Multiple P0 issues detected. "
                "INFERRED: Site has technical debt. "
                "RECOMMENDED: Fix critical issues first."
            ),
            "root_causes": [
                {
                    "title": "Missing on-page SEO elements",
                    "evidence": [
                        "Title tags missing on 5 pages",
                        "Meta descriptions missing on 3 pages",
                    ],
                    "confidence": 0.95,
                }
            ],
            "top_issues": [
                {
                    "issue_code": "DX_TITLE_MISSING",
                    "title": "Missing title tags",
                    "interpretation": "Pages without titles lose primary on-page signal",
                    "impact": "Potential ranking issue for affected pages",
                    "confidence": 0.9,
                    "affected_url_count": 5,
                }
            ],
            "quick_wins": [
                {
                    "action": "Add title tags to all pages",
                    "reason": "Quick fix with high impact",
                    "priority": "P0",
                    "difficulty": "low",
                }
            ],
            "action_plan": [
                {
                    "order": 1,
                    "action": "Add title tags",
                    "reason": "Critical SEO obstacle",
                    "priority": "P0",
                    "difficulty": "low",
                    "dependencies": [],
                }
            ],
        }
    )


class MockTransport(httpx.AsyncBaseTransport):
    def __init__(
        self,
        *,
        status_code: int = 200,
        json_data: dict | None = None,
        raise_exc: Exception | None = None,
    ):
        self._status_code = status_code
        self._json_data = json_data
        self._raise_exc = raise_exc
        self.requests: list[dict] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append({"method": request.method, "url": str(request.url)})
        if self._raise_exc:
            raise self._raise_exc
        if self._json_data is not None:
            return httpx.Response(status_code=self._status_code, json=self._json_data)
        return httpx.Response(status_code=self._status_code, text="{}")


# ════════════════════════════════════════════════════════════════════════════
# Evidence package construction tests
# ════════════════════════════════════════════════════════════════════════════


class TestEvidencePackageConstruction:
    def test_build_evidence_package_empty(self):
        pkg = _make_evidence_package()
        assert pkg.run_id == "test-run"
        assert pkg.crawl.total_pages == 50
        assert pkg.crawl.status_distribution == {"200": 45, "404": 3, "301": 2}
        assert pkg.technical.title_missing_count == 0
        assert pkg.architecture.orphan_count == 0
        assert pkg.content.avg_word_count == 0.0

    def test_build_evidence_package_with_diagnosis(self):
        diag = _make_diagnosis_result()
        pkg = build_evidence_package(
            run_id="test-run",
            diagnosis=diag,
            crawled_page_count=10,
        )
        assert pkg.diagnosis_issue_count == 3
        assert pkg.diagnosis_issues_by_priority == {"P0": 2, "P1": 1}
        assert pkg.diagnosis_issues_by_category == {"meta": 1, "content": 1, "status": 1}

    def test_evidence_package_is_bounded(self):
        """Verify evidence package doesn't grow unbounded."""
        pkg = _make_evidence_package()
        # Crawl evidence is bounded
        assert len(pkg.crawl.http_problems) <= 20
        # Architecture URLs are bounded
        assert len(pkg.architecture.orphan_urls) <= 15
        assert len(pkg.architecture.dead_end_urls) <= 15
        # Content URLs are bounded
        assert len(pkg.content.thin_content_urls) <= 15
        assert len(pkg.content.top_keywords) <= 10
        assert len(pkg.content.duplicate_pairs) <= 10

    def test_evidence_prompt_contains_all_sections(self):
        pkg = _make_evidence_package()
        prompt = build_user_prompt_from_evidence(pkg)
        assert "CRAWL STATISTICS" in prompt
        assert "TECHNICAL SEO FINDINGS" in prompt
        assert "SITE ARCHITECTURE" in prompt
        assert "CONTENT ANALYSIS" in prompt
        assert "DIAGNOSIS SUMMARY" in prompt
        assert "REQUIRED OUTPUT SCHEMA" in prompt

    def test_evidence_prompt_has_anti_hallucination_rules(self):
        pkg = _make_evidence_package()
        prompt = build_user_prompt_from_evidence(pkg)
        assert "Anti-hallucination rules" in prompt
        assert "NEVER invent" in prompt
        assert "OBSERVED" in prompt
        assert "INFERRED" in prompt
        assert "RECOMMENDED" in prompt

    def test_system_prompt_has_measured_language(self):
        assert "potential ranking issue" in SYSTEM_PROMPT
        assert "SEO risk" in SYSTEM_PROMPT
        assert "will drop rankings" in SYSTEM_PROMPT  # in "Never use" list


# ════════════════════════════════════════════════════════════════════════════
# Structured output validation tests
# ════════════════════════════════════════════════════════════════════════════


class TestStructuredOutputValidation:
    def test_parse_v2_valid_response(self):
        service = IntelligenceService(llm_provider=None)
        raw = _mock_v2_llm_response()
        result = service._parse_llm_response_v2("run-1", raw)
        assert isinstance(result, LLMReasoningResult)
        expected = "Critical technical issues require attention."
        assert result.summary == expected
        assert len(result.root_causes) == 1
        assert result.root_causes[0].title == "Missing on-page SEO elements"
        assert result.root_causes[0].confidence == 0.95
        assert len(result.top_issues) == 1
        assert result.top_issues[0].issue_code == "DX_TITLE_MISSING"
        assert result.top_issues[0].affected_url_count == 5
        assert len(result.quick_wins) == 1
        assert result.quick_wins[0].difficulty == "low"
        assert len(result.action_plan) == 1
        assert result.action_plan[0].order == 1
        assert result.action_plan[0].difficulty == "low"

    def test_parse_v2_missing_required_keys(self):
        service = IntelligenceService(llm_provider=None)
        with pytest.raises(ValueError, match="missing keys"):
            service._parse_llm_response_v2("run", json.dumps({"summary": "hi"}))

    def test_parse_v2_invalid_json(self):
        service = IntelligenceService(llm_provider=None)
        with pytest.raises(ValueError, match="invalid JSON"):
            service._parse_llm_response_v2("run", "not json")

    def test_parse_v2_code_fences(self):
        service = IntelligenceService(llm_provider=None)
        raw = _mock_v2_llm_response()
        fenced = f"```json\n{raw}\n```"
        result = service._parse_llm_response_v2("run", fenced)
        assert result.summary.startswith("Critical")

    def test_parse_v2_confidence_clamped(self):
        service = IntelligenceService(llm_provider=None)
        data = {
            "summary": "Test",
            "overall_assessment": "Test",
            "root_causes": [
                {"title": "X", "evidence": [], "confidence": 1.5},
            ],
            "top_issues": [
                {
                    "issue_code": "X",
                    "title": "X",
                    "interpretation": "X",
                    "impact": "X",
                    "confidence": -0.5,
                    "affected_url_count": 0,
                },
            ],
            "quick_wins": [
                {"action": "X", "reason": "X", "priority": "P0", "difficulty": "low"},
            ],
            "action_plan": [
                {
                    "order": 1,
                    "action": "X",
                    "reason": "X",
                    "priority": "P0",
                    "difficulty": "low",
                    "dependencies": [],
                },
            ],
        }
        result = service._parse_llm_response_v2("run", json.dumps(data))
        assert result.root_causes[0].confidence == 1.0
        assert result.top_issues[0].confidence == 0.0

    def test_parse_v2_invalid_difficulty_normalized(self):
        service = IntelligenceService(llm_provider=None)
        data = {
            "summary": "Test",
            "overall_assessment": "Test",
            "root_causes": [],
            "top_issues": [],
            "quick_wins": [
                {"action": "X", "reason": "X", "priority": "P0", "difficulty": "extreme"},
            ],
            "action_plan": [
                {
                    "order": 1,
                    "action": "X",
                    "reason": "X",
                    "priority": "P0",
                    "difficulty": "impossible",
                    "dependencies": [],
                },
            ],
        }
        result = service._parse_llm_response_v2("run", json.dumps(data))
        assert result.quick_wins[0].difficulty == "medium"
        assert result.action_plan[0].difficulty == "medium"

    def test_parse_v2_invalid_priority_normalized(self):
        service = IntelligenceService(llm_provider=None)
        data = {
            "summary": "Test",
            "overall_assessment": "Test",
            "root_causes": [],
            "top_issues": [],
            "quick_wins": [
                {"action": "X", "reason": "X", "priority": "URGENT", "difficulty": "low"},
            ],
            "action_plan": [
                {
                    "order": 1,
                    "action": "X",
                    "reason": "X",
                    "priority": "CRITICAL",
                    "difficulty": "low",
                    "dependencies": [],
                },
            ],
        }
        result = service._parse_llm_response_v2("run", json.dumps(data))
        assert result.quick_wins[0].priority == "P2"
        assert result.action_plan[0].priority == "P2"


# ════════════════════════════════════════════════════════════════════════════
# Hallucination guard tests
# ════════════════════════════════════════════════════════════════════════════


class TestHallucinationGuards:
    def test_system_prompt_prohibits_ranking_claims(self):
        """Verify the system prompt explicitly forbids ranking claims."""
        assert "ranking change" in SYSTEM_PROMPT
        assert "Do not claim" in SYSTEM_PROMPT
        assert "will drop rankings" in SYSTEM_PROMPT  # in "Never use" list

    def test_evidence_prompt_requires_observed_inferred_recommended(self):
        """Verify the prompt requires OBSERVED/INFERRED/RECOMMENDED framework."""
        pkg = _make_evidence_package()
        prompt = build_user_prompt_from_evidence(pkg)
        assert "OBSERVED" in prompt
        assert "INFERRED" in prompt
        assert "RECOMMENDED" in prompt
        # Anti-hallucination rules are in the user prompt
        assert "NEVER invent" in prompt
        assert "Google ranking positions" in prompt
        assert "search volume" in prompt
        assert "backlinks" in prompt
        assert "traffic" in prompt
        assert "Google penalties" in prompt

    def test_deterministic_report_uses_measured_language(self):
        """Verify the deterministic fallback report uses measured language."""
        svc = IntelligenceService(llm_provider=None)
        diag = _make_diagnosis_result()
        report = svc._build_deterministic_report("ir_test", "test-run", diag)
        assert "Detected" in report.summary
        assert "OBSERVED:" in report.overall_assessment
        assert "INFERRED:" in report.overall_assessment
        assert "RECOMMENDED:" in report.overall_assessment


# ════════════════════════════════════════════════════════════════════════════
# LLM failure fallback tests
# ════════════════════════════════════════════════════════════════════════════


class TestLLMFailureFallback:
    @pytest.mark.asyncio
    async def test_reason_from_evidence_fallback_on_timeout(self):
        transport = MockTransport(raise_exc=httpx.TimeoutException("timeout"))
        client = httpx.AsyncClient(transport=transport)
        provider = OpenAICompatibleProvider(
            base_url="https://api.test.com", api_key="sk-test", client=client,
        )
        service = IntelligenceService(llm_provider=provider)
        diag = _make_diagnosis_result()
        evidence = _make_evidence_package()
        result = await service.reason_from_evidence("run-1", diag, evidence)
        assert result.llm_available is False
        assert result.reasoning is None
        assert result.diagnosis is diag
        await provider.close()

    @pytest.mark.asyncio
    async def test_reason_from_evidence_fallback_on_invalid_json(self):
        transport = MockTransport(
            status_code=200,
            json_data={"choices": [{"message": {"content": "not json"}}]},
        )
        client = httpx.AsyncClient(transport=transport)
        provider = OpenAICompatibleProvider(
            base_url="https://api.test.com", api_key="sk-test", client=client,
        )
        service = IntelligenceService(llm_provider=provider)
        diag = _make_diagnosis_result()
        evidence = _make_evidence_package()
        result = await service.reason_from_evidence("run-2", diag, evidence)
        assert result.llm_available is False
        assert result.reasoning is None
        await provider.close()

    @pytest.mark.asyncio
    async def test_generate_report_fallback_on_llm_failure(self):
        transport = MockTransport(raise_exc=httpx.ConnectError("refused"))
        client = httpx.AsyncClient(transport=transport)
        provider = OpenAICompatibleProvider(
            base_url="https://api.test.com", api_key="sk-test", client=client,
        )
        service = IntelligenceService(llm_provider=provider)
        diag = _make_diagnosis_result()
        evidence = _make_evidence_package()
        report = await service.generate_report("run-3", diag, evidence)
        assert report.model_name == "deterministic"
        assert report.provider == "none"
        assert len(report.root_causes) > 0
        assert len(report.action_plan) > 0
        await provider.close()

    @pytest.mark.asyncio
    async def test_generate_report_success_with_llm(self):
        llm_json = _mock_v2_llm_response()
        transport = MockTransport(
            status_code=200,
            json_data={"choices": [{"message": {"content": llm_json}}]},
        )
        client = httpx.AsyncClient(transport=transport)
        provider = OpenAICompatibleProvider(
            base_url="https://api.test.com", api_key="sk-test", client=client,
        )
        service = IntelligenceService(
            llm_provider=provider, model_name="gpt-4o", provider_name="openai",
        )
        diag = _make_diagnosis_result()
        evidence = _make_evidence_package()
        report = await service.generate_report("run-4", diag, evidence)
        assert report.model_name == "gpt-4o"
        assert report.provider == "openai"
        assert report.prompt_version == PROMPT_VERSION
        assert len(report.root_causes) == 1
        assert len(report.top_issues) == 1
        assert len(report.quick_wins) == 1
        assert len(report.action_plan) == 1
        await provider.close()

    @pytest.mark.asyncio
    async def test_report_cached_and_retrievable(self):
        service = IntelligenceService(llm_provider=None)
        diag = _make_diagnosis_result()
        evidence = _make_evidence_package()
        report = await service.generate_report("run-5", diag, evidence)
        retrieved = service.get_report(report.intelligence_id)
        assert retrieved is not None
        assert retrieved.intelligence_id == report.intelligence_id
        by_run = service.get_report_by_run_id("run-5")
        assert by_run is not None

    @pytest.mark.asyncio
    async def test_deterministic_only_report_structure(self):
        """Verify deterministic-only report has complete structure."""
        service = IntelligenceService(llm_provider=None)
        diag = _make_diagnosis_result()
        evidence = _make_evidence_package()
        report = await service.generate_report("run-6", diag, evidence)
        # Root causes grouped by category
        assert len(report.root_causes) == 3  # meta, content, status
        # Top issues from diagnosis
        assert len(report.top_issues) >= 3
        # Quick wins from P0 issues
        assert len(report.quick_wins) >= 1
        # Action plan from diagnosis
        assert len(report.action_plan) >= 1


# ════════════════════════════════════════════════════════════════════════════
# Persistence tests (unit-level, using in-memory mock)
# ════════════════════════════════════════════════════════════════════════════


class TestPersistence:
    @pytest.mark.asyncio
    async def test_report_round_trip_via_repository(self, harness):
        """Test save + retrieve via the actual repository."""
        from datetime import UTC, datetime

        from sie.domain.models.crawl import CrawlRunRecord, CrawlStatus

        # First create a crawl run (FK requirement)
        run_id = "test-persist"
        now = datetime.now(UTC)
        run = CrawlRunRecord(
            id=run_id,
            target_url="https://example.com",
            status=CrawlStatus.COMPLETED,
            started_at=now,
            completed_at=now,
            policy_snapshot={},
            total_pages=0,
            error_count=0,
        )
        repo = harness.app.state.repository
        await repo.create_run(run)

        # Generate and save intelligence report
        svc = IntelligenceService(llm_provider=None)
        diag = _make_diagnosis_result(run_id)
        evidence = _make_evidence_package(run_id)
        report = await svc.generate_report(run_id, diag, evidence)
        await repo.save_intelligence_report(run_id, report)

        # Retrieve by intelligence_id
        retrieved = await repo.get_intelligence_report(report.intelligence_id)
        assert retrieved is not None
        assert retrieved.intelligence_id == report.intelligence_id
        assert retrieved.summary == report.summary
        assert retrieved.overall_assessment == report.overall_assessment
        assert len(retrieved.root_causes) == len(report.root_causes)
        assert len(retrieved.top_issues) == len(report.top_issues)
        assert len(retrieved.quick_wins) == len(report.quick_wins)
        assert len(retrieved.action_plan) == len(report.action_plan)

        # Retrieve by run_id
        by_run = await repo.get_intelligence_report_by_run_id(run_id)
        assert by_run is not None
        assert by_run.intelligence_id == report.intelligence_id

    @pytest.mark.asyncio
    async def test_persistence_returns_none_for_missing(self, harness):
        repo = harness.app.state.repository
        result = await repo.get_intelligence_report("nonexistent")
        assert result is None
        result = await repo.get_intelligence_report_by_run_id("nonexistent")
        assert result is None


# ════════════════════════════════════════════════════════════════════════════
# API tests
# ════════════════════════════════════════════════════════════════════════════


class TestIntelligenceAPI:
    @pytest.fixture
    async def crawl_with_pages(self, harness):
        """Start a crawl run and inject sample pages."""
        app = harness.app
        client = harness.client

        from sie.domain.models.page import FetchedPage

        pages = [
            FetchedPage(
                url="https://example.com/good-page",
                final_url="https://example.com/good-page",
                status_code=200,
                headers={"Content-Type": "text/html"},
                content=b"""<html>
                <head>
                    <title>Good Page - SEO Guide</title>
                    <meta name="description" content="Learn SEO basics">
                </head>
                <body>
                    <h1>Complete SEO Guide</h1>
                    <p>This is a comprehensive SEO guide with enough content.</p>
                    <h2>Keywords</h2>
                    <p>Keywords are important for SEO. Use them naturally.</p>
                    <img src="/img1.jpg" alt="SEO diagram">
                </body>
                </html>""",
                content_type="text/html",
                depth=0,
            ),
            FetchedPage(
                url="https://example.com/bad-page",
                final_url="https://example.com/bad-page",
                status_code=404,
                headers={"Content-Type": "text/html"},
                content=b"<html><body><h1>Not Found</h1></body></html>",
                content_type="text/html",
                depth=1,
            ),
        ]

        resp = await client.post("/api/crawl", json={"url": "https://example.com", "max_pages": 10})
        assert resp.status_code == 202
        run_id = resp.json()["run_id"]
        app.state.crawled_pages[run_id] = pages
        return run_id

    @pytest.mark.asyncio
    async def test_reason_intelligence(self, harness, crawl_with_pages):
        client = harness.client
        run_id = crawl_with_pages

        resp = await client.post("/api/intelligence/reason", json={"run_id": run_id})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert "intelligence_id" in data
        assert data["top_issue_count"] >= 0
        assert data["action_count"] >= 0
        assert len(data["summary"]) > 0

    @pytest.mark.asyncio
    async def test_get_intelligence_report(self, harness, crawl_with_pages):
        client = harness.client
        run_id = crawl_with_pages

        # First generate
        resp = await client.post("/api/intelligence/reason", json={"run_id": run_id})
        intel_id = resp.json()["intelligence_id"]

        # Then retrieve
        resp = await client.get(f"/api/intelligence/{intel_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["intelligence_id"] == intel_id
        assert data["status"] == "completed"
        assert "root_causes" in data
        assert "top_issues" in data
        assert "quick_wins" in data
        assert "action_plan" in data

    @pytest.mark.asyncio
    async def test_get_action_plan(self, harness, crawl_with_pages):
        client = harness.client
        run_id = crawl_with_pages

        resp = await client.post("/api/intelligence/reason", json={"run_id": run_id})
        intel_id = resp.json()["intelligence_id"]

        resp = await client.get(f"/api/intelligence/{intel_id}/actions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["intelligence_id"] == intel_id
        assert "actions" in data
        assert "total_actions" in data

    @pytest.mark.asyncio
    async def test_get_report_not_found(self, harness):
        client = harness.client
        resp = await client.get("/api/intelligence/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_actions_not_found(self, harness):
        client = harness.client
        resp = await client.get("/api/intelligence/nonexistent/actions")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_reason_not_found(self, harness):
        client = harness.client
        resp = await client.post("/api/intelligence/reason", json={"run_id": "nonexistent"})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_report_persisted_after_reason(self, harness, crawl_with_pages):
        """Verify report is persisted and retrievable after /reason."""
        client = harness.client
        run_id = crawl_with_pages

        resp = await client.post("/api/intelligence/reason", json={"run_id": run_id})
        intel_id = resp.json()["intelligence_id"]

        # Should be retrievable
        resp = await client.get(f"/api/intelligence/{intel_id}")
        assert resp.status_code == 200
        assert resp.json()["intelligence_id"] == intel_id
