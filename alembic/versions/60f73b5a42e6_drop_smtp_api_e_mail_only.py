"""drop smtp, api e-mail only

Revision ID: 60f73b5a42e6
Revises: 441c704031fc
Create Date: 2026-10-10 17:07:19.473946

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '60f73b5a42e6'
down_revision: Union[str, Sequence[str], None] = '441c704031fc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """E-mail goes only through API senders: drop the SMTP settings (and their saved passwords) and SMTP-only columns."""
    op.execute("DELETE FROM mail_senders WHERE provider = 'SMTP'")
    op.drop_table('smtp_configs')
    for col in ('host', 'port', 'security', 'username'):
        op.drop_column('mail_senders', col)


def downgrade() -> None:
    """Downgrade schema (saved SMTP settings are not restored)."""
    op.add_column('mail_senders', sa.Column('username', sa.String(length=200), nullable=True))
    op.add_column('mail_senders', sa.Column('security', sa.String(length=10), nullable=True))
    op.add_column('mail_senders', sa.Column('port', sa.Integer(), nullable=True))
    op.add_column('mail_senders', sa.Column('host', sa.String(length=200), nullable=True))
    op.create_table('smtp_configs',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('scope', sa.String(length=10), nullable=False),
    sa.Column('owner_id', sa.String(length=32), nullable=False),
    sa.Column('host', sa.String(length=200), nullable=False),
    sa.Column('port', sa.Integer(), nullable=False),
    sa.Column('security', sa.String(length=10), nullable=False),
    sa.Column('username', sa.String(length=200), nullable=True),
    sa.Column('password_enc', sa.Text(), nullable=True),
    sa.Column('from_email', sa.String(length=200), nullable=False),
    sa.Column('from_name', sa.String(length=120), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('scope', 'owner_id', name='uq_smtp_scope_owner')
    )
