"""Interfaz LLM swappable. Implementaciones:
  - CodexCLIClient: usa `codex exec` (ChatGPT subscription, sin API key).
  - HermesClient: target final cuando Hermes MCP esté listo.
  - OpenAIClient: opcional, requiere OPENAI_API_KEY (fallback).

El normalizer ETL y el price-parser de WhatsApp consumen esto sin saber qué backend hay debajo.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Protocol, Type, TypeVar

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMClient(Protocol):
    def structured_extract(
        self,
        *,
        system_prompt: str,
        user_content: str,
        schema: Type[T],
        max_retries: int = 2,
    ) -> T | None: ...


# ──────────────────────────────────────────────────────────────────────────────
# Codex CLI — default backend (ChatGPT subscription)
# ──────────────────────────────────────────────────────────────────────────────


class CodexCLIClient:
    def __init__(self, model: str | None = None, timeout: int = 180):
        self.model = model
        self.timeout = timeout

    def structured_extract(
        self,
        *,
        system_prompt: str,
        user_content: str,
        schema: Type[T],
        max_retries: int = 2,
    ) -> T | None:
        json_schema = self._pydantic_to_json_schema(schema)
        prompt = self._build_prompt(system_prompt, user_content, json_schema)

        for attempt in range(max_retries + 1):
            with tempfile.TemporaryDirectory() as tmpdir:
                out_path = Path(tmpdir) / "out.txt"

                cmd = [
                    "codex",
                    "exec",
                    "--skip-git-repo-check",
                    "-s",
                    "read-only",
                    "--ephemeral",
                    "--output-last-message",
                    str(out_path),
                    "--color",
                    "never",
                    "-",
                ]
                if self.model:
                    cmd.extend(["-m", self.model])

                try:
                    res = subprocess.run(
                        cmd, input=prompt, capture_output=True, text=True, timeout=self.timeout
                    )
                except subprocess.TimeoutExpired:
                    logger.warning("codex exec timeout (attempt %d)", attempt)
                    continue

                if res.returncode != 0:
                    logger.warning(
                        "codex exec rc=%d (attempt %d): %s",
                        res.returncode,
                        attempt,
                        (res.stderr or "")[:400],
                    )
                    continue

                if not out_path.exists():
                    logger.warning("codex exec produced no output file (attempt %d)", attempt)
                    continue

                raw = out_path.read_text(encoding="utf-8").strip()
                if not raw:
                    logger.warning("codex output vacío (attempt %d)", attempt)
                    continue

                json_str = self._extract_json(raw)
                if json_str is None:
                    logger.warning("no se encontró JSON en respuesta (attempt %d): %s", attempt, raw[:200])
                    continue

                try:
                    return schema.model_validate_json(json_str)
                except ValidationError as e:
                    logger.warning("ValidationError (attempt %d): %s", attempt, str(e)[:400])
                    prompt = (
                        f"{self._build_prompt(system_prompt, user_content, json_schema)}\n\n"
                        f"--- INTENTO PREVIO FALLÓ VALIDACIÓN ---\n{e}\n"
                        "Corrige y devuelve JSON estricto al esquema."
                    )
                    continue

        logger.error("CodexCLIClient agotó retries (%d)", max_retries + 1)
        return None

    @staticmethod
    def _build_prompt(system_prompt: str, user_content: str, json_schema: dict) -> str:
        schema_str = json.dumps(json_schema, ensure_ascii=False)
        return (
            f"{system_prompt}\n\n"
            f"--- ESQUEMA JSON OBLIGATORIO ---\n{schema_str}\n\n"
            f"--- ENTRADA ---\n{user_content}\n--- FIN ENTRADA ---\n\n"
            "Responde EXCLUSIVAMENTE con un objeto JSON que cumpla el esquema. "
            "Sin texto introductorio, sin markdown, sin code fences, sin explicaciones. "
            "El JSON debe ser parseable directamente."
        )

    @staticmethod
    def _pydantic_to_json_schema(schema: Type[BaseModel]) -> dict:
        return schema.model_json_schema()

    @staticmethod
    def _extract_json(text: str) -> str | None:
        """Encuentra el primer objeto JSON balanceado en O(n) usando conteo de llaves.

        Ignora `{` y `}` dentro de strings con escapes.
        """
        text = text.strip()
        if text.startswith("```"):
            lines = [l for l in text.splitlines() if not l.startswith("```")]
            text = "\n".join(lines).strip()

        start = text.find("{")
        if start == -1:
            return None

        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == "\\":
                if in_string:
                    escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : i + 1]
                    try:
                        json.loads(candidate)
                        return candidate
                    except json.JSONDecodeError:
                        return None
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Hermes MCP — target final
# ──────────────────────────────────────────────────────────────────────────────


class HermesClient:
    def __init__(self, *args, **kwargs):
        raise NotImplementedError("Hermes MCP no conectado todavía.")


# ──────────────────────────────────────────────────────────────────────────────
# OpenAI directo — fallback opcional
# ──────────────────────────────────────────────────────────────────────────────


class OpenAIClient:
    def __init__(self, model: str = "gpt-4o-mini", api_key: str | None = None):
        from openai import OpenAI  # import lazy: deps opcionales

        self.model = model
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

    def structured_extract(
        self,
        *,
        system_prompt: str,
        user_content: str,
        schema: Type[T],
        max_retries: int = 2,
    ) -> T | None:
        last_err: str | None = None
        for attempt in range(max_retries + 1):
            try:
                user_msg = user_content
                if last_err:
                    user_msg = (
                        f"{user_content}\n\n--- INTENTO PREVIO FALLÓ ---\n"
                        f"Error: {last_err}\nCorrige el JSON al esquema."
                    )
                resp = self.client.beta.chat.completions.parse(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_msg},
                    ],
                    response_format=schema,
                )
                parsed = resp.choices[0].message.parsed
                if parsed is None:
                    last_err = "respuesta vacía"
                    continue
                return parsed
            except ValidationError as e:
                last_err = str(e)
            except Exception as e:  # noqa: BLE001
                last_err = str(e)
        logger.error("OpenAIClient agotó retries: %s", last_err)
        return None


def get_default_llm() -> LLMClient:
    backend = os.getenv("BRICS_LLM_BACKEND", "codex").lower()
    if backend == "hermes":
        return HermesClient()
    if backend == "openai":
        return OpenAIClient(model=os.getenv("BRICS_OPENAI_MODEL", "gpt-4o-mini"))
    return CodexCLIClient(model=os.getenv("BRICS_CODEX_MODEL"))
