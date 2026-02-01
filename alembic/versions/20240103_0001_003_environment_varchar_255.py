"""Increase environment column to VARCHAR(255).

Revision ID: 003
Revises: 002
Create Date: 2024-01-03 00:00:00.000000

GitHub environment names can exceed 100 characters when they include
branch names and PR numbers.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Increase environment column from VARCHAR(100) to VARCHAR(255)
    op.alter_column(
        "deployments",
        "environment",
        existing_type=sa.String(100),
        type_=sa.String(255),
        existing_nullable=False,
    )


def downgrade() -> None:
    # Decrease back to VARCHAR(100) - may truncate data
    op.alter_column(
        "deployments",
        "environment",
        existing_type=sa.String(255),
        type_=sa.String(100),
        existing_nullable=False,
    )
