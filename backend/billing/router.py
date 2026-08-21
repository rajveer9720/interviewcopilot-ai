"""Billing domain — FastAPI router with Razorpay webhook handler."""

import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from backend.core.database import get_db
from backend.auth.dependencies import get_current_user
from backend.auth.models import User
from backend.billing.models import UserSubscription
from backend.billing.razorpay_client import (
    create_subscription, construct_webhook_event, plan_id_to_tier,
)
from backend.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/plans")
async def get_plans():
    return [
        {
            "id": "free",
            "name": "Free",
            "price_usd": 0,
            "sessions_per_month": 5,
            "max_duration_mins": 20,
            "llm_providers": ["gemini"],
            "features": ["Basic AI coaching", "1 resume profile", "7-day analytics"],
        },
        {
            "id": "pro",
            "name": "Pro",
            "price_usd": 19,
            "razorpay_plan_id": settings.RAZORPAY_PRO_PLAN_ID,
            "sessions_per_month": None,
            "max_duration_mins": 90,
            "llm_providers": ["openai", "gemini"],
            "features": [
                "Unlimited sessions", "GPT-4o coaching", "5 resume profiles",
                "90-day analytics", "Detailed reports", "Email support",
            ],
        },
        {
            "id": "enterprise",
            "name": "Enterprise",
            "price_usd": 49,
            "razorpay_plan_id": settings.RAZORPAY_ENTERPRISE_PLAN_ID,
            "sessions_per_month": None,
            "max_duration_mins": 180,
            "llm_providers": ["openai", "gemini"],
            "features": [
                "Everything in Pro", "20 resume profiles", "1-year analytics",
                "PDF report export", "Priority support", "Team seats add-on",
            ],
        },
    ]

@router.post("/checkout")
async def create_checkout(
    plan_id: str,
    current_user: User = Depends(get_current_user),
):
    checkout = await create_subscription(
        user_id=str(current_user.id),
        plan_id=plan_id,
        customer_email=current_user.email,
    )
    return checkout


@router.post("/webhook")
async def razorpay_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    payload = await request.body()
    sig_header = request.headers.get("x-razorpay-signature")

    try:
        event = construct_webhook_event(payload, sig_header)
    except Exception as e:
        raise HTTPException(400, f"Webhook signature verification failed: {e}")

    event_type = event["event"]
    data = event.get("payload", {}).get("subscription", {}).get("entity", {})

    if event_type in ("subscription.authenticated", "subscription.activated"):
        await _handle_subscription_created(db, data)
    elif event_type in (
        "subscription.charged", "subscription.updated", "subscription.paused",
        "subscription.resumed", "subscription.pending", "subscription.halted",
    ):
        await _handle_subscription_updated(db, data)
    elif event_type in ("subscription.cancelled", "subscription.completed"):
        await _handle_subscription_deleted(db, data)

    return {"received": True}


def _to_datetime(unix_ts: int | None) -> datetime | None:
    return datetime.fromtimestamp(unix_ts, tz=timezone.utc) if unix_ts else None


async def _upsert_subscription(db: AsyncSession, sub: dict, tier: str) -> None:
    """Create or update the UserSubscription row from a Razorpay subscription."""
    user_id = sub.get("notes", {}).get("user_id")
    if not user_id:
        logger.warning("Razorpay subscription event missing user_id note: %s", sub.get("id"))
        return

    result = await db.execute(
        select(UserSubscription).where(UserSubscription.user_id == user_id)
    )
    subscription = result.scalar_one_or_none()
    if not subscription:
        subscription = UserSubscription(user_id=user_id)
        db.add(subscription)

    subscription.razorpay_customer_id = sub.get("customer_id")
    subscription.razorpay_subscription_id = sub.get("id")
    subscription.status = sub.get("status")
    subscription.current_period_start = _to_datetime(sub.get("current_start"))
    subscription.current_period_end = _to_datetime(sub.get("current_end"))

    await db.execute(
        update(User).where(User.id == user_id).values(plan_tier=tier)
    )


async def _handle_subscription_created(db: AsyncSession, sub: dict):
    tier = plan_id_to_tier(sub.get("plan_id"))
    await _upsert_subscription(db, sub, tier)


async def _handle_subscription_updated(db: AsyncSession, sub: dict):
    tier = plan_id_to_tier(sub.get("plan_id")) if sub.get("status") in ("active", "authenticated") else "free"
    await _upsert_subscription(db, sub, tier)


async def _handle_subscription_deleted(db: AsyncSession, sub: dict):
    await _upsert_subscription(db, sub, tier="free")
