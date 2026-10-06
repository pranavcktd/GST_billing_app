"""filing sync off until enabled

Revision ID: cabc31bb4b71
Revises: a7c85b32b322
Create Date: 2026-10-07 00:39:39.362409

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cabc31bb4b71'
down_revision: Union[str, Sequence[str], None] = 'a7c85b32b322'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Fetching GST filing status costs API credit: off until the super admin switches it on (Admin → Integrations)."""
    bind = op.get_bind()
    row = bind.execute(sa.text("SELECT value FROM platform_settings WHERE key = 'gstin_api'")).first()
    if row and row[0]:
        import json

        value = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        value["filing_sync"] = False
        bind.execute(sa.text("UPDATE platform_settings SET value = :v WHERE key = 'gstin_api'"), {"v": json.dumps(value)})


def downgrade() -> None:
    """Downgrade schema."""
    pass
