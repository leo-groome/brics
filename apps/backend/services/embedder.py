"""Embeddings locales con sentence-transformers (multilingual-e5-large, 1024-dim).

Sin API key, sin $, offline. Filosofía Valta: "el backend es el ancla de la realidad física".

Modelo: intfloat/multilingual-e5-large
  - 1024 dimensiones
  - Entrenado para retrieval multilingüe (Español técnico OK)
  - ~560M parámetros, ~2GB en disco
  - CPU: ~50-100 textos/s

Convenciones del modelo E5: prefijar inputs con "passage: " (al indexar) y "query: " (al buscar).
"""

from __future__ import annotations

import logging
import threading
from typing import Iterable

logger = logging.getLogger(__name__)

EMBEDDING_MODEL_NAME = "intfloat/multilingual-e5-large"
EMBEDDING_DIM = 1024

_model_lock = threading.Lock()
_model = None


def _get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                # Import lazy para no cargar torch hasta primer uso.
                from sentence_transformers import SentenceTransformer

                logger.info("Cargando modelo de embeddings: %s", EMBEDDING_MODEL_NAME)
                _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _model


class Embedder:
    def embed(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: Iterable[str], batch_size: int = 32) -> list[list[float]]:
        items = [f"passage: {t}" for t in texts]
        model = _get_model()
        vectors = model.encode(
            items,
            batch_size=batch_size,
            normalize_embeddings=True,  # vectores unitarios → cosine ≡ dot product
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return [v.tolist() for v in vectors]

    def embed_query(self, text: str) -> list[float]:
        """Variante para queries (runtime BOM matching). El prefijo cambia per docs E5."""
        model = _get_model()
        v = model.encode(
            [f"query: {text}"],
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )[0]
        return v.tolist()


def concept_to_embed_text(family: str, technical_concept: str, unit: str) -> str:
    return f"{family} :: {technical_concept} ({unit})"
