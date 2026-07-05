"""Endpoints de Matriz de Fricción: pendientes + resolución por línea."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from models.database import get_db
from models.domain import BudgetLine, MasterConcept
from services.embedder import Embedder, concept_to_embed_text

router = APIRouter(prefix="/friction", tags=["friction"])

_embedder = Embedder()


class CandidateOut(BaseModel):
    concept_id: int
    family: str
    technical_concept: str
    unit: str
    confidence: float


class FrictionItemOut(BaseModel):
    budget_line_id: int
    budget_id: int
    raw_input: str
    quantity: float | None
    top_candidates: list[CandidateOut]


class SelectCandidatePayload(BaseModel):
    action: Literal["select_candidate"] = "select_candidate"
    concept_id: int


class CreateNewConceptPayload(BaseModel):
    action: Literal["create_new_concept"] = "create_new_concept"
    family: str
    technical_concept: str = Field(min_length=3)
    unit: str


class DiscardPayload(BaseModel):
    action: Literal["discard"] = "discard"


@router.get("/pending", response_model=list[FrictionItemOut])
def list_pending(limit: int = 50, db: Session = Depends(get_db)) -> list[FrictionItemOut]:
    rows = (
        db.query(BudgetLine)
        .filter(BudgetLine.match_status == "friction")
        .order_by(BudgetLine.id)
        .limit(limit)
        .all()
    )
    out: list[FrictionItemOut] = []
    for bl in rows:
        cached = bl.top_candidates or []
        out.append(
            FrictionItemOut(
                budget_line_id=bl.id,
                budget_id=bl.budget_id,
                raw_input=bl.raw_input,
                quantity=bl.quantity,
                top_candidates=[
                    CandidateOut(
                        concept_id=c["concept_id"],
                        family=c["family"],
                        technical_concept=c["technical_concept"],
                        unit=c["unit"],
                        confidence=c["confidence"],
                    )
                    for c in cached
                ],
            )
        )
    return out


@router.post("/{budget_line_id}/resolve", status_code=200)
def resolve(
    budget_line_id: int,
    payload: SelectCandidatePayload | CreateNewConceptPayload | DiscardPayload,
    db: Session = Depends(get_db),
):
    bl = db.get(BudgetLine, budget_line_id)
    if bl is None:
        raise HTTPException(404, "BudgetLine no encontrada")
    if bl.match_status != "friction":
        raise HTTPException(409, f"línea ya está en estado '{bl.match_status}'")

    if payload.action == "select_candidate":
        mc = db.get(MasterConcept, payload.concept_id)
        if mc is None:
            raise HTTPException(404, "MasterConcept no encontrado")
        bl.matched_concept_id = mc.id
        bl.unit = mc.unit
        bl.match_confidence = 1.0  # decisión humana = certeza
        bl.match_status = "resolved"
        db.commit()
        try:
            from workers.tasks import quote_line_task
            quote_line_task.delay(bl.id)
        except Exception as e:
            # logger no está importado como objeto global logger en friction.py? Vamos a revisar si logger existe.
            # En la línea 15 dice: router = APIRouter(prefix="/friction", tags=["friction"])
            # Pero arriba no vimos logger importado. Importemos y usemos logger.
            import logging
            logging.getLogger(__name__).error("No se pudo encolar la tarea de cotización para la línea %d: %s", bl.id, str(e))
        return {"status": "resolved", "matched_concept_id": mc.id}

    if payload.action == "create_new_concept":
        # Embedding del concepto canonicalizado (no del raw_input — el humano ya lo curó)
        vec = _embedder.embed(
            concept_to_embed_text(payload.family, payload.technical_concept, payload.unit)
        )
        mc = MasterConcept(
            family=payload.family,
            technical_concept=payload.technical_concept.strip(),
            unit=payload.unit.strip().lower(),
            embedding=vec,
            source_files=[f"friction:budget_line_{bl.id}"],
        )
        db.add(mc)
        db.flush()
        bl.matched_concept_id = mc.id
        bl.unit = mc.unit
        bl.match_confidence = 1.0
        bl.match_status = "resolved"
        db.commit()
        try:
            from workers.tasks import quote_line_task
            quote_line_task.delay(bl.id)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error("No se pudo encolar la tarea de cotización para la línea %d: %s", bl.id, str(e))
        return {"status": "resolved", "matched_concept_id": mc.id, "new_concept": True}

    if payload.action == "discard":
        db.delete(bl)
        db.commit()
        return {"status": "discarded"}


    raise HTTPException(400, "acción desconocida")
