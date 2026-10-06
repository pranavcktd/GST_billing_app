"""service items unit NA

Revision ID: 271cec1a913b
Revises: b420b82613c6
Create Date: 2026-10-06 21:23:07.801924

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '271cec1a913b'
down_revision: Union[str, Sequence[str], None] = 'b420b82613c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Services carry no quantity unit (GST portal: UQC "NA" for SAC codes)."""
    op.execute("UPDATE items SET unit = 'NA' WHERE type = 'SERVICE'")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("UPDATE items SET unit = 'OTH' WHERE type = 'SERVICE' AND unit = 'NA'")
