"""Dependencies compartidas de la API: auth por API key → Org (tenant)."""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from models.database import get_db
from models.domain import Org


def get_current_org(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> Org:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Falta header X-API-Key")
    org = db.query(Org).filter(Org.api_key == x_api_key).first()
    if org is None:
        raise HTTPException(status_code=401, detail="API key inválida")
    return org
