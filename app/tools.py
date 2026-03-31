import asyncio
import random
import logging

logger = logging.getLogger(__name__)


async def cancel_order(order_id: str) -> dict:
    """Simulate async order cancellation with 20% failure rate."""
    logger.info(f"[TOOL] Cancelling order #{order_id}...")
    await asyncio.sleep(1)

    if random.random() < 0.2:
        logger.warning(f"[TOOL] Order #{order_id} cancellation FAILED")
        return {"status": "failed", "order_id": order_id}

    logger.info(f"[TOOL] Order #{order_id} cancelled successfully")
    return {"status": "success", "order_id": order_id}


async def send_email(email: str, message: str) -> dict:
    """Simulate async email sending."""
    logger.info(f"[TOOL] Sending email to {email}...")
    await asyncio.sleep(1)
    logger.info(f"[TOOL] Email sent to {email}")
    return {"status": "sent", "email": email, "message": message}


# Tool registry — extend here to add more tools
TOOL_REGISTRY = {
    "cancel_order": cancel_order,
    "send_email": send_email,
}
