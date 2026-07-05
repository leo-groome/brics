"""orgs (tenants) + org_id en budgets y concept_prices.

Defensiva contra el drift real de la DB (creada con create_all() parcial):
cada paso verifica existencia antes de actuar. En DBs frescas, create_all()
en el lifespan crea todo el schema del modelo (ya incluye org_id) y esta
revisión solo agrega lo que falte.

Revision ID: 0001
Revises:
Create Date: 2026-07-05
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _inspector():
    return sa.inspect(op.get_bind())


def _has_column(insp, table: str, column: str) -> bool:
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    insp = _inspector()
    tables = set(insp.get_table_names())

    if "orgs" not in tables:
        op.create_table(
            "orgs",
            sa.Column("id", sa.BigInteger(), primary_key=True),
            sa.Column("name", sa.String(), nullable=False, unique=True),
            sa.Column("api_key", sa.String(), nullable=False, unique=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_orgs_api_key", "orgs", ["api_key"])

    # budgets.org_id: NOT NULL. budgets está vacía en este punto (verificado);
    # si hubiera filas, backfillear antes.
    if "budgets" in tables and not _has_column(insp, "budgets", "org_id"):
        op.add_column("budgets", sa.Column("org_id", sa.BigInteger(), nullable=False))
        op.create_foreign_key("budgets_org_id_fkey", "budgets", "orgs", ["org_id"], ["id"])
        op.create_index("ix_budgets_org_id", "budgets", ["org_id"])

    # concept_prices puede no existir aún (la crea create_all() con org_id incluido).
    if "concept_prices" in tables and not _has_column(insp, "concept_prices", "org_id"):
        op.add_column("concept_prices", sa.Column("org_id", sa.BigInteger(), nullable=True))
        op.create_foreign_key(
            "concept_prices_org_id_fkey", "concept_prices", "orgs", ["org_id"], ["id"]
        )
        op.create_index("ix_concept_prices_org_id", "concept_prices", ["org_id"])


def downgrade() -> None:
    insp = _inspector()
    tables = set(insp.get_table_names())
    if "concept_prices" in tables and _has_column(insp, "concept_prices", "org_id"):
        op.drop_index("ix_concept_prices_org_id", "concept_prices")
        op.drop_constraint("concept_prices_org_id_fkey", "concept_prices")
        op.drop_column("concept_prices", "org_id")
    if "budgets" in tables and _has_column(insp, "budgets", "org_id"):
        op.drop_index("ix_budgets_org_id", "budgets")
        op.drop_constraint("budgets_org_id_fkey", "budgets")
        op.drop_column("budgets", "org_id")
    if "orgs" in tables:
        op.drop_index("ix_orgs_api_key", "orgs")
        op.drop_table("orgs")
