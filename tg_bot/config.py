"""
Configuration for H3H Telegram Uploader Bot.
"""

import os
import socket
from pathlib import Path

# Telegram Bot Token (obtained via @BotFather in Telegram)
BOT_TOKEN = os.getenv("BOT_TOKEN", "8930658933:AAEBml3fA4huJmEeSDPKxJJBpPJ_O77-HEI")

# Dynamic credentials loader from local secure files
_PROJECT_ROOT = Path(__file__).parent.parent.resolve()

def _get_local_credential(key: str, default: str = "") -> str:
    val = os.getenv(key, "")
    if val:
        return val
    # Fallback 1: permanent_gdrive_credentials.txt
    cred_file = _PROJECT_ROOT / "permanent_gdrive_credentials.txt"
    if cred_file.exists():
        for line in cred_file.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip()
    # Fallback 2: user home .h3h_google_drive.json
    home_cfg = Path.home() / ".h3h_google_drive.json"
    if home_cfg.exists():
        try:
            import json
            data = json.loads(home_cfg.read_text(encoding="utf-8"))
            k_map = {
                "GDRIVE_REFRESH_TOKEN": "refresh_token",
                "GDRIVE_CLIENT_ID": "client_id",
                "GDRIVE_CLIENT_SECRET": "client_secret",
            }
            if key in k_map and k_map[key] in data:
                return data[k_map[key]]
        except Exception:
            pass
    # Fallback 3: GitHub stored credentials
    if key == "GITHUB_TOKEN":
        try:
            from h3h_studio.core.github_publisher import GitHubPublisher
            tok, _ = GitHubPublisher.get_stored_credentials()
            if tok:
                return tok
        except Exception:
            pass
    return default

# GitHub Personal Access Token (for auto-pushing updated catalogs)
GITHUB_TOKEN = _get_local_credential("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "Holy3holy-dev/H3H-Backgrounds")
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")
GITHUB_BRANCH_AFTER_DARK = os.getenv("GITHUB_BRANCH_AFTER_DARK", "after-dark")

# Google Drive storage settings
GDRIVE_FOLDER_ID = os.getenv("GDRIVE_FOLDER_ID", "1hI1klJ6t2ymVoBwGA6IzY79QMjp5dTJC")
GDRIVE_AFTER_DARK_FOLDER_ID = os.getenv("GDRIVE_AFTER_DARK_FOLDER_ID", "1SXWjp12pKxPPT6YRMZ7tle8cgZdrKkHk")
GDRIVE_REFRESH_TOKEN = _get_local_credential("GDRIVE_REFRESH_TOKEN", "")
GDRIVE_CLIENT_ID = _get_local_credential("GDRIVE_CLIENT_ID", "")
GDRIVE_CLIENT_SECRET = _get_local_credential("GDRIVE_CLIENT_SECRET", "")

# Admin Telegram user IDs (who can moderate / approve uploads, or empty list for public auto-upload)
ADMIN_IDS = [
    # 123456789,
]

# Target catalog paths relative to repository root
CATALOG_PATH_STANDARD = Path("catalog/data/catalog.json")
CATALOG_PATH_AFTER_DARK = Path("catalog/data/catalog_after_dark.json")

# Temporary working directory for video conversion
TEMP_DIR = Path("tmp/tg_bot_processing")
TEMP_DIR.mkdir(parents=True, exist_ok=True)

def detect_local_proxy() -> str | None:
    """Auto-detects active local proxy (v2rayN/sing-box/clash) if running on Windows and sets environment."""
    for port in [10809, 7890, 10808, 8080]:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.4)
            if s.connect_ex(('127.0.0.1', port)) == 0:
                s.close()
                proxy_url = f"http://127.0.0.1:{port}"
                os.environ["HTTP_PROXY"] = proxy_url
                os.environ["HTTPS_PROXY"] = proxy_url
                os.environ["http_proxy"] = proxy_url
                os.environ["https_proxy"] = proxy_url
                return proxy_url
            s.close()
        except Exception:
            pass
    return None
