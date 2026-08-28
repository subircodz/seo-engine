"""Generative visibility analysis using an OpenAI-compatible LLM.

This adapter is intentionally labelled as an LLM simulation/analysis source.
It must not be presented as a live observation from ChatGPT, Perplexity,
Gemini, Claude, or another generative search engine unless that engine itself
was queried through a real provider adapter.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from sie.domain.models.search import SearchQuery
from sie.domain.models.search_geo import EntityMention, EntityType, GenerativeEngineType, GEOObservation
from sie.infrastructure.llm.openai_provider import OpenAICompatibleProvider
from sie.logging import get_logger

logger = get_logger(__name__)

__all__ = ["GEOLLMProvider", "GEOPromptTemplate"]


@dataclass(frozen=True, slots=True)
class GEOPromptTemplate:
    system_prompt: str
    user_prompt_template: str
    engine_type: GenerativeEngineType


DEFAULT_GEO_TEMPLATES: dict[GenerativeEngineType, list[GEOPromptTemplate]] = {
    GenerativeEngineType.CHATGPT: [
        GEOPromptTemplate(
            system_prompt="You are a helpful assistant that provides comprehensive, accurate answers. When mentioning brands, companies, or products, be specific and factual.",
            user_prompt_template="Answer the following question comprehensively: {keyword}",
            engine_type=GenerativeEngineType.CHATGPT,
        ),
        GEOPromptTemplate(
            system_prompt="You are a helpful assistant that provides comprehensive, accurate answers. When mentioning brands, companies, or products, be specific and factual.",
            user_prompt_template="What are the best options for {keyword}? Please provide a detailed comparison.",
            engine_type=GenerativeEngineType.CHATGPT,
        ),
    ],
    GenerativeEngineType.PERPLEXITY: [
        GEOPromptTemplate(
            system_prompt="You are a research assistant that provides well-cited, factual answers. Always cite your sources and mention specific brands, companies, and products.",
            user_prompt_template="Research and provide a comprehensive answer with citations: {keyword}",
            engine_type=GenerativeEngineType.PERPLEXITY,
        )
    ],
    GenerativeEngineType.CLAUDE: [
        GEOPromptTemplate(
            system_prompt="You are a helpful, accurate assistant. Provide thorough, nuanced answers. Mention specific brands, companies, and products when relevant.",
            user_prompt_template="Please provide a detailed analysis of: {keyword}",
            engine_type=GenerativeEngineType.CLAUDE,
        )
    ],
    GenerativeEngineType.GEMINI: [
        GEOPromptTemplate(
            system_prompt="You are a helpful assistant that provides comprehensive, accurate answers. Mention specific brands, companies, and products when relevant.",
            user_prompt_template="Answer the following question in detail: {keyword}",
            engine_type=GenerativeEngineType.GEMINI,
        )
    ],
    GenerativeEngineType.OTHER: [
        GEOPromptTemplate(
            system_prompt="You are a helpful assistant that provides comprehensive, accurate answers. Mention specific brands, companies, and products when relevant.",
            user_prompt_template="Answer the following question: {keyword}",
            engine_type=GenerativeEngineType.OTHER,
        )
    ],
}


class GEOLLMProvider:
    """Generate a clearly labelled LLM-based GEO simulation."""

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
        return True

    @property
    def supports_aio(self) -> bool:
        return False

    async def query_geo(self, query: SearchQuery, target_domain: str, engine_type: GenerativeEngineType) -> GEOObservation | None:
        templates = self._templates.get(engine_type, self._templates[GenerativeEngineType.OTHER])
        template = templates[0]
        try:
            response_text = await self._llm.generate(
                system_prompt=template.system_prompt,
                user_prompt=template.user_prompt_template.format(keyword=query.query),
                temperature=0.3,
                max_tokens=4096,
            )
        except Exception as exc:
            logger.warning("GEO LLM query failed for %r: %s", query.query, exc)
            raise
        return self._parse_geo_response(query.query, engine_type, target_domain, response_text)

    async def extract_aio(self, query: SearchQuery, target_domain: str) -> None:
        return None

    def _parse_geo_response(self, keyword: str, engine_type: GenerativeEngineType, target_domain: str, response_text: str) -> GEOObservation:
        target_domain_normalized = target_domain.casefold().removeprefix("www.")
        target_mentioned = False
        mention_count = 0
        entity_mentions: list[EntityMention] = []
        competitor_domains: set[str] = set()
        citation_urls: list[str] = []

        for match in re.finditer(r"https?://[^\s\)\]\}>]+", response_text):
            url = match.group(0).rstrip(".,;:!?)")
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                continue
            domain = parsed.netloc.split(":")[0].casefold().removeprefix("www.")
            citation_urls.append(url) if url not in citation_urls else None
            if domain != target_domain_normalized and domain not in self._competitor_domains:
                competitor_domains.add(domain)

        for brand in self._target_brands:
            matches = list(re.finditer(rf"\b{re.escape(brand)}\b", response_text, re.IGNORECASE))
            if matches:
                target_mentioned = True
                mention_count += len(matches)
                entity_mentions.extend(
                    EntityMention(text=m.group(0), entity_type=EntityType.BRAND, is_target=True, domain=target_domain_normalized)
                    for m in matches
                )

        for comp_domain in self._competitor_domains:
            matches = list(re.finditer(rf"\b{re.escape(comp_domain)}\b", response_text, re.IGNORECASE))
            if matches:
                competitor_domains.add(comp_domain)
                entity_mentions.extend(
                    EntityMention(text=m.group(0), entity_type=EntityType.BRAND, is_target=False, domain=comp_domain)
                    for m in matches
                )

        for match in re.finditer(r"\b[a-z0-9][-a-z0-9]*\.[a-z]{2,}\b", response_text, re.IGNORECASE):
            domain = match.group(0).casefold()
            if domain != target_domain_normalized and domain not in self._competitor_domains:
                if any(domain.endswith(f".{tld}") for tld in ("com", "org", "net", "io", "co", "ai", "app")):
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
            source=f"llm-simulation:{engine_type.value}",
        )

    async def close(self) -> None:
        await self._llm.close()
