import httpx
import logging
from typing import Optional, Dict, Any
from app.core.config import settings

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
    """
    ha_base_url = settings.HA_BASE_URL
    ha_webhook_id = settings.HA_WEBHOOK_ID

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
