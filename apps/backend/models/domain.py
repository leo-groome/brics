from datetime import datetime
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from .database import Base


EMBEDDING_DIM = 1024


class MasterConcept(Base):
    """Catálogo Maestro — fuente de verdad del lenguaje técnico (sin precios)."""

    __tablename__ = "master_concepts"

    id = Column(BigInteger, primary_key=True, index=True)
    family = Column(String, nullable=False, index=True)
    technical_concept = Column(Text, nullable=False)
    unit = Column(String, nullable=False)
    embedding = Column(Vector(EMBEDDING_DIM), nullable=False)
    source_files = Column(ARRAY(String), nullable=False, default=list)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        UniqueConstraint("technical_concept", "unit", name="master_concepts_concept_unit_uq"),
    )

    prices = relationship("ConceptPrice", back_populates="concept", cascade="all, delete-orphan")


Index(
    "master_concepts_embedding_hnsw",
    MasterConcept.embedding,
    postgresql_using="hnsw",
    postgresql_ops={"embedding": "vector_cosine_ops"},
)

# Fuzzy fallback / búsqueda textual rápida sobre la descripción canónica.
Index(
    "master_concepts_concept_trgm",
    MasterConcept.technical_concept,
    postgresql_using="gin",
    postgresql_ops={"technical_concept": "gin_trgm_ops"},
)


class Budget(Base):
    __tablename__ = "budgets"

    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(String, nullable=True, index=True)
    project_name = Column(String, nullable=True)
    project_type = Column(String, nullable=True)
    region = Column(String, nullable=True)
    status = Column(String, nullable=False, default="draft")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    lines = relationship("BudgetLine", back_populates="budget", cascade="all, delete-orphan")


class BudgetLine(Base):
    __tablename__ = "budget_lines"

    id = Column(BigInteger, primary_key=True, index=True)
    budget_id = Column(BigInteger, ForeignKey("budgets.id", ondelete="CASCADE"), nullable=False, index=True)
    raw_input = Column(Text, nullable=False)
    matched_concept_id = Column(BigInteger, ForeignKey("master_concepts.id"), nullable=True)
    match_confidence = Column(Float, nullable=True)
    match_status = Column(String, nullable=False, default="pending")
    quantity = Column(Float, nullable=True)
    unit = Column(String, nullable=True)
    unit_price = Column(Float, nullable=True)
    price_source = Column(String, nullable=True)
    # Top-K candidatos serializados en el momento del match — evita re-embedding
    # cuando el frontend pide /friction/pending.
    top_candidates = Column(JSONB, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    budget = relationship("Budget", back_populates="lines")
    matched_concept = relationship("MasterConcept")


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String, nullable=False)
    whatsapp_number = Column(String, nullable=False, unique=True)
    families = Column(ARRAY(String), nullable=False, default=list)
    active = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class QuoteRequest(Base):
    __tablename__ = "quote_requests"

    id = Column(BigInteger, primary_key=True, index=True)
    budget_line_id = Column(BigInteger, ForeignKey("budget_lines.id", ondelete="CASCADE"), nullable=False, index=True)
    supplier_id = Column(BigInteger, ForeignKey("suppliers.id"), nullable=False, index=True)
    sent_at = Column(DateTime, nullable=True)
    response_text = Column(Text, nullable=True)
    response_price = Column(Float, nullable=True)
    status = Column(String, nullable=False, default="queued")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class ConceptPrice(Base):
    """Historial de precios observados para un MasterConcept (una por fila de presupuesto/Excel)."""

    __tablename__ = "concept_prices"

    id = Column(BigInteger, primary_key=True, index=True)
    concept_id = Column(
        BigInteger, ForeignKey("master_concepts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    unit_price = Column(Float, nullable=False)
    unit = Column(String, nullable=True)
    source_file = Column(String, nullable=True)
    project_name = Column(String, nullable=True)
    region = Column(String, nullable=True)
    observed_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    concept = relationship("MasterConcept", back_populates="prices")


Index(
    "concept_prices_concept_observed_idx",
    ConceptPrice.concept_id,
    ConceptPrice.observed_at.desc(),
)
