"""Rename s3_key -> storage_key

Revision ID: 002
Revises: 001
Create Date: 2026-08-20 00:00:00.000000

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Use raw SQL to be explicit and portable for Postgres
    op.execute("ALTER TABLE resumes RENAME COLUMN s3_key TO storage_key;")


def downgrade() -> None:
    op.execute("ALTER TABLE resumes RENAME COLUMN storage_key TO s3_key;")
