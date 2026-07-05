"""Normalizer LLM: dump crudo de hoja → conceptos canónicos sin precios."""

from __future__ import annotations

import logging
import re
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from etl.families import FAMILIES
from services.llm_client import LLMClient

logger = logging.getLogger(__name__)


# Enum dinámico para que Pydantic obligue al modelo a quedarse dentro de FAMILIES.
FamilyEnum = Enum("FamilyEnum", {re.sub(r"\W+", "_", f).strip("_"): f for f in FAMILIES}, type=str)


UNIT_ENUM = Literal[
    "pza", "m2", "m3", "ml", "kg", "ton", "lote", "jgo", "salida", "lt", "ml_cable", "servicio"
]


class StandardizedConcept(BaseModel):
    family: FamilyEnum = Field(description="Familia técnica del concepto (vocabulario cerrado).")
    technical_concept: str = Field(
        description="Descripción canónica del concepto, normalizada y sin precios ni cantidades."
    )
    unit: UNIT_ENUM = Field(description="Unidad normalizada.")

    @field_validator("technical_concept")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class SheetExtraction(BaseModel):
    project_name: str | None = Field(default=None, description="Nombre del proyecto si aparece.")
    project_type: Literal["residencial", "comercial", "agencia_auto", "industrial", "otro"] | None = (
        Field(default=None)
    )
    concepts: list[StandardizedConcept] = Field(default_factory=list)


SYSTEM_PROMPT = f"""Eres un extractor de conceptos técnicos de construcción. Recibirás texto crudo de una hoja de Excel (presupuesto, estimación, catálogo o cotización) en español mexicano.

OBJETIVO: extraer la lista de CONCEPTOS TÉCNICOS canónicos que el archivo describe. NUNCA precios, cantidades, importes ni montos.

REGLAS ESTRICTAS:
1. Ignora completamente: filas de metadata (Obra, Propietario, Fecha, Empresa, Proveedor, Ubicación, Cotización), encabezados de tabla, subtotales, totales, IVA, anticipos, columnas de cantidad/importe/precio, celdas con #REF!, secciones (PRELIMINARES, CIMENTACIÓN, etc. solas), filas vacías.
2. Un CONCEPTO es una descripción técnica de trabajo o material (ej. "Concreto fc=200 kg/cm² en cimentación", "Luminaria LED 15W superficial", "Tablarroca de 1/2 pulgada en muros").
3. NORMALIZA cada concepto: minimiza mayúsculas innecesarias, expande abreviaciones obvias (fc, MR, PVC), conserva especificaciones técnicas clave (calibre, espesor, calidad).
4. Si una misma hoja tiene variantes léxicas del mismo concepto (ej. "tablaroca std 1/2" y "TABLAROCA STANDAR 1/2 PULG"), DEVUELVE UNA SOLA versión canónica.
5. Familia: del enum cerrado: {", ".join(FAMILIES)}. Si dudas → "Otros".
6. Unidad normalizada: pza | m2 | m3 | ml | kg | ton | lote | jgo | salida | lt | ml_cable | servicio. Aliases comunes: PZA=pza, M2/m²=m2, METRO LINEAL=ml, KG/KGS=kg, LOTE/GLOBAL=lote, JUEGO=jgo, SAL/SALIDA=salida.
7. Si la hoja no contiene conceptos técnicos útiles (es un resumen, índice o portada), devuelve concepts=[].
8. Si la descripción técnica es ambigua o solo dice "varios" o "trabajos extra" sin detalle → omítela.

SIN INVENTAR. Solo lo que está en el texto.
"""


def normalize_sheet(
    *,
    llm: LLMClient,
    filename: str,
    sheet_name: str,
    raw_text: str,
    max_chars: int = 60_000,
) -> SheetExtraction | None:
    """Normaliza una hoja. Devuelve None si falla tras los retries del LLM."""
    if not raw_text.strip():
        return SheetExtraction()

    # Hoja muy grande → trocear y mergear. Por ahora truncamos con warning.
    if len(raw_text) > max_chars:
        logger.warning(
            "Hoja %s/%s muy grande (%d chars), truncando a %d",
            filename,
            sheet_name,
            len(raw_text),
            max_chars,
        )
        raw_text = raw_text[:max_chars]

    user_content = (
        f"Archivo: {filename}\nHoja: {sheet_name}\n\n--- DUMP ---\n{raw_text}\n--- FIN DUMP ---"
    )
    return llm.structured_extract(
        system_prompt=SYSTEM_PROMPT,
        user_content=user_content,
        schema=SheetExtraction,
    )
