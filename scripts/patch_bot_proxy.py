from pathlib import Path

p = Path("tg_bot/bot.py")
text = p.read_text(encoding="utf-8")
is_crlf = "\r\n" in text
if is_crlf:
    text = text.replace("\r\n", "\n")

old = """from tg_bot.config import (
    BOT_TOKEN,
    ADMIN_IDS,
    CATALOG_PATH_STANDARD,
    CATALOG_PATH_AFTER_DARK,
    TEMP_DIR
)
from scripts.title_id_resolver import TitleIdResolver
from h3h_studio.core.google_drive import GoogleDriveHelper, GoogleDriveClient
from h3h_studio.core.github_publisher import GitHubPublisher

if BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE" or not BOT_TOKEN:
    print("[!] Warning: BOT_TOKEN is not configured in tg_bot/config.py or environment variable.")
    print("    Please get a bot token from @BotFather in Telegram and update tg_bot/config.py.")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")"""

new = """from tg_bot.config import (
    BOT_TOKEN,
    ADMIN_IDS,
    CATALOG_PATH_STANDARD,
    CATALOG_PATH_AFTER_DARK,
    TEMP_DIR,
    detect_local_proxy
)
from scripts.title_id_resolver import TitleIdResolver
from h3h_studio.core.google_drive import GoogleDriveHelper, GoogleDriveClient
from h3h_studio.core.github_publisher import GitHubPublisher

# Auto-detect local proxy for stable Telegram connectivity
local_proxy = detect_local_proxy()
if local_proxy:
    print(f"[*] Detected local proxy on {local_proxy}, configuring telebot...")
    from telebot import apihelper
    apihelper.proxy = {'http': local_proxy, 'https': local_proxy}

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")"""

if old in text:
    text = text.replace(old, new)
    if is_crlf:
        text = text.replace("\n", "\r\n")
    p.write_text(text, encoding="utf-8")
    print("[+] Successfully patched bot.py with proxy auto-detection!")
else:
    print("[-] Old text not found in bot.py")
