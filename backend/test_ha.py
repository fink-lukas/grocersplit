import asyncio
import os
from app.notifications_ha import send_ha_notification

async def main():
    print("Testing send_ha_notification with url...")
    url = f"http://192.168.0.69:5173/receipt/38"
    print(f"URL being sent: {url}")
    await send_ha_notification(
        target_user="martin",
        event_type="new_receipt",
        message="You owe $12.50 for groceries.",
        data={"url": url}
    )
    print("Done")

if __name__ == "__main__":
    asyncio.run(main())
