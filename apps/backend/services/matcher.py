"""Matcher: BOM line cruda → match semántico contra Catálogo Maestro.

Decisión binaria PRD: confianza ≥ 0.95 → AUTO; < 0.95 → FRICTION.
Sin buckets intermedios. La friction es el escape humano.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from services.embedder import Embedder

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.95


@dataclass
class MatchCandidate:
    concept_id: int
    family: str
    technical_concept: str
    unit: str
    confidence: float  # cosine similarity ∈ [0, 1]


@dataclass
class MatchResult:
    raw_input: str
    status: str  # "auto" | "friction" | "missing" (vacío catálogo)
    best: MatchCandidate | None
    candidates: list[MatchCandidate]  # top-5 para Friction UI


def _query_top_k(session: Session, query_vector: list[float], k: int = 5) -> list[MatchCandidate]:
    rows = session.execute(
        sql_text(
            """
            SELECT id, family, technical_concept, unit,
                   1 - (embedding <=> CAST(:vec AS vector)) AS confidence
            FROM master_concepts
            ORDER BY embedding <=> CAST(:vec AS vector)
            LIMIT :k
            """
        ),
        {"vec": str(query_vector), "k": k},
    ).all()
    return [
        MatchCandidate(
            concept_id=r.id,
            family=r.family,
            technical_concept=r.technical_concept,
            unit=r.unit,
            confidence=float(r.confidence) if r.confidence is not None else 0.0,
        )
        for r in rows
    ]


def match_line(
    *,
    session: Session,
    embedder: Embedder,
    raw_input: str,
    top_k: int = 5,
) -> MatchResult:
    if not raw_input.strip():
        return MatchResult(raw_input=raw_input, status="friction", best=None, candidates=[])

    query_vec = embedder.embed_query(raw_input)
    candidates = _query_top_k(session, query_vec, k=top_k)

    if not candidates:
        return MatchResult(raw_input=raw_input, status="missing", best=None, candidates=[])

    best = candidates[0]
    status = "auto" if best.confidence >= CONFIDENCE_THRESHOLD else "friction"
    return MatchResult(raw_input=raw_input, status=status, best=best, candidates=candidates)


def match_batch(
    *,
    session: Session,
    embedder: Embedder,
    raw_inputs: list[str],
    top_k: int = 5,
) -> list[MatchResult]:
    return [
        match_line(session=session, embedder=embedder, raw_input=raw, top_k=top_k)
        for raw in raw_inputs
    ]
