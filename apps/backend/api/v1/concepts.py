"""Concepts API — historial de precios y estadísticas por concepto maestro."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from models.database import get_db
from models.domain import ConceptPrice, MasterConcept
from services.prices import get_last_price, get_price_history, get_price_stats

router = APIRouter(prefix="/concepts", tags=["concepts"])


# ---------------------------------------------------------------------------
# Pydantic response models
# ---------------------------------------------------------------------------


class PriceOut(BaseModel):
    id: int
    concept_id: int
    unit_price: float
    unit: Optional[str]
    source_file: Optional[str]
    project_name: Optional[str]
    region: Optional[str]
    observed_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class StatsOut(BaseModel):
    count: int
    last_price: Optional[float]
    last_observed_at: Optional[datetime]
    min: Optional[float]
    max: Optional[float]
    avg: Optional[float]
    median: Optional[float]


class ConceptOut(BaseModel):
    id: int
    family: str
    technical_concept: str
    unit: str
    last_price: Optional[float]

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_concept_or_404(db: Session, concept_id: int) -> MasterConcept:
    concept = db.get(MasterConcept, concept_id)
    if concept is None:
        raise HTTPException(status_code=404, detail="Concepto no encontrado")
    return concept


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/{concept_id}/prices", response_model=list[PriceOut])
def list_prices(
    concept_id: int,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> list[PriceOut]:
    """Historial de precios de un concepto maestro, del más nuevo al más antiguo."""
    _get_concept_or_404(db, concept_id)
    rows = get_price_history(db, concept_id, limit=limit)
    return [PriceOut.model_validate(r) for r in rows]


@router.get("/{concept_id}/price-stats", response_model=StatsOut)
def price_stats(
    concept_id: int,
    db: Session = Depends(get_db),
) -> StatsOut:
    """Estadísticas agregadas (min, max, avg, mediana, último precio) para un concepto."""
    _get_concept_or_404(db, concept_id)
    stats = get_price_stats(db, concept_id)
    return StatsOut(**stats)


@router.get("/{concept_id}", response_model=ConceptOut)
def get_concept(
    concept_id: int,
    db: Session = Depends(get_db),
) -> ConceptOut:
    """Información básica de un concepto maestro más su último precio observado."""
    concept = _get_concept_or_404(db, concept_id)
    last = get_last_price(db, concept_id)
    return ConceptOut(
        id=concept.id,
        family=concept.family,
        technical_concept=concept.technical_concept,
        unit=concept.unit,
        last_price=last.unit_price if last else None,
    )
