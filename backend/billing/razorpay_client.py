"""Razorpay client for subscription checkout and webhook verification."""

import hashlib
import hmac
import httpx
import json

from backend.config import settings

RAZORPAY_API_URL = "https://api.razorpay.com/v1"


async def create_subscription(
    user_id: str,
    plan_id: str,
    customer_email: str,
) -> dict:
    """Create a Razorpay subscription and return data for Checkout.js."""
    async with httpx.AsyncClient() as http_client:
        response = await http_client.post(
            f"{RAZORPAY_API_URL}/subscriptions",
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET),
            json={
                "plan_id": plan_id,
                "customer_notify": 1,
                "total_count": 12,
                "notes": {"user_id": user_id, "customer_email": customer_email},
            },
        )
        response.raise_for_status()
        subscription = response.json()
    return {
        "key_id": settings.RAZORPAY_KEY_ID,
        "subscription_id": subscription["id"],
        "name": settings.APP_NAME,
        "email": customer_email,
    }


def construct_webhook_event(payload: bytes, signature: str | None) -> dict:
    """Verify Razorpay's webhook signature and return the decoded payload."""
    if not signature:
        raise ValueError("Missing x-razorpay-signature header")
    expected_signature = hmac.new(
        settings.RAZORPAY_WEBHOOK_SECRET.encode(), payload, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected_signature, signature):
        raise ValueError("Invalid Razorpay webhook signature")
    return json.loads(payload)


PLAN_TIER_MAP = {
    settings.RAZORPAY_PRO_PLAN_ID: "pro",
    settings.RAZORPAY_ENTERPRISE_PLAN_ID: "enterprise",
}


def plan_id_to_tier(plan_id: str | None) -> str:
    return PLAN_TIER_MAP.get(plan_id, "free")
