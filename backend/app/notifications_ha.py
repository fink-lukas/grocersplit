
import os
import httpx
import logging
import asyncio
from typing import Optional, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def send_ha_notification(
    target_user: str,
    event_type: str,
    message: str,
    data: Optional[Dict[str, Any]] = None
):
    """
    Sends a notification payload to the Home Assistant webhook.
    
    :param target_user: The username of the recipient (to be used by HA automation).
    :param event_type: The type of event (e.g., 'new_receipt', 'item_assigned').
    :param message: A human-readable message.
    :param data: Additional data payload.
    """
    ha_base_url = os.getenv("HA_BASE_URL")
    ha_webhook_id = os.getenv("HA_WEBHOOK_ID")

    if not ha_base_url or not ha_webhook_id:
        logger.warning("Home Assistant configuration missing (HA_BASE_URL or HA_WEBHOOK_ID). Notification skipped.")
        return

    # Normalize URL
    if ha_base_url.endswith("/"):
        ha_base_url = ha_base_url[:-1]
        
    url = f"{ha_base_url}/api/webhook/{ha_webhook_id}"
    
    payload = {
        "target_user": target_user,
        "type": event_type,
        "message": message,
        "data": data or {}
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=5.0)
            if response.status_code == 200:
                logger.info(f"Successfully sent HA notification to {target_user}")
            else:
                logger.error(f"Failed to send HA notification. Status for {target_user}: {response.status_code}, Body: {response.text}")
    except Exception as e:
        logger.error(f"Error sending HA notification: {e}")
