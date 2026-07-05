"""CLI: normaliza los dumps de data/_extracted/ y los ingesta al Catálogo Maestro.

Uso:
    uv run python apps/backend/etl/run_normalize.py                # full run
    uv run python apps/backend/etl/run_normalize.py --limit 3      # smoke test 3 archivos
    uv run python apps/backend/etl/run_normalize.py --file "..."   # un solo archivo
    uv run python apps/backend/etl/run_normalize.py --dry-run      # sin DB, solo JSON
    uv run python apps/backend/etl/run_normalize.py --workers 4    # paralelizar llamadas LLM
    uv run python apps/backend/etl/run_normalize.py --resume       # saltar archivos ya en _normalized/
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from sqlalchemy import text as sql_text

from etl.ingester import ingest_concepts
from etl.normalizer import normalize_sheet
from models.database import SessionLocal, engine, Base
from models import domain  # noqa: F401 — registra tablas
from services.embedder import Embedder
from services.llm_client import get_default_llm

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def init_db():
    with engine.connect() as conn:
        conn.execute(sql_text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.commit()
    Base.metadata.create_all(bind=engine)


def normalize_one_sheet(
    llm, filename: str, sheet_name: str, raw_text: str
) -> tuple[list[dict], str | None]:
    """Normaliza una hoja. Retorna (concepts, error). error=None si tuvo éxito."""
    result = normalize_sheet(llm=llm, filename=filename, sheet_name=sheet_name, raw_text=raw_text)
    if result is None:
        return [], "llm_agoto_retries: sin JSON válido tras reintentos (ver log para el error de API)"
    out = []
    for c in result.concepts:
        out.append(
            {
                "family": c.family.value if hasattr(c.family, "value") else str(c.family),
                "technical_concept": c.technical_concept,
                "unit": c.unit,
                "source_file": filename,
            }
        )
    return out, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--file", type=str, default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--workers", type=int, default=4, help="Llamadas LLM en paralelo.")
    ap.add_argument("--resume", action="store_true", help="Skip files already in _normalized/.")
    ap.add_argument("--min-chars", type=int, default=300, help="Skip sheets más chicas que esto.")
    args = ap.parse_args()

    project_root = Path(__file__).resolve().parents[3]
    extracted = project_root / "data" / "_extracted"
    manifest_path = extracted / "manifest.json"
    if not manifest_path.exists():
        logger.error("manifest no existe — corre run_extract.py primero")
        sys.exit(1)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if args.file:
        manifest = [m for m in manifest if args.file.lower() in m.get("filename", "").lower()]
    if args.limit:
        manifest = manifest[: args.limit]

    if not args.dry_run:
        init_db()

    llm = get_default_llm()
    embedder = Embedder() if not args.dry_run else None

    audit_dir = extracted / "_normalized"
    audit_dir.mkdir(parents=True, exist_ok=True)

    total_concepts = 0
    total_inserted = 0
    total_deduped = 0
    total_invalid = 0
    failures: list[dict] = []
    skipped_resume = 0

    session = None if args.dry_run else SessionLocal()
    try:
        for file_idx, entry in enumerate(manifest, 1):
            filename = entry.get("filename")
            if entry.get("error"):
                logger.warning("SKIP %s (error en extracción)", filename)
                continue

            audit_path = audit_dir / f"{Path(filename).stem}.json"
            if args.resume and audit_path.exists():
                skipped_resume += 1
                logger.info("[%d/%d] RESUME-SKIP %s", file_idx, len(manifest), filename)
                if not args.dry_run:
                    file_concepts = json.loads(audit_path.read_text(encoding="utf-8"))
                    if file_concepts:
                        stats = ingest_concepts(session=session, embedder=embedder, concepts=file_concepts)
                        total_inserted += stats.inserted
                        total_deduped += stats.deduped
                        total_invalid += stats.skipped_invalid
                continue

            sheets = entry.get("sheets", [])
            # Filtrar hojas vacías o demasiado chicas
            jobs = []
            for s in sheets:
                dump_path = project_root / s["out_path"]
                raw = dump_path.read_text(encoding="utf-8")
                if len(raw.strip()) < args.min_chars:
                    continue
                jobs.append((s["sheet_name"], raw))

            t0 = time.time()
            logger.info("[%d/%d] %s — %d hojas a normalizar", file_idx, len(manifest), filename, len(jobs))

            file_concepts: list[dict] = []
            if jobs:
                with ThreadPoolExecutor(max_workers=args.workers) as pool:
                    future_to_sheet = {
                        pool.submit(normalize_one_sheet, llm, filename, sn, raw): sn for sn, raw in jobs
                    }
                    for fut in as_completed(future_to_sheet):
                        sn = future_to_sheet[fut]
                        try:
                            concepts, error = fut.result()
                        except Exception as e:  # noqa: BLE001
                            logger.exception("normalize_one_sheet exception en %s", sn)
                            error = f"exception: {type(e).__name__}: {str(e)[:300]}"
                            concepts = []
                        if error is not None:
                            failures.append({"file": filename, "sheet": sn, "error": error})
                            continue
                        file_concepts.extend(concepts)

            elapsed = time.time() - t0
            total_concepts += len(file_concepts)
            logger.info(
                "  → %s extrajo %d conceptos en %.1fs",
                filename,
                len(file_concepts),
                elapsed,
            )

            audit_path.write_text(json.dumps(file_concepts, ensure_ascii=False, indent=2), encoding="utf-8")

            if args.dry_run or not file_concepts:
                continue
            stats = ingest_concepts(session=session, embedder=embedder, concepts=file_concepts)
            total_inserted += stats.inserted
            total_deduped += stats.deduped
            total_invalid += stats.skipped_invalid
            logger.info(
                "  → INGEST inserted=%d deduped=%d invalid=%d",
                stats.inserted,
                stats.deduped,
                stats.skipped_invalid,
            )
    finally:
        if session is not None:
            session.close()

    logger.info(
        "DONE files=%d concepts_extraidos=%d inserted=%d deduped=%d invalid=%d failures=%d resume_skipped=%d",
        len(manifest),
        total_concepts,
        total_inserted,
        total_deduped,
        total_invalid,
        len(failures),
        skipped_resume,
    )
    if failures:
        out = extracted / "normalize_failures.json"
        out.write_text(json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.warning("Failures → %s", out)


if __name__ == "__main__":
    main()
