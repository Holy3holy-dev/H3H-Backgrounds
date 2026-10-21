"""
Configuration for H3H Telegram Uploader Bot.
"""

import os
import socket
from pathlib import Path

# Telegram Bot Token (obtained via @BotFather in Telegram)
BOT_TOKEN = os.getenv("BOT_TOKEN", "8930658933:AAEBml3fA4huJmEeSDPKxJJBpPJ_O77-HEI")

# Admin Telegram user IDs (who can moderate / approve uploads, or empty list for public auto-upload)
ADMIN_IDS = [
    # 123456789,
]

# GitHub repository settings
GITHUB_REPO = "Holy3holy-dev/H3H-Backgrounds"
GITHUB_BRANCH = "main"

# Target catalog paths relative to repository root
CATALOG_PATH_STANDARD = Path("catalog/data/catalog.json")
CATALOG_PATH_AFTER_DARK = Path("catalog/data/catalog_after_dark.json")

# Temporary working directory for video conversion
TEMP_DIR = Path("tmp/tg_bot_processing")
TEMP_DIR.mkdir(parents=True, exist_ok=True)

def detect_local_proxy() -> str | None:
    """Auto-detects active local proxy (v2rayN/sing-box/clash) if running on Windows."""
    for port in [10809, 7890, 10808, 8080]:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.4)
            if s.connect_ex(('127.0.0.1', port)) == 0:
                s.close()
                return f"http://127.0.0.1:{port}"
            s.close()
        except Exception:
            pass
    return None
