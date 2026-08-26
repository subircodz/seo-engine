"""Generative Engine Optimization (GEO) provider using LLM APIs.

Implements GEO observation by querying OpenAI-compatible LLM endpoints
with structured prompts and parsing the responses for brand/entity mentions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from sie.domain.models.search import SearchQuery
from sie.domain.models.search_geo import (
    EntityMention,
    EntityType,
    GenerativeEngineType,
    GEOObservation,
)
from sie.infrastructure.llm.openai_provider import OpenAICompatibleProvider
from sie.logging import get_logger

logger = get_logger(__name__)

__all__ = ["GEOLLMProvider", "GEOPromptTemplate"]


@dataclass(frozen=True, slots=True)
class GEOPromptTemplate:
    """Template for generating GEO prompts.

    Attributes
    ----------
    system_prompt:
        System prompt that sets the behavior of the LLM.
    user_prompt_template:
        User prompt template with {keyword} placeholder.
    engine_type:
        The generative engine type this template is designed for.
    """

    system_prompt: str
    user_prompt_template: str
    engine_type: GenerativeEngineType


# Default prompt templates for different GEO scenarios
DEFAULT_GEO_TEMPLATES: dict[GenerativeEngineType, list[GEOPromptTemplate]] = {
    GenerativeEngineType.CHATGPT: [
        GEOPromptTemplate(
            system_prompt=(
                "You are a helpful assistant that provides comprehensive, accurate answers. "
                "When mentioning brands, companies, or products, be specific and factual."
            ),
            user_prompt_template=(
                "Answer the following question comprehensively: {keyword}"
            ),
            engine_type=GenerativeEngineType.CHATGPT,
        ),
        GEOPromptTemplate(
            system_prompt=(
                "You are a helpful assistant that provides comprehensive, accurate answers. "
                "When mentioning brands, companies, or products, be specific and factual."
            ),
            user_prompt_template=(
                "What are the best options for {keyword}? Please provide a detailed comparison."
            ),
            engine_type=GenerativeEngineType.CHATGPT,
        ),
    ],
    GenerativeEngineType.PERPLEXITY: [
        GEOPromptTemplate(
            system_prompt=(
                "You are a research assistant that provides well-cited, factual answers. "
                "Always cite your sources and mention specific brands, companies, and products."
            ),
            user_prompt_template=(
                "Research and provide a comprehensive answer with citations: {keyword}"
            ),
            engine_type=GenerativeEngineType.PERPLEXITY,
        ),
    ],
    GenerativeEngineType.CLAUDE: [
        GEOPromptTemplate(
            system_prompt=(
                "You are a helpful, accurate assistant. Provide thorough, nuanced answers. "
                "Mention specific brands, companies, and products when relevant."
            ),
            user_prompt_template=(
                "Please provide a detailed analysis of: {keyword}"
            ),
            engine_type=GenerativeEngineType.CLAUDE,
        ),
    ],
    GenerativeEngineType.GEMINI: [
        GEOPromptTemplate(
            system_prompt=(
                "You are a helpful assistant that provides comprehensive, accurate answers. "
                "Mention specific brands, companies, and products when relevant."
            ),
            user_prompt_template=(
                "Answer the following question in detail: {keyword}"
            ),
            engine_type=GenerativeEngineType.GEMINI,
        ),
    ],
    GenerativeEngineType.OTHER: [
        GEOPromptTemplate(
            system_prompt=(
                "You are a helpful assistant that provides comprehensive, accurate answers. "
                "Mention specific brands, companies, and products when relevant."
            ),
            user_prompt_template=(
                "Answer the following question: {keyword}"
            ),
            engine_type=GenerativeEngineType.OTHER,
        ),
    ],
}


class GEOLLMProvider:
    """GEO provider using OpenAI-compatible LLM APIs.

    This provider executes structured prompts against a configured LLM
    and extracts brand/entity mentions from the responses to create
    ``GEOObservation`` objects.

    Parameters
    ----------
    llm_provider:
        Configured ``OpenAICompatibleProvider`` instance.
    templates:
        Optional custom prompt templates. If not provided, uses
        ``DEFAULT_GEO_TEMPLATES``.
    target_brand_names:
        List of brand names to detect as the target (case-insensitive).
    competitor_domains:
        List of competitor domains/brands to track.
    """

    def __init__(
        self,
        llm_provider: OpenAICompatibleProvider,
        *,
        templates: dict[GenerativeEngineType, list[GEOPromptTemplate]] | None = None,
        target_brand_names: list[str] | None = None,
        competitor_domains: list[str] | None = None,
    ) -> None:
        self._llm = llm_provider
        self._templates = templates or DEFAULT_GEO_TEMPLATES
        self._target_brands = [b.casefold() for b in (target_brand_names or [])]
        self._competitor_domains = [d.casefold() for d in (competitor_domains or [])]

    @property
    def supports_geo(self) -> bool:
        """This provider supports GEO queries via LLM."""
        return True

    @property
    def supports_aio(self) -> bool:
        """This provider does not support AIO extraction."""
        return False

    async def query_geo(
        self,
        query: SearchQuery,
        target_domain: str,
        engine_type: GenerativeEngineType,
    ) -> GEOObservation | None:
        """Query the LLM for a GEO observation.

        Uses the configured prompt templates for the engine type,
        extracts brand/entity mentions from the response, and returns
        a structured GEOObservation.
        """
        templates = self._templates.get(engine_type, self._templates[GenerativeEngineType.OTHER])

        # For now, use the first template. In the future, we could cycle through
        # multiple templates or select based on query intent.
        template = templates[0]

        user_prompt = template.user_prompt_template.format(keyword=query.query)

        try:
            response_text = await self._llm.generate(
                system_prompt=template.system_prompt,
                user_prompt=user_prompt,
                temperature=0.3,
                max_tokens=4096,
            )
        except Exception as exc:
            logger.warning("GEO LLM query failed for %r: %s", query.query, exc)
            raise

        return self._parse_geo_response(
            keyword=query.query,
            engine_type=engine_type,
            target_domain=target_domain,
            response_text=response_text,
        )

    async def extract_aio(
        self, query: SearchQuery, target_domain: str
    ) -> None:
        """This provider does not support AIO extraction."""
        return None

    def _parse_geo_response(
        self,
        keyword: str,
        engine_type: GenerativeEngineType,
        target_domain: str,
        response_text: str,
    ) -> GEOObservation:
        """Parse LLM response for brand/entity mentions."""
        target_domain_normalized = target_domain.casefold().removeprefix("www.")
        target_mentioned = False
        mention_count = 0
        entity_mentions: list[EntityMention] = []
        competitor_domains: set[str] = set()
        citation_urls: list[str] = []

        # Extract URLs from response (citations)
        url_pattern = r'https?://[^\s\)\]\}>]+'
        for match in re.finditer(url_pattern, response_text):
            url = match.group(0).rstrip('.,;:!?)')
            parsed = urlparse(url)
            if parsed.scheme in ("http", "https") and parsed.netloc:
                domain = parsed.netloc.split(":")[0].casefold()
                if domain.startswith("www."):
                    domain = domain[4:]
                if domain not in citation_urls:
                    citation_urls.append(url)
                if domain != target_domain_normalized and domain not in self._competitor_domains:
                    competitor_domains.add(domain)

        # Check for target brand mentions
        for brand in self._target_brands:
            # Use word boundaries for more accurate matching
            pattern = rf'\b{re.escape(brand)}\b'
            matches = list(re.finditer(pattern, response_text, re.IGNORECASE))
            if matches:
                target_mentioned = True
                mention_count += len(matches)
                for match in matches:
                    entity_mentions.append(EntityMention(
                        text=match.group(0),
                        entity_type=EntityType.BRAND,
                        is_target=True,
                        domain=target_domain_normalized,
                    ))

        # Check for competitor brand mentions
        for comp_domain in self._competitor_domains:
            # Simple domain/brand matching - in practice, this would use
            # a more sophisticated entity recognition approach
            pattern = rf'\b{re.escape(comp_domain)}\b'
            matches = list(re.finditer(pattern, response_text, re.IGNORECASE))
            if matches:
                competitor_domains.add(comp_domain)
                for match in matches:
                    entity_mentions.append(EntityMention(
                        text=match.group(0),
                        entity_type=EntityType.BRAND,
                        is_target=False,
                        domain=comp_domain,
                    ))

        # Also check for any domain-like patterns that might be competitors
        domain_pattern = r'\b[a-z0-9][-a-z0-9]*\.[a-z]{2,}\b'
        known_tlds = ["com", "org", "net", "io", "co", "ai", "app"]
        for match in re.finditer(domain_pattern, response_text, re.IGNORECASE):
            domain = match.group(0).casefold()
            if domain != target_domain_normalized and domain not in self._competitor_domains:
                # Check if it's a known TLD pattern (not just any word.word)
                if not any(domain.endswith(f".{tld}") for tld in known_tlds):
                    continue
                competitor_domains.add(domain)

        return GEOObservation(
            keyword=keyword,
            engine_type=engine_type,
            target_mentioned=target_mentioned,
            target_domain=target_domain,
            mention_count=mention_count,
            entity_mentions=tuple(entity_mentions),
            competitor_domains=tuple(sorted(competitor_domains)),
            citation_urls=tuple(citation_urls),
            answer_length=len(response_text),
            source=f"llm-{engine_type.value}",
        )

    async def close(self) -> None:
        """Close the underlying LLM provider."""
        await self._llm.close()

