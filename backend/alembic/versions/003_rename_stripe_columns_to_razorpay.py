"""Rename Stripe subscription columns to Razorpay columns.

Revision ID: 003
Revises: 002
Create Date: 2026-08-21 00:00:00.000000
"""
from alembic import op


revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE user_subscriptions "
        "RENAME COLUMN stripe_customer_id TO razorpay_customer_id;"
    )
    op.execute(
        "ALTER TABLE user_subscriptions "
        "RENAME COLUMN stripe_subscription_id TO razorpay_subscription_id;"
    )
    op.execute(
        "ALTER INDEX ix_user_subscriptions_stripe_customer_id "
        "RENAME TO ix_user_subscriptions_razorpay_customer_id;"
    )


def downgrade() -> None:
    op.execute(
        "ALTER INDEX ix_user_subscriptions_razorpay_customer_id "
        "RENAME TO ix_user_subscriptions_stripe_customer_id;"
    )
    op.execute(
        "ALTER TABLE user_subscriptions "
        "RENAME COLUMN razorpay_subscription_id TO stripe_subscription_id;"
    )
    op.execute(
        "ALTER TABLE user_subscriptions "
        "RENAME COLUMN razorpay_customer_id TO stripe_customer_id;"
    )
