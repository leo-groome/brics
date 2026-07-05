"""Webhook Evolution API: recibe respuestas de proveedores por WhatsApp.

Stub — el parser de precio + actualización de BudgetLine se conectan
cuando el cotizador asíncrono Celery esté armado.
"""

from __future__ import annotations

import hmac
import logging
import os
import re
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from models.database import get_db
from models.domain import BudgetLine, QuoteRequest, Supplier

router = APIRouter(prefix="/webhooks/evolution", tags=["webhooks"])
logger = logging.getLogger(__name__)


_PRICE_RE = re.compile(
    r"\$?\s*([0-9]{1,3}(?:[\.,][0-9]{3})*(?:[\.,][0-9]{1,2})?|[0-9]+(?:[\.,][0-9]{1,2})?)"
)


def _extract_price(text: str) -> float | None:
    """Heurística simple. Casos ambiguos → null (queda para revisión humana)."""
    if not text:
        return None
    matches = _PRICE_RE.findall(text)
    if not matches:
        return None
    # Toma el primer número con coma/punto decimal plausible
    for raw in matches:
        cleaned = raw.replace(",", "").replace(" ", "")
        try:
            v = float(cleaned)
            if 0 < v < 10_000_000:
                return v
        except ValueError:
            continue
    return None


def _check_webhook_token(authorization: str | None) -> None:
    expected = os.getenv("EVOLUTION_WEBHOOK_TOKEN")
    if not expected:
        raise HTTPException(503, "EVOLUTION_WEBHOOK_TOKEN no configurado en el backend")
    if not authorization:
        raise HTTPException(401, "Authorization header ausente")
    # Forma esperada: "Bearer <token>"
    prefix, _, provided = authorization.partition(" ")
    if prefix.lower() != "bearer" or not hmac.compare_digest(provided, expected):
        raise HTTPException(401, "token inválido")


@router.post("/incoming")
async def incoming(
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Evolution API entrega un payload con la respuesta de WhatsApp.

    Formato esperado (mínimo):
      { "from": "+52...", "message": "El precio es $1,250", "instance": "..." }
    Headers obligatorios: Authorization: Bearer <EVOLUTION_WEBHOOK_TOKEN>
    """
    _check_webhook_token(authorization)
    body = await request.json()
    sender = (body.get("from") or body.get("phone") or "").strip()
    message = (body.get("message") or body.get("text") or "").strip()

    if not sender or not message:
        raise HTTPException(400, "payload inválido: faltan 'from' o 'message'")

    supplier = db.query(Supplier).filter(Supplier.whatsapp_number == sender).first()
    if not supplier:
        logger.info("Mensaje de número desconocido: %s", sender)
        return {"status": "ignored", "reason": "unknown_sender"}

    pending = (
        db.query(QuoteRequest)
        .filter(QuoteRequest.supplier_id == supplier.id, QuoteRequest.status == "sent")
        .order_by(QuoteRequest.sent_at.desc())
        .first()
    )
    if not pending:
        logger.info("Sin QuoteRequest pendiente para supplier %d", supplier.id)
        return {"status": "ignored", "reason": "no_pending_quote"}

    price = _extract_price(message)
    pending.response_text = message
    pending.response_price = price
    pending.status = "responded" if price else "ambiguous"

    if price:
        bl = db.get(BudgetLine, pending.budget_line_id)
        if bl is not None and bl.unit_price is None:  # primera respuesta gana
            bl.unit_price = price
            bl.price_source = f"supplier:{supplier.id}:{pending.id}"
    db.commit()

    return {"status": "ok", "parsed_price": price, "quote_request_id": pending.id}
