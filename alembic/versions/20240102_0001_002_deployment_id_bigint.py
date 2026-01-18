"""Change github_deployment_id to BIGINT.

Revision ID: 002
Revises: 001
Create Date: 2024-01-02 00:00:00.000000

GitHub deployment IDs can exceed 32-bit integer range.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Change github_deployment_id from INTEGER to BIGINT
    op.alter_column(
        "deployments",
        "github_deployment_id",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=False,
    )


def downgrade() -> None:
    # Change back to INTEGER (may fail if data exceeds int32 range)
    op.alter_column(
        "deployments",
        "github_deployment_id",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=False,
    )
