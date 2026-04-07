"""add_start_time

Revision ID: 001
Revises: 
Create Date: 2026-04-07 10:17:13.253915

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE sessions ADD COLUMN start_time TEXT")
    # Backfill historical rows: approximate start time as end time minus duration.
    op.execute("""
        UPDATE sessions
        SET start_time = datetime(timestamp, '-' || duration || ' minutes')
        WHERE start_time IS NULL
    """)


def downgrade() -> None:
    # SQLite does not support DROP COLUMN directly; recreate the table without it.
    op.execute("""
        CREATE TABLE sessions_backup AS
        SELECT id, timestamp, duration, focus, topic, distracted, reason
        FROM sessions
    """)
    op.execute("DROP TABLE sessions")
    op.execute("ALTER TABLE sessions_backup RENAME TO sessions")
