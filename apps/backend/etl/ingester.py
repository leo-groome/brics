"""Ingester: StandardizedConcept[] → embeddings → dedupe semántico → insert pgvector."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from models.domain import MasterConcept
from services.embedder import Embedder, concept_to_embed_text

logger = logging.getLogger(__name__)

DEDUPE_COSINE_THRESHOLD = 0.97


@dataclass
class IngestStats:
    inserted: int = 0
    deduped: int = 0
    skipped_invalid: int = 0


def _normalize_pair(technical_concept: str, unit: str) -> tuple[str, str]:
    return technical_concept.strip(), unit.strip().lower()


def ingest_concepts(
    *,
    session: Session,
    embedder: Embedder,
    concepts: list[dict],
    batch_size: int = 100,
) -> IngestStats:
    """Inserta conceptos con dedupe triple:
    (1) in-batch por (technical_concept, unit) — colapsa antes de tocar DB.
    (2) exact match en DB (technical_concept, unit).
    (3) similaridad coseno ≥ DEDUPE_COSINE_THRESHOLD contra vecino más cercano.
    En cualquier caso de dedupe se agrega source_file al concepto existente.
    """
    stats = IngestStats()
    if not concepts:
        return stats

    # ── (1) Dedupe in-batch primero ────────────────────────────────────────────
    seen: dict[tuple[str, str], dict] = {}
    for raw in concepts:
        tc, unit = _normalize_pair(raw["technical_concept"], raw["unit"])
        if not tc or not unit:
            stats.skipped_invalid += 1
            continue
        key = (tc, unit)
        if key in seen:
            # mismo concepto repetido en el lote — junta source_files
            existing_sources = seen[key].setdefault("_sources", [seen[key]["source_file"]])
            if raw.get("source_file") and raw["source_file"] not in existing_sources:
                existing_sources.append(raw["source_file"])
            stats.deduped += 1
            continue
        seen[key] = {
            "family": raw["family"],
            "technical_concept": tc,
            "unit": unit,
            "source_file": raw.get("source_file"),
        }

    if not seen:
        return stats

    unique_concepts = list(seen.values())
    texts_to_embed = [
        concept_to_embed_text(c["family"], c["technical_concept"], c["unit"])
        for c in unique_concepts
    ]
    embeddings = embedder.embed_batch(texts_to_embed, batch_size=batch_size)

    for raw, vec in zip(unique_concepts, embeddings, strict=True):
        tc = raw["technical_concept"]
        unit = raw["unit"]
        family = raw["family"]
        sources = raw.get("_sources") or ([raw["source_file"]] if raw.get("source_file") else [])

        # ── (2) Exact dedupe DB ────────────────────────────────────────────────
        existing = session.execute(
            select(MasterConcept).where(
                MasterConcept.technical_concept == tc, MasterConcept.unit == unit
            )
        ).scalar_one_or_none()

        if existing is not None:
            _merge_sources(existing, sources)
            stats.deduped += 1
            continue

        # ── (3) Cosine dedupe DB ──────────────────────────────────────────────
        nearest = session.execute(
            text(
                """
                SELECT id, 1 - (embedding <=> CAST(:vec AS vector)) AS sim
                FROM master_concepts
                ORDER BY embedding <=> CAST(:vec AS vector)
                LIMIT 1
                """
            ),
            {"vec": str(vec)},
        ).first()

        if nearest and nearest.sim is not None and nearest.sim >= DEDUPE_COSINE_THRESHOLD:
            mc = session.get(MasterConcept, nearest.id)
            if mc is not None:
                _merge_sources(mc, sources)
                stats.deduped += 1
                continue

        # ── Insert nuevo ──────────────────────────────────────────────────────
        mc = MasterConcept(
            family=family,
            technical_concept=tc,
            unit=unit,
            embedding=vec,
            source_files=sources,
        )
        session.add(mc)
        session.flush()  # flush per-row para que las queries siguientes lo encuentren
        stats.inserted += 1

    session.commit()
    return stats


def _merge_sources(concept: MasterConcept, new_sources: list[str]) -> None:
    if not new_sources:
        return
    existing = list(concept.source_files or [])
    changed = False
    for s in new_sources:
        if s and s not in existing:
            existing.append(s)
            changed = True
    if changed:
        concept.source_files = existing
