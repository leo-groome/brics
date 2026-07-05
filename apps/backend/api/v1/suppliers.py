"""Suppliers CRUD básico para alimentar el cotizador asíncrono."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from models.database import get_db
from models.domain import Supplier

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


class SupplierIn(BaseModel):
    name: str = Field(min_length=2)
    whatsapp_number: str = Field(min_length=8)
    families: list[str] = Field(default_factory=list)
    active: bool = True


class SupplierOut(BaseModel):
    id: int
    name: str
    whatsapp_number: str
    families: list[str]
    active: bool

    model_config = {"from_attributes": True}


def _to_out(s: Supplier) -> SupplierOut:
    return SupplierOut(
        id=s.id,
        name=s.name,
        whatsapp_number=s.whatsapp_number,
        families=list(s.families or []),
        active=bool(s.active),
    )


@router.post("", response_model=SupplierOut, status_code=201)
def create(payload: SupplierIn, db: Session = Depends(get_db)) -> SupplierOut:
    existing = db.query(Supplier).filter(Supplier.whatsapp_number == payload.whatsapp_number).first()
    if existing:
        raise HTTPException(409, "WhatsApp ya registrado")
    s = Supplier(
        name=payload.name,
        whatsapp_number=payload.whatsapp_number,
        families=payload.families,
        active=1 if payload.active else 0,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return _to_out(s)


@router.get("", response_model=list[SupplierOut])
def list_all(db: Session = Depends(get_db)) -> list[SupplierOut]:
    return [_to_out(s) for s in db.query(Supplier).order_by(Supplier.id).all()]


@router.delete("/{supplier_id}", status_code=204)
def delete(supplier_id: int, db: Session = Depends(get_db)):
    s = db.get(Supplier, supplier_id)
    if s is None:
        raise HTTPException(404, "Supplier no encontrado")
    db.delete(s)
    db.commit()
