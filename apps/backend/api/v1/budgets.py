"""Endpoints de Budgets: creación + ingesta de BOM con match semántico inmediato."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from models.database import get_db
from models.domain import Budget, BudgetLine
from services.embedder import Embedder
from services.matcher import match_batch

router = APIRouter(prefix="/budgets", tags=["budgets"])

_embedder = Embedder()


class BudgetCreate(BaseModel):
    project_name: str | None = None
    project_type: Literal["residencial", "comercial", "agencia_auto", "industrial", "otro"] | None = (
        None
    )
    region: str | None = "Aguascalientes"


class BudgetOut(BaseModel):
    id: int
    project_name: str | None
    project_type: str | None
    region: str | None
    status: str

    model_config = {"from_attributes": True}


class BomLineIn(BaseModel):
    raw_input: str = Field(min_length=1)
    quantity: float | None = None
    unit: str | None = None


class BomBulkIn(BaseModel):
    lines: list[BomLineIn]


class BudgetLineOut(BaseModel):
    id: int
    raw_input: str
    quantity: float | None
    unit: str | None
    matched_concept_id: int | None
    match_confidence: float | None
    match_status: str
    unit_price: float | None

    model_config = {"from_attributes": True}


@router.post("", response_model=BudgetOut, status_code=201)
def create_budget(payload: BudgetCreate, db: Session = Depends(get_db)) -> BudgetOut:
    b = Budget(
        project_name=payload.project_name,
        project_type=payload.project_type,
        region=payload.region,
        status="draft",
    )
    db.add(b)
    db.commit()
    db.refresh(b)
    return b


@router.get("/{budget_id}", response_model=BudgetOut)
def get_budget(budget_id: int, db: Session = Depends(get_db)) -> BudgetOut:
    b = db.get(Budget, budget_id)
    if b is None:
        raise HTTPException(404, "Budget no encontrado")
    return b


@router.get("/{budget_id}/lines", response_model=list[BudgetLineOut])
def list_lines(budget_id: int, db: Session = Depends(get_db)) -> list[BudgetLineOut]:
    b = db.get(Budget, budget_id)
    if b is None:
        raise HTTPException(404, "Budget no encontrado")
    return b.lines


@router.post("/{budget_id}/lines/bulk", response_model=list[BudgetLineOut], status_code=201)
def add_lines_bulk(
    budget_id: int, payload: BomBulkIn, db: Session = Depends(get_db)
) -> list[BudgetLineOut]:
    """Ingesta del BOM crudo. Match semántico inmediato por línea.

    >= 0.95 confianza → match_status='auto'
    <  0.95 confianza → match_status='friction'
    Catálogo vacío    → match_status='missing'
    """
    b = db.get(Budget, budget_id)
    if b is None:
        raise HTTPException(404, "Budget no encontrado")

    results = match_batch(
        session=db,
        embedder=_embedder,
        raw_inputs=[l.raw_input for l in payload.lines],
        top_k=5,
    )

    created: list[BudgetLine] = []
    for line_in, result in zip(payload.lines, results, strict=True):
        # Serializa top-K para que /friction/pending no tenga que re-embedear.
        candidates_json = [
            {
                "concept_id": c.concept_id,
                "family": c.family,
                "technical_concept": c.technical_concept,
                "unit": c.unit,
                "confidence": c.confidence,
            }
            for c in result.candidates
        ]
        bl = BudgetLine(
            budget_id=budget_id,
            raw_input=line_in.raw_input,
            quantity=line_in.quantity,
            unit=(result.best.unit if result.best and result.status == "auto" else line_in.unit),
            matched_concept_id=result.best.concept_id if result.best and result.status == "auto" else None,
            match_confidence=result.best.confidence if result.best else None,
            match_status=result.status,
            top_candidates=candidates_json,
        )
        db.add(bl)
        created.append(bl)
    db.commit()
    for bl in created:
        db.refresh(bl)
        if bl.match_status == "auto":
            try:
                from workers.tasks import quote_line_task
                quote_line_task.delay(bl.id)
            except Exception as e:
                # Si Celery/Redis no está corriendo, registrar log y continuar (tolerante a fallos)
                logger.error("No se pudo encolar la tarea de cotización para la línea %d: %s", bl.id, str(e))
    return created

