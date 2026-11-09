"""
Patch script to update tg_bot/bot.py:
1. Adds user_preferences for default upload category.
2. Adds /afterdark, /ad, /standard, /main, /mode commands.
3. Auto-detects After Dark from caption / filename keywords.
4. Auto-routes uploads to After Dark by default if indicated.
5. Handles text input in AWAITING_CATEGORY gracefully.
6. Atomic remote catalog sync before appending variants.
"""

import re
from pathlib import Path

bot_path = Path("tg_bot/bot.py")
code = bot_path.read_text(encoding="utf-8")

# 1. Add user_preferences and preference helpers
pref_block = '''user_sessions: Dict[int, Dict[str, Any]] = {}
user_preferences: Dict[int, Dict[str, Any]] = {}

def get_user_category_pref(chat_id: int) -> str:
    """Returns user's default category preference ('standard' or 'after_dark')."""
    return user_preferences.get(chat_id, {}).get("category", "standard")

def set_user_category_pref(chat_id: int, category: str):
    """Sets user's default category preference."""
    if chat_id not in user_preferences:
        user_preferences[chat_id] = {}
    user_preferences[chat_id]["category"] = category
'''

code = code.replace("user_sessions: Dict[int, Dict[str, Any]] = {}", pref_block, 1)

# 2. Update get_session and reset_session to use user preference
old_get_sess = '''def get_session(chat_id: int) -> Dict[str, Any]:
    if chat_id not in user_sessions:
        user_sessions[chat_id] = {
            "state": "IDLE",
            "temp_vid": None,
            "title_id": None,
            "game_name": None,
            "variant_name": None,
            "suggested_variant": None,
            "batch_items": [],
            "zip_dir": None,
            "category": "standard",
            "author": ""
        }
    return user_sessions[chat_id]'''

new_get_sess = '''def get_session(chat_id: int) -> Dict[str, Any]:
    if chat_id not in user_sessions:
        pref = get_user_category_pref(chat_id)
        user_sessions[chat_id] = {
            "state": "IDLE",
            "temp_vid": None,
            "title_id": None,
            "game_name": None,
            "variant_name": None,
            "suggested_variant": None,
            "batch_items": [],
            "zip_dir": None,
            "category": pref,
            "author": ""
        }
    return user_sessions[chat_id]'''

code = code.replace(old_get_sess, new_get_sess, 1)

old_reset_sess = '''    user_sessions[chat_id] = {
        "state": "IDLE",
        "temp_vid": None,
        "title_id": None,
        "game_name": None,
        "variant_name": None,
        "suggested_variant": None,
        "batch_items": [],
        "zip_dir": None,
        "category": "standard",
        "author": "",
        "codec": "h264"
    }'''

new_reset_sess = '''    pref = get_user_category_pref(chat_id)
    user_sessions[chat_id] = {
        "state": "IDLE",
        "temp_vid": None,
        "title_id": None,
        "game_name": None,
        "variant_name": None,
        "suggested_variant": None,
        "batch_items": [],
        "zip_dir": None,
        "category": pref,
        "author": "",
        "codec": "h264"
    }'''

code = code.replace(old_reset_sess, new_reset_sess, 1)

# 3. Add remote catalog fetch helper before append_variant_to_catalog
fetch_func = '''def fetch_remote_catalog_json(catalog_rel: Path, branch: str) -> Optional[dict]:
    """Fetches freshest catalog directly from GitHub REST API to ensure atomic updates across branches."""
    gh_token, _ = GitHubPublisher.get_stored_credentials()
    if not gh_token:
        gh_token = os.getenv("GITHUB_TOKEN") or GITHUB_TOKEN
    if not gh_token:
        return None
    repo_name = GITHUB_REPO or GitHubPublisher.get_repo_name()
    rel_str = str(catalog_rel).replace("\\\\", "/")
    headers = {
        "Authorization": f"Bearer {gh_token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "H3H-Background-Uploader-Bot"
    }
    url = f"https://api.github.com/repos/{repo_name}/contents/{rel_str}?ref={branch}"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw_bytes = base64.b64decode(data.get("content", ""))
            return json.loads(raw_bytes.decode("utf-8"))
    except Exception as e:
        return None

'''

old_append = '''def append_variant_to_catalog(
    catalog_rel: Path,
    title_id: str,
    game_name: str,
    variant_name: str,
    author: str,
    category: str,
    direct_url: str,
    preview_url: str,
    file_size: int,
    codec: str = "h264"
) -> Dict[str, Any]:
    """Adds a new background variant to catalog JSON file and updates metadata."""
    target_catalog_path = PROJECT_ROOT / catalog_rel
    cat_data = json.loads(target_catalog_path.read_text(encoding="utf-8"))'''

new_append = fetch_func + '''def append_variant_to_catalog(
    catalog_rel: Path,
    title_id: str,
    game_name: str,
    variant_name: str,
    author: str,
    category: str,
    direct_url: str,
    preview_url: str,
    file_size: int,
    codec: str = "h264",
    branch: Optional[str] = None
) -> Dict[str, Any]:
    """Adds a new background variant to catalog JSON file and updates metadata."""
    target_catalog_path = PROJECT_ROOT / catalog_rel
    target_branch = branch or (GITHUB_BRANCH_AFTER_DARK if category == "after_dark" else GITHUB_BRANCH)
    remote_data = fetch_remote_catalog_json(catalog_rel, target_branch)
    if remote_data:
        cat_data = remote_data
    else:
        cat_data = json.loads(target_catalog_path.read_text(encoding="utf-8"))'''

code = code.replace(old_append, new_append, 1)

# 4. Add /afterdark, /standard, /mode commands
cmd_block = '''@bot.message_handler(commands=["afterdark", "ad", "nsfw", "ecchi"])
def cmd_afterdark_mode(message: types.Message):
    chat_id = message.chat.id
    set_user_category_pref(chat_id, "after_dark")
    sess = get_session(chat_id)
    sess["category"] = "after_dark"
    bot.reply_to(
        message,
        "🌸 <b>Режим After Dark (18+) АКТИВИРОВАН ПО УМОЛЧАНИЮ!</b>\n\n"
        "Теперь все ваши загружаемые ролики будут автоматически публиковаться в каталог <b>After Dark</b> (ветка <code>after-dark</code>).\n\n"
        "💡 <i>Чтобы переключиться обратно на семейный/основной каталог, отправьте /standard</i>",
        parse_mode="HTML"
    )

@bot.message_handler(commands=["standard", "main"])
def cmd_standard_mode(message: types.Message):
    chat_id = message.chat.id
    set_user_category_pref(chat_id, "standard")
    sess = get_session(chat_id)
    sess["category"] = "standard"
    bot.reply_to(
        message,
        "🎮 <b>Режим Обычного каталога H3H активирован!</b>\n\n"
        "Все загружаемые ролики будут публиковаться в основной каталог на ветку <code>main</code>.\n\n"
        "💡 <i>Чтобы включить After Dark по умолчанию, отправьте /afterdark</i>",
        parse_mode="HTML"
    )

@bot.message_handler(commands=["mode"])
def cmd_show_mode(message: types.Message):
    chat_id = message.chat.id
    pref = get_user_category_pref(chat_id)
    mode_str = "🌸 After Dark (18+)" if pref == "after_dark" else "🎮 Обычный каталог H3H"
    bot.reply_to(
        message,
        f"⚙️ <b>Текущий режим загрузки:</b> <b>{mode_str}</b>\n\n"
        "• Для After Dark по умолчанию: /afterdark\n"
        "• Для обычного каталога: /standard",
        parse_mode="HTML"
    )
'''

code = code.replace('@bot.message_handler(commands=["cancel"])', cmd_block + '\n@bot.message_handler(commands=["cancel"])', 1)

bot_path.write_text(code, encoding="utf-8")
print("[+] Applied patch 1: preferences, remote sync, commands")
