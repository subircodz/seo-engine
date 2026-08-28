from datetime import UTC, datetime

from sie.domain.models.search_aio import AIOverviewObservation, AIOverviewType
from sie.domain.models.search_geo import GEOObservation, GenerativeEngineType
from sie.domain.models.search_surface import EvidenceProvenance, ObservationKind


def test_live_aio_is_distinguished_from_simulation() -> None:
    observation = AIOverviewObservation(
        keyword="best example",
        ai_type=AIOverviewType.AI_OVERVIEW,
        present=True,
        source="serpapi",
        provenance=EvidenceProvenance(
            provider_name="serpapi",
            observation_kind=ObservationKind.LIVE_PROVIDER,
            retrieved_at=datetime.now(UTC),
        ),
    )
    assert observation.provenance.observation_kind is ObservationKind.LIVE_PROVIDER
    assert observation.provenance.provider_name == "serpapi"


def test_geo_simulation_cannot_claim_live_engine_evidence() -> None:
    observation = GEOObservation(
        keyword="best example",
        engine_type=GenerativeEngineType.CHATGPT,
        target_mentioned=True,
        source="llm-simulation:chatgpt",
        provenance=EvidenceProvenance(
            provider_name="openai-compatible-llm",
            observation_kind=ObservationKind.LLM_SIMULATION,
            methodology="Prompted model response; not a live ChatGPT query.",
        ),
    )
    assert observation.engine_type is GenerativeEngineType.CHATGPT
    assert observation.provenance.observation_kind is ObservationKind.LLM_SIMULATION
    assert observation.provenance.provider_name != "chatgpt"
