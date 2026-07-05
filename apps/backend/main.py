import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from api.v1 import budgets as budgets_router
from api.v1 import concepts as concepts_router
from api.v1 import friction as friction_router
from models.database import engine, Base
from models import domain  # noqa: F401 — register tables on Base.metadata
from services import embedder as embedder_module

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Inicializando Base de Datos...")
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
        conn.commit()
    Base.metadata.create_all(bind=engine)
    logger.info("Base de Datos OK.")

    # Pre-carga del modelo de embeddings (2GB) para que el primer request no espere 15-30s.
    logger.info("Pre-cargando modelo de embeddings...")
    embedder_module._get_model()
    logger.info("Embedder listo.")

    yield
    logger.info("Apagando aplicación...")


app = FastAPI(
    title="Brics Core API",
    description="Motor Vectorial de Presupuestación",
    version="1.0.0",
    lifespan=lifespan,
)

cors_origins = os.getenv("BRICS_CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in cors_origins if o.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)

app.include_router(budgets_router.router, prefix="/api/v1")
app.include_router(concepts_router.router, prefix="/api/v1")
app.include_router(friction_router.router, prefix="/api/v1")


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "Brics Core API"}
