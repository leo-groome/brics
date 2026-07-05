"""Cliente LLM único: API con structured outputs (schema Pydantic).

Un solo backend, reproducible y dockerizable. Consumido por el normalizer ETL
y por la extracción de líneas en el upload de presupuestos.

Config:
  OPENAI_API_KEY      (obligatoria)
  BRICS_OPENAI_MODEL  (default: gpt-4o-mini)
"""

from __future__ import annotations

import logging
import os
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


class OpenAIClient:
    def __init__(self, model: str = "gpt-4o-mini", api_key: str | None = None):
        from openai import OpenAI  # import lazy: no cargar en workers que no lo usan

        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY no configurada — el pipeline LLM no puede operar.")
        self.model = model
        self.client = OpenAI(api_key=key)

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
                    logger.warning("respuesta vacía (attempt %d/%d)", attempt + 1, max_retries + 1)
                    continue
                return parsed
            except ValidationError as e:
                last_err = str(e)
                logger.warning("ValidationError (attempt %d/%d): %s", attempt + 1, max_retries + 1, str(e)[:400])
            except Exception as e:  # noqa: BLE001
                last_err = str(e)
                logger.warning("error API (attempt %d/%d): %s", attempt + 1, max_retries + 1, str(e)[:400])
        logger.error("OpenAIClient agotó retries (%d): %s", max_retries + 1, last_err)
        return None


def get_default_llm() -> LLMClient:
    return OpenAIClient(model=os.getenv("BRICS_OPENAI_MODEL", "gpt-4o-mini"))
