from pathlib import Path

p = Path("tg_bot/bot.py")
text = p.read_text(encoding="utf-8")
is_crlf = "\r\n" in text
if is_crlf:
    text = text.replace("\r\n", "\n")

# 1. Update config import
old_import = """from tg_bot.config import (
    BOT_TOKEN,
    ADMIN_IDS,
    CATALOG_PATH_STANDARD,
    CATALOG_PATH_AFTER_DARK,
    TEMP_DIR,
    detect_local_proxy
)"""

new_import = """from tg_bot.config import (
    BOT_TOKEN,
    GITHUB_TOKEN,
    GITHUB_REPO,
    GITHUB_BRANCH,
    GDRIVE_FOLDER_ID,
    GDRIVE_REFRESH_TOKEN,
    ADMIN_IDS,
    CATALOG_PATH_STANDARD,
    CATALOG_PATH_AFTER_DARK,
    TEMP_DIR,
    detect_local_proxy
)"""

if old_import in text:
    text = text.replace(old_import, new_import)

# 2. Update gdrive token resolution
old_gdrive = """    gdrive_cfg = GoogleDriveHelper.get_stored_config()
    refresh_tok = gdrive_cfg.get("refresh_token")
    access_tok = GoogleDriveHelper.refresh_access_token(refresh_tok) or gdrive_cfg.get("token")
    folder_id = gdrive_cfg.get("project_folder_id") or gdrive_cfg.get("folder_id")"""

new_gdrive = """    gdrive_cfg = GoogleDriveHelper.get_stored_config()
    refresh_tok = os.getenv("GDRIVE_REFRESH_TOKEN") or GDRIVE_REFRESH_TOKEN or gdrive_cfg.get("refresh_token")
    access_tok = GoogleDriveHelper.refresh_access_token(refresh_tok) or gdrive_cfg.get("token")
    folder_id = os.getenv("GDRIVE_FOLDER_ID") or GDRIVE_FOLDER_ID or gdrive_cfg.get("project_folder_id") or gdrive_cfg.get("folder_id")"""

if old_gdrive in text:
    text = text.replace(old_gdrive, new_gdrive)

# 3. Update github token resolution
old_github = """        gh_token, _ = GitHubPublisher.get_stored_credentials()
        if gh_token:
            repo_url = f"https://x-access-token:{gh_token}@github.com/{GitHubPublisher.get_repo_name()}.git" """

old_github_target = """        gh_token, _ = GitHubPublisher.get_stored_credentials()
        if gh_token:
            repo_url = f"https://x-access-token:{gh_token}@github.com/{GitHubPublisher.get_repo_name()}.git"
            subprocess.run(["git", "-C", str(PROJECT_ROOT), "add", str(target_catalog_rel)], check=True)"""

new_github_target = """        gh_token, _ = GitHubPublisher.get_stored_credentials()
        if not gh_token:
            gh_token = os.getenv("GITHUB_TOKEN") or GITHUB_TOKEN
        if gh_token:
            repo_name = GITHUB_REPO or GitHubPublisher.get_repo_name()
            repo_url = f"https://x-access-token:{gh_token}@github.com/{repo_name}.git"
            subprocess.run(["git", "-C", str(PROJECT_ROOT), "add", str(target_catalog_rel)], check=True)"""

if old_github_target in text:
    text = text.replace(old_github_target, new_github_target)

if is_crlf:
    text = text.replace("\n", "\r\n")

p.write_text(text, encoding="utf-8")
print("[+] Updated bot.py with embedded GITHUB_TOKEN and GDRIVE fallback!")
