"""Tests for the LLM provider and intelligence service."""

from __future__ import annotations

import json

import httpx
import pytest

from sie.config import LLMSettings, Settings
from sie.domain.models.diagnosis import (
    DiagnosisCategory,
    DiagnosisEvidence,
    DiagnosisIssue,
    DiagnosisPriority,
    DiagnosisResult,
    DiagnosisSeverity,
)
from sie.domain.models.intelligence import LLMReasoningResult
from sie.domain.ports.llm import (
    LLMAuthenticationError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from sie.domain.prompts.seo_diagnosis import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_user_prompt,
)
from sie.domain.services.intelligence_service import IntelligenceService
from sie.infrastructure.llm.openai_provider import OpenAICompatibleProvider

try:
    from pydantic import ValidationError
except ImportError:
    ValidationError = Exception  # type: ignore[assignment,misc]

# ════════════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════════════


def _make_diagnosis_result(run_id: str = "test-run") -> DiagnosisResult:
    """Create a minimal but real DiagnosisResult for testing."""
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
    )
    return DiagnosisResult(
        run_id=run_id,
        total_issues=2,
        issues_by_priority={"P0": 1, "P1": 1},
        issues_by_severity={"critical": 1, "high": 1},
        issues_by_category={"meta": 1, "content": 1},
        issues=issues,
        top_affected_pages=("https://example.com/no-title",),
    )


def _mock_llm_response(
    summary: str = "Test summary",
    priority_issues: list[dict] | None = None,
    action_plan: list[dict] | None = None,
) -> str:
    """Build a valid LLM JSON response string."""
    if priority_issues is None:
        priority_issues = [
            {
                "issue_code": "DX_TITLE_MISSING",
                "interpretation": "Missing title is a potential ranking issue",
                "impact": "Could reduce click-through rates from search results",
                "recommendation": "Add a descriptive title tag",
                "confidence": 0.9,
            }
        ]
    if action_plan is None:
        action_plan = [
            {
                "priority": "P0",
                "action": "Add title tags to all pages",
                "reason": "Missing titles are a critical SEO obstacle",
                "depends_on": [],
            }
        ]
    return json.dumps(
        {
            "summary": summary,
            "priority_issues": priority_issues,
            "action_plan": action_plan,
        }
    )


class MockTransport(httpx.AsyncBaseTransport):
    """Mock HTTP transport that returns pre-configured responses."""

    def __init__(
        self,
        status_code: int = 200,
        json_data: dict | None = None,
        text: str | None = None,
        raise_exc: Exception | None = None,
    ):
        self._status_code = status_code
        self._json_data = json_data
        self._text = text
        self._raise_exc = raise_exc
        self.requests: list[dict] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(
            {
                "method": request.method,
                "url": str(request.url),
                "content": request.content,
            }
        )
        if self._raise_exc:
            raise self._raise_exc
        if self._json_data is not None:
            return httpx.Response(
                status_code=self._status_code,
                json=self._json_data,
            )
        return httpx.Response(
            status_code=self._status_code,
            text=self._text or "",
        )


# ════════════════════════════════════════════════════════════════════════════
# Configuration tests
# ════════════════════════════════════════════════════════════════════════════


class TestLLMConfiguration:
    def test_default_llm_settings_disabled(self):
        settings = Settings(_env_file=None)
        assert settings.llm.enabled is False
        assert settings.llm.api_key == ""
        assert settings.llm.base_url == "https://api.openai.com"
        assert settings.llm.model == "gpt-4o-mini"
        assert settings.llm.timeout_seconds == 60.0
        assert settings.llm.max_tokens == 4096
        assert settings.llm.temperature == 0.3

    def test_llm_settings_from_env(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text(
            "SIE_LLM__ENABLED=true\n"
            "SIE_LLM__API_KEY=sk-test-key-123\n"
            "SIE_LLM__BASE_URL=https://custom.api.com\n"
            "SIE_LLM__MODEL=gpt-4\n"
            "SIE_LLM__TIMEOUT_SECONDS=30\n"
        )
        settings = Settings(_env_file=str(env_file))
        assert settings.llm.enabled is True
        assert settings.llm.api_key == "sk-test-key-123"
        assert settings.llm.base_url == "https://custom.api.com"
        assert settings.llm.model == "gpt-4"
        assert settings.llm.timeout_seconds == 30.0

    def test_llm_settings_validation(self):
        with pytest.raises(ValidationError):
            LLMSettings(timeout_seconds=-1)  # type: ignore[arg-type]
        with pytest.raises(ValidationError):
            LLMSettings(max_tokens=100)  # type: ignore[arg-type]
        with pytest.raises(ValidationError):
            LLMSettings(temperature=-0.1)  # type: ignore[arg-type]

    def test_prompt_version_exists(self):
        assert PROMPT_VERSION is not None
        assert isinstance(PROMPT_VERSION, str)

    def test_system_prompt_is_string(self):
        assert isinstance(SYSTEM_PROMPT, str)
        assert "SEO diagnosis analyst" in SYSTEM_PROMPT


# ════════════════════════════════════════════════════════════════════════════
# Prompt building tests
# ════════════════════════════════════════════════════════════════════════════


class TestPromptBuilding:
    def test_build_user_prompt_contains_evidence(self):
        result = _make_diagnosis_result()
        prompt = build_user_prompt(result)
        assert "test-run" in prompt
        assert "DX_TITLE_MISSING" in prompt
        assert "DX_THIN_CONTENT" in prompt
        assert "https://example.com/no-title" in prompt
        assert "title_present" in prompt

    def test_build_user_prompt_has_schema_instruction(self):
        result = _make_diagnosis_result()
        prompt = build_user_prompt(result)
        assert "REQUIRED OUTPUT SCHEMA" in prompt
        assert "priority_issues" in prompt
        assert "action_plan" in prompt

    def test_build_user_prompt_measured_language(self):
        system = SYSTEM_PROMPT
        assert "potential ranking issue" in system
        assert "SEO risk" in system
        assert "optimization opportunity" in system
        # Verify the prompt instructs against ranking claims
        assert "Do not claim" in system
        assert "ranking change" in system


# ════════════════════════════════════════════════════════════════════════════
# Provider tests — successful response
# ════════════════════════════════════════════════════════════════════════════


class TestOpenAIProviderSuccess:
    @pytest.mark.asyncio
    async def test_generate_returns_content(self):
        transport = MockTransport(
            status_code=200,
            json_data={"choices": [{"message": {"content": "Hello from LLM"}}]},
        )
        client = httpx.AsyncClient(transport=transport)
        provider = OpenAICompatibleProvider(
            base_url="https://api.test.com",
            api_key="sk-test",
            model="test-model",
            client=client,
        )
        result = await provider.generate("System", "User")
        assert result == "Hello from LLM"
        assert len(transport.requests) == 1
        req = json.loads(transport.requests[0]["content"])
        assert req["model"] == "test-model"
        assert req["messages"][0]["role"] == "system"
        assert req["messages"][1]["role"] == "user"
        await provider.close()

    @pytest.mark.asyncio
    async def test_generate_sends_correct_headers(self):
        transport = MockTransport(
            status_code=200,
            json_data={"choices": [{"message": {"content": "ok"}}]},
        )
        client = httpx.AsyncClient(transport=transport)
        provider = OpenAICompatibleProvider(
            base_url="https://api.test.com",
            api_key="sk-my-key",
            client=client,
        )
        await provider.generate("s", "u")
        # Check the request was made to the correct URL
        assert "/v1/chat/completions" in transport.requests[0]["url"]
        await provider.close()

    @pytest.mark.asyncio
    async def test_generate_temperature_and_max_tokens(self):
        transport = MockTransport(
            status_code=200,
            json_data={"choices": [{"message": {"content": "ok"}}]},
        )
        client = httpx.AsyncClient(transport=transport)
        provider = OpenAICompatibleProvider(
            base_url="https://api.test.com",
            api_key="sk-test",
            client=client,
        )
        await provider.generate("s", "u", temperature=0.7, max_tokens=2048)
        req = json.loads(transport.requests[0]["content"])
        assert req["temperature"] == 0.7
        assert req["max_tokens"] == 2048
        await provider.close()


# ════════════════════════════════════════════════════════════════════════════
# Provider tests — timeout
# ════════════════════════════════════════════════════════════════════════════


class TestOpenAIProviderTimeout:
    @pytest.mark.asyncio
    async def test_timeout_raises_llm_timeout_error(self):
        transport = MockTransport(raise_exc=httpx.TimeoutException("timed out"))
        client = httpx.AsyncClient(transport=transport)
        provider = OpenAICompatibleProvider(
            base_url="https://api.test.com",
            api_key="sk-test",
            client=client,
        )
        with pytest.raises(LLMTimeoutError, match="timed out"):
            await provider.generate("s", "u")
        await provider.close()


# ════════════════════════════════════════════════════════════════════════════
# Provider tests — HTTP failures
# ════════════════════════════════════════════════════════════════════════════


class TestOpenAIProviderHTTPFailures:
    @pytest.mark.asyncio
    async def test_401_raises_auth_error(self):
        transport = MockTransport(status_code=401, text="Unauthorized")
        client = httpx.AsyncClient(transport=transport)
        provider = OpenAICompatibleProvider(
            base_url="https://api.test.com",
            api_key="sk-bad",
            client=client,
        )
        with pytest.raises(LLMAuthenticationError, match="invalid or missing"):
            await provider.generate("s", "u")
        await provider.close()

    @pytest.mark.asyncio
    async def test_429_raises_rate_limit_error(self):
        transport = MockTransport(status_code=429, text="Rate limited")
        client = httpx.AsyncClient(transport=transport)
        provider = OpenAICompatibleProvider(
            base_url="https://api.test.com",
            api_key="sk-test",
            client=client,
        )
        with pytest.raises(LLMRateLimitError, match="rate limit"):
            await provider.generate("s", "u")
        await provider.close()

    @pytest.mark.asyncio
    async def test_500_raises_provider_error(self):
        transport = MockTransport(status_code=500, text="Internal Server Error")
        client = httpx.AsyncClient(transport=transport)
        provider = OpenAICompatibleProvider(
            base_url="https://api.test.com",
            api_key="sk-test",
            client=client,
        )
        with pytest.raises(LLMProviderError, match="HTTP 500"):
            await provider.generate("s", "u")
        await provider.close()


# ════════════════════════════════════════════════════════════════════════════
# Provider tests — invalid JSON
# ════════════════════════════════════════════════════════════════════════════


class TestOpenAIProviderInvalidJSON:
    @pytest.mark.asyncio
    async def test_invalid_json_raises_provider_error(self):
        transport = MockTransport(status_code=200, text="not json at all")
        client = httpx.AsyncClient(transport=transport)
        provider = OpenAICompatibleProvider(
            base_url="https://api.test.com",
            api_key="sk-test",
            client=client,
        )
        with pytest.raises(LLMProviderError, match="invalid JSON"):
            await provider.generate("s", "u")
        await provider.close()


# ════════════════════════════════════════════════════════════════════════════
# Provider tests — invalid structured output
# ════════════════════════════════════════════════════════════════════════════


class TestOpenAIProviderInvalidStructure:
    @pytest.mark.asyncio
    async def test_missing_choices_raises_provider_error(self):
        transport = MockTransport(status_code=200, json_data={"data": "no choices here"})
        client = httpx.AsyncClient(transport=transport)
        provider = OpenAICompatibleProvider(
            base_url="https://api.test.com",
            api_key="sk-test",
            client=client,
        )
        with pytest.raises(LLMProviderError, match="missing expected structure"):
            await provider.generate("s", "u")
        await provider.close()

    @pytest.mark.asyncio
    async def test_empty_choices_raises_provider_error(self):
        transport = MockTransport(status_code=200, json_data={"choices": []})
        client = httpx.AsyncClient(transport=transport)
        provider = OpenAICompatibleProvider(
            base_url="https://api.test.com",
            api_key="sk-test",
            client=client,
        )
        with pytest.raises(LLMProviderError, match="missing expected structure"):
            await provider.generate("s", "u")
        await provider.close()


# ════════════════════════════════════════════════════════════════════════════
# Intelligence service tests — LLM disabled
# ════════════════════════════════════════════════════════════════════════════


class TestIntelligenceServiceDisabled:
    @pytest.mark.asyncio
    async def test_llm_none_returns_deterministic_only(self):
        service = IntelligenceService(llm_provider=None)
        diagnosis = _make_diagnosis_result()
        result = await service.reason("run-1", diagnosis)
        assert result.run_id == "run-1"
        assert result.llm_available is False
        assert result.reasoning is None
        assert result.diagnosis is diagnosis

    @pytest.mark.asyncio
    async def test_result_cached(self):
        service = IntelligenceService(llm_provider=None)
        diagnosis = _make_diagnosis_result()
        await service.reason("run-1", diagnosis)
        cached = service.get_result("run-1")
        assert cached is not None
        assert cached.run_id == "run-1"

    @pytest.mark.asyncio
    async def test_get_result_returns_none_for_unknown(self):
        service = IntelligenceService(llm_provider=None)
        assert service.get_result("unknown") is None


# ════════════════════════════════════════════════════════════════════════════
# Intelligence service tests — LLM failure handling
# ════════════════════════════════════════════════════════════════════════════


class TestIntelligenceServiceLLMFailure:
    @pytest.mark.asyncio
    async def test_llm_timeout_returns_deterministic(self):
        transport = MockTransport(raise_exc=httpx.TimeoutException("timeout"))
        client = httpx.AsyncClient(transport=transport)
        provider = OpenAICompatibleProvider(
            base_url="https://api.test.com",
            api_key="sk-test",
            client=client,
        )
        service = IntelligenceService(llm_provider=provider)
        diagnosis = _make_diagnosis_result()
        result = await service.reason("run-2", diagnosis)
        assert result.llm_available is False
        assert result.reasoning is None
        assert result.diagnosis is diagnosis
        await provider.close()

    @pytest.mark.asyncio
    async def test_llm_auth_error_returns_deterministic(self):
        transport = MockTransport(status_code=401, text="Unauthorized")
        client = httpx.AsyncClient(transport=transport)
        provider = OpenAICompatibleProvider(
            base_url="https://api.test.com",
            api_key="sk-bad",
            client=client,
        )
        service = IntelligenceService(llm_provider=provider)
        diagnosis = _make_diagnosis_result()
        result = await service.reason("run-3", diagnosis)
        assert result.llm_available is False
        assert result.reasoning is None
        await provider.close()

    @pytest.mark.asyncio
    async def test_llm_server_error_returns_deterministic(self):
        transport = MockTransport(status_code=500, text="Server Error")
        client = httpx.AsyncClient(transport=transport)
        provider = OpenAICompatibleProvider(
            base_url="https://api.test.com",
            api_key="sk-test",
            client=client,
        )
        service = IntelligenceService(llm_provider=provider)
        diagnosis = _make_diagnosis_result()
        result = await service.reason("run-4", diagnosis)
        assert result.llm_available is False
        assert result.reasoning is None
        await provider.close()


# ════════════════════════════════════════════════════════════════════════════
# Intelligence service tests — successful LLM reasoning
# ════════════════════════════════════════════════════════════════════════════


class TestIntelligenceServiceSuccess:
    @pytest.mark.asyncio
    async def test_successful_llm_reasoning(self):
        llm_json = _mock_llm_response(
            summary="The site has critical meta issues.",
            priority_issues=[
                {
                    "issue_code": "DX_TITLE_MISSING",
                    "interpretation": "Missing titles reduce discoverability",
                    "impact": "Potential ranking issue for affected pages",
                    "recommendation": "Add descriptive titles",
                    "confidence": 0.95,
                }
            ],
            action_plan=[
                {
                    "priority": "P0",
                    "action": "Add title tags",
                    "reason": "Critical SEO obstacle",
                    "depends_on": [],
                }
            ],
        )
        transport = MockTransport(
            status_code=200,
            json_data={"choices": [{"message": {"content": llm_json}}]},
        )
        client = httpx.AsyncClient(transport=transport)
        provider = OpenAICompatibleProvider(
            base_url="https://api.test.com",
            api_key="sk-test",
            client=client,
        )
        service = IntelligenceService(llm_provider=provider)
        diagnosis = _make_diagnosis_result()
        result = await service.reason("run-5", diagnosis)

        assert result.llm_available is True
        assert result.reasoning is not None
        assert result.reasoning.run_id == "test-run"  # from diagnosis.run_id
        assert result.reasoning.summary == "The site has critical meta issues."
        assert len(result.reasoning.priority_issues) == 1
        assert result.reasoning.priority_issues[0].issue_code == "DX_TITLE_MISSING"
        assert result.reasoning.priority_issues[0].confidence == 0.95
        assert len(result.reasoning.action_plan) == 1
        assert result.reasoning.action_plan[0].priority == "P0"
        assert result.diagnosis is diagnosis
        await provider.close()

    @pytest.mark.asyncio
    async def test_llm_response_with_markdown_fences(self):
        llm_json = _mock_llm_response(summary="Wrapped in fences")
        fenced = f"```json\n{llm_json}\n```"
        transport = MockTransport(
            status_code=200,
            json_data={"choices": [{"message": {"content": fenced}}]},
        )
        client = httpx.AsyncClient(transport=transport)
        provider = OpenAICompatibleProvider(
            base_url="https://api.test.com",
            api_key="sk-test",
            client=client,
        )
        service = IntelligenceService(llm_provider=provider)
        diagnosis = _make_diagnosis_result()
        result = await service.reason("run-6", diagnosis)
        assert result.llm_available is True
        assert result.reasoning is not None
        assert result.reasoning.summary == "Wrapped in fences"
        await provider.close()

    @pytest.mark.asyncio
    async def test_llm_invalid_json_returns_deterministic(self):
        transport = MockTransport(
            status_code=200,
            json_data={"choices": [{"message": {"content": "not valid json"}}]},
        )
        client = httpx.AsyncClient(transport=transport)
        provider = OpenAICompatibleProvider(
            base_url="https://api.test.com",
            api_key="sk-test",
            client=client,
        )
        service = IntelligenceService(llm_provider=provider)
        diagnosis = _make_diagnosis_result()
        result = await service.reason("run-7", diagnosis)
        assert result.llm_available is False
        assert result.reasoning is None
        assert result.diagnosis is diagnosis
        await provider.close()

    @pytest.mark.asyncio
    async def test_llm_missing_required_keys_returns_deterministic(self):
        transport = MockTransport(
            status_code=200,
            json_data={"choices": [{"message": {"content": json.dumps({"summary": "hi"})}}]},
        )
        client = httpx.AsyncClient(transport=transport)
        provider = OpenAICompatibleProvider(
            base_url="https://api.test.com",
            api_key="sk-test",
            client=client,
        )
        service = IntelligenceService(llm_provider=provider)
        diagnosis = _make_diagnosis_result()
        result = await service.reason("run-8", diagnosis)
        assert result.llm_available is False
        assert result.reasoning is None
        await provider.close()


# ════════════════════════════════════════════════════════════════════════════
# Response parsing tests
# ════════════════════════════════════════════════════════════════════════════


class TestLLMResponseParsing:
    def test_parse_valid_json(self):
        service = IntelligenceService(llm_provider=None)
        raw = _mock_llm_response(summary="Test")
        result = service._parse_llm_response("run", raw)
        assert isinstance(result, LLMReasoningResult)
        assert result.summary == "Test"

    def test_parse_json_with_code_fences(self):
        service = IntelligenceService(llm_provider=None)
        raw = _mock_llm_response(summary="Fenced")
        fenced = f"```json\n{raw}\n```"
        result = service._parse_llm_response("run", fenced)
        assert result.summary == "Fenced"

    def test_parse_invalid_json_raises(self):
        service = IntelligenceService(llm_provider=None)
        with pytest.raises(ValueError, match="invalid JSON"):
            service._parse_llm_response("run", "not json")

    def test_parse_missing_keys_raises(self):
        service = IntelligenceService(llm_provider=None)
        with pytest.raises(ValueError, match="missing keys"):
            service._parse_llm_response("run", json.dumps({"summary": "hi"}))

    def test_parse_confidence_clamped(self):
        service = IntelligenceService(llm_provider=None)
        raw = _mock_llm_response(
            priority_issues=[
                {
                    "issue_code": "X",
                    "interpretation": "Y",
                    "impact": "Z",
                    "recommendation": "W",
                    "confidence": 1.5,
                }
            ]
        )
        result = service._parse_llm_response("run", raw)
        assert result.priority_issues[0].confidence == 1.0

    def test_parse_negative_confidence_clamped(self):
        service = IntelligenceService(llm_provider=None)
        raw = _mock_llm_response(
            priority_issues=[
                {
                    "issue_code": "X",
                    "interpretation": "Y",
                    "impact": "Z",
                    "recommendation": "W",
                    "confidence": -0.5,
                }
            ]
        )
        result = service._parse_llm_response("run", raw)
        assert result.priority_issues[0].confidence == 0.0


# ════════════════════════════════════════════════════════════════════════════
# Deterministic diagnosis still works when LLM fails
# ════════════════════════════════════════════════════════════════════════════


class TestDeterministicFallback:
    @pytest.mark.asyncio
    async def test_deterministic_result_preserved_on_llm_failure(self):
        transport = MockTransport(raise_exc=httpx.ConnectError("refused"))
        client = httpx.AsyncClient(transport=transport)
        provider = OpenAICompatibleProvider(
            base_url="https://api.test.com",
            api_key="sk-test",
            client=client,
        )
        service = IntelligenceService(llm_provider=provider)
        diagnosis = _make_diagnosis_result("fallback-run")
        result = await service.reason("fallback-run", diagnosis)

        # Deterministic data is preserved
        assert result.run_id == "fallback-run"
        assert result.llm_available is False
        assert result.reasoning is None
        d = result.diagnosis
        assert d.total_issues == 2
        assert d.issues[0].rule_code == "DX_TITLE_MISSING"
        assert d.issues[1].rule_code == "DX_THIN_CONTENT"
        await provider.close()

    @pytest.mark.asyncio
    async def test_multiple_failures_still_return_diagnosis(self):
        """Simulate multiple sequential LLM failures — each returns diagnosis."""

        class AlwaysFailProvider:
            async def generate(self, system_prompt, user_prompt, **kwargs):
                raise LLMProviderError("always fails")

            async def close(self):
                pass

        service = IntelligenceService(llm_provider=AlwaysFailProvider())
        diagnosis = _make_diagnosis_result()
        for i in range(5):
            result = await service.reason(f"run-{i}", diagnosis)
            assert result.llm_available is False
            assert result.diagnosis.total_issues == 2
