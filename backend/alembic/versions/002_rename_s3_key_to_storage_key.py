"""Rename s3_key -> storage_key

Revision ID: 002
Revises: 001
Create Date: 2026-08-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fresh databases may already use the current name in revision 001.
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("resumes")}
    if "s3_key" in columns:
        op.alter_column("resumes", "s3_key", new_column_name="storage_key")


def downgrade() -> None:
    op.execute("ALTER TABLE resumes RENAME COLUMN storage_key TO s3_key;")
