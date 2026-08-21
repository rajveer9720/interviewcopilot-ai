"""Billing domain — SQLAlchemy models."""

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base


class UserSubscription(Base):
    """
    Tracks the Razorpay subscription state for a user.
    One row per user — updated in place as Razorpay webhook events arrive.
    """

    __tablename__ = "user_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        unique=True, nullable=False, index=True,
    )
    razorpay_customer_id: Mapped[str | None] = mapped_column(String(255), index=True)
    razorpay_subscription_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    status: Mapped[str | None] = mapped_column(String(50))  # active | trialing | past_due | canceled
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="subscription")  # noqa

    def __repr__(self):
        return f"<UserSubscription user={self.user_id} status={self.status}>"
