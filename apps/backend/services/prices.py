"""Price helpers — pure DB, no LLM.

Convention: functions do NOT commit; caller is responsible for session.commit()
(mirrors ingester.py which flushes/commits externally).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from models.domain import ConceptPrice


def record_price(
    session: Session,
    *,
    concept_id: int,
    unit_price: float,
    unit: Optional[str] = None,
    source_file: Optional[str] = None,
    project_name: Optional[str] = None,
    region: Optional[str] = None,
    observed_at: Optional[datetime] = None,
) -> ConceptPrice:
    """Insert a ConceptPrice row and return it (does not commit).

    Raises ValueError for non-positive or None unit_price.
    """
    if unit_price is None or unit_price <= 0:
        raise ValueError(f"unit_price must be a positive number, got {unit_price!r}")

    row = ConceptPrice(
        concept_id=concept_id,
        unit_price=unit_price,
        unit=unit,
        source_file=source_file,
        project_name=project_name,
        region=region,
        observed_at=observed_at or datetime.utcnow(),
    )
    session.add(row)
    return row


def get_last_price(session: Session, concept_id: int) -> Optional[ConceptPrice]:
    """Return the most recent ConceptPrice for this concept (tie-break by created_at desc)."""
    return (
        session.query(ConceptPrice)
        .filter(ConceptPrice.concept_id == concept_id)
        .order_by(ConceptPrice.observed_at.desc(), ConceptPrice.created_at.desc())
        .first()
    )


def get_price_history(
    session: Session, concept_id: int, limit: int = 50
) -> list[ConceptPrice]:
    """Return up to *limit* ConceptPrice rows, newest first."""
    return (
        session.query(ConceptPrice)
        .filter(ConceptPrice.concept_id == concept_id)
        .order_by(ConceptPrice.observed_at.desc(), ConceptPrice.created_at.desc())
        .limit(limit)
        .all()
    )


def get_price_stats(session: Session, concept_id: int) -> dict:
    """Return aggregate stats computed in SQL.

    Returns:
        {
            count: int,
            last_price: float | None,
            last_observed_at: datetime | None,
            min: float | None,
            max: float | None,
            avg: float | None,
            median: float | None,
        }
    Median is computed via percentile_cont (Postgres native).
    All numeric fields are None when count == 0.
    """
    row = session.execute(
        text(
            """
            SELECT
                count(*)                                                      AS cnt,
                min(unit_price)                                               AS min_price,
                max(unit_price)                                               AS max_price,
                avg(unit_price)                                               AS avg_price,
                percentile_cont(0.5) WITHIN GROUP (ORDER BY unit_price)      AS median_price,
                max(observed_at)                                              AS last_observed_at
            FROM concept_prices
            WHERE concept_id = :cid
            """
        ),
        {"cid": concept_id},
    ).one()

    if row.cnt == 0:
        return {
            "count": 0,
            "last_price": None,
            "last_observed_at": None,
            "min": None,
            "max": None,
            "avg": None,
            "median": None,
        }

    last = get_last_price(session, concept_id)
    return {
        "count": int(row.cnt),
        "last_price": last.unit_price if last else None,
        "last_observed_at": row.last_observed_at,
        "min": float(row.min_price),
        "max": float(row.max_price),
        "avg": float(row.avg_price),
        "median": float(row.median_price),
    }
