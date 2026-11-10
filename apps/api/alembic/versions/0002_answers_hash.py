"""0002: submissions.answers_hash for idempotent re-export."""

import sqlalchemy as sa
from alembic import op

revision = "0002_answers_hash"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("submissions", sa.Column("answers_hash", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("submissions", "answers_hash")
