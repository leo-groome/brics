"""Dependencies compartidas de la API: auth por API key → Org (tenant).

La DB guarda SHA-256 de la key, nunca el plaintext (se muestra una sola vez
al crear la org). Un dump de la tabla orgs no compromete las keys.
"""

from __future__ import annotations

import hashlib

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from models.database import get_db
from models.domain import Org


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()


def get_current_org(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> Org:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Falta header X-API-Key")
    org = db.query(Org).filter(Org.api_key == hash_api_key(x_api_key)).first()
    if org is None:
        raise HTTPException(status_code=401, detail="API key inválida")
    return org
