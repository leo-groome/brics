"""CLI: extrae los 51 XLSX a texto plano y guarda dumps en data/_extracted/."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

# Ajustar import path cuando se corre como script
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from etl.extractor import extract_dir  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main():
    project_root = Path(__file__).resolve().parents[3]
    data_dir = project_root / "data"
    out_dir = data_dir / "_extracted"
    out_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Extrayendo desde %s", data_dir)
    file_dumps = extract_dir(data_dir)

    manifest = []
    total_sheets = 0
    total_rows = 0
    errors = 0

    for fd in file_dumps:
        if fd.error:
            errors += 1
            logger.error("FAIL %s — %s", fd.filename, fd.error)
            manifest.append({"filename": fd.filename, "error": fd.error})
            continue
        file_stem = Path(fd.filename).stem
        file_dir = out_dir / file_stem
        file_dir.mkdir(parents=True, exist_ok=True)

        sheet_entries = []
        for s in fd.sheets:
            safe_sheet = s.sheet_name.strip().replace("/", "_").replace("\\", "_") or "Hoja"
            out_path = file_dir / f"{safe_sheet}.txt"
            out_path.write_text(s.raw_text, encoding="utf-8")
            sheet_entries.append(
                {
                    "sheet_name": s.sheet_name,
                    "out_path": str(out_path.relative_to(project_root)),
                    "n_rows": s.n_rows,
                    "n_cols": s.n_cols,
                    "chars": len(s.raw_text),
                }
            )
            total_sheets += 1
            total_rows += s.n_rows
        manifest.append({"filename": fd.filename, "sheets": sheet_entries})
        logger.info("OK %s — %d hoja(s)", fd.filename, len(fd.sheets))

    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(
        "DONE archivos=%d hojas=%d filas=%d errores=%d manifest=%s",
        len(file_dumps),
        total_sheets,
        total_rows,
        errors,
        manifest_path,
    )


if __name__ == "__main__":
    main()
