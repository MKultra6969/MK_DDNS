import os

from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "300"))

if not TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN is not configured")

if not ADMIN_ID:
    raise RuntimeError("ADMIN_ID is not configured")
