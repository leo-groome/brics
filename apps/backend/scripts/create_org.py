"""CLI: alta de una constructora (tenant) con su API key.

Uso:
    uv run python scripts/create_org.py "Constructora Piloto 1"
"""

from __future__ import annotations

import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.deps import hash_api_key
from models.database import SessionLocal
from models.domain import Org


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    name = sys.argv[1].strip()
    api_key = f"brics_{secrets.token_urlsafe(32)}"

    with SessionLocal() as db:
        if db.query(Org).filter(Org.name == name).first():
            print(f"ERROR: ya existe org '{name}'")
            sys.exit(1)
        # Se guarda el hash; el plaintext solo se imprime aquí, una vez.
        org = Org(name=name, api_key=hash_api_key(api_key))
        db.add(org)
        db.commit()
        db.refresh(org)
        print(f"org_id={org.id}  name={org.name}")
        print(f"API key (guárdala, no se vuelve a mostrar en logs): {api_key}")


if __name__ == "__main__":
    main()
