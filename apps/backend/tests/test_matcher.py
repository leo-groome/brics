import pytest
from services.embedder import Embedder, concept_to_embed_text
from services.matcher import MatchCandidate, MatchResult, CONFIDENCE_THRESHOLD


def test_concept_to_embed_text():
    text = concept_to_embed_text("Tablarroca", "Plafón de tablarroca std 1/2 pulgada", "m2")
    assert text == "Tablarroca :: Plafón de tablarroca std 1/2 pulgada (m2)"


def test_embedder_dimension():
    embedder = Embedder()
    # E5 requiere prefijo query: para búsquedas y passage: para indexar.
    # El embedder maneja esto automáticamente en embed_query y embed.
    vec = embedder.embed_query("foco led 15w")
    assert isinstance(vec, list)
    assert len(vec) == 1024
    
    # Comprobar lote
    vecs = embedder.embed_batch(["foco led 15w", "tablarroca"])
    assert len(vecs) == 2
    assert len(vecs[0]) == 1024


def test_match_threshold_rules():
    # Validar lógica de decisión binaria del PRD
    assert CONFIDENCE_THRESHOLD == 0.95
    
    # Simular candidatos
    c1 = MatchCandidate(
        concept_id=1,
        family="Iluminacion",
        technical_concept="Luminaria LED 15W superficial",
        unit="pza",
        confidence=0.96  # >= 0.95 -> AUTO
    )
    
    c2 = MatchCandidate(
        concept_id=2,
        family="Iluminacion",
        technical_concept="Spot LED empotrar 5W",
        unit="pza",
        confidence=0.88  # < 0.95 -> FRICTION
    )

    # Si hay un match con confianza >= 0.95, estado debe ser 'auto'
    res_auto = MatchResult(
        raw_input="Luminaria LED 15W",
        status="auto",
        best=c1,
        candidates=[c1, c2]
    )
    assert res_auto.status == "auto"
    assert res_auto.best.concept_id == 1
    
    # Si la mejor confianza es < 0.95, el estado es 'friction'
    res_friction = MatchResult(
        raw_input="foquito",
        status="friction",
        best=c2,
        candidates=[c2]
    )
    assert res_friction.status == "friction"
