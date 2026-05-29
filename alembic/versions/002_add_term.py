"""add term column to sessions

Revision ID: 002
Revises: 001
Create Date: 2026-05-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '002'
down_revision: Union[str, Sequence[str], None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE sessions ADD COLUMN term TEXT")


def downgrade() -> None:
    op.execute("""
        CREATE TABLE sessions_backup AS
        SELECT id, timestamp, duration, focus, topic, distracted, reason, start_time
        FROM sessions
    """)
    op.execute("DROP TABLE sessions")
    op.execute("ALTER TABLE sessions_backup RENAME TO sessions")
