"""
Configuration for H3H Telegram Uploader Bot.
"""

import os
from pathlib import Path

# Telegram Bot Token (obtain via @BotFather in Telegram)
# Can be passed via environment variable BOT_TOKEN or filled directly below
BOT_TOKEN = os.getenv("BOT_TOKEN", "0000000000:AA_PLACEHOLDER_TOKEN_REPLACE_ME")

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
