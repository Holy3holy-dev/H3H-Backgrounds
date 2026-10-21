from pathlib import Path

p = Path("tg_bot/bot.py")
content = p.read_text(encoding="utf-8")

old_push = """def push_catalog_to_github(catalog_rel: Path, commit_msg: str, branch: Optional[str] = None) -> bool:
    \"\"\"Commits catalog changes and pushes to GitHub branch via GitHub REST API (rock-solid on Render/containers).\"\"\"
    gh_token, _ = GitHubPublisher.get_stored_credentials()
    if not gh_token:
        gh_token = os.getenv("GITHUB_TOKEN") or GITHUB_TOKEN
    if not gh_token:
        print("[!] No GitHub token available for pushing to remote.")
        return False"""

new_push = """def push_catalog_to_github(catalog_rel: Path, commit_msg: str, branch: Optional[str] = None) -> bool:
    \"\"\"Commits catalog changes and pushes to GitHub branch via GitHub REST API (rock-solid on Render/containers).\"\"\"
    push_catalog_to_github.last_error = ""
    gh_token, _ = GitHubPublisher.get_stored_credentials()
    if not gh_token:
        gh_token = os.getenv("GITHUB_TOKEN") or GITHUB_TOKEN
    if not gh_token:
        push_catalog_to_github.last_error = "Отсутствует GITHUB_TOKEN"
        print(f"[!] No GitHub token available for pushing to remote.")
        return False"""

old_step3_check = """            push_ok = push_catalog_to_github(target_catalog_rel, commit_msg, branch=target_branch)
            if not push_ok:
                raise RuntimeError("Не удалось опубликовать изменения в репозиторий GitHub.")"""

new_step3_check = """            push_ok = push_catalog_to_github(target_catalog_rel, commit_msg, branch=target_branch)
            if not push_ok:
                err_msg = getattr(push_catalog_to_github, "last_error", "") or "Ошибка API / прав доступа"
                raise RuntimeError(f"Не удалось опубликовать изменения в репозиторий GitHub: {err_msg}")"""

content_norm = content.replace("\r\n", "\n")
if old_push.replace("\r\n", "\n") in content_norm:
    content_norm = content_norm.replace(old_push.replace("\r\n", "\n"), new_push.replace("\r\n", "\n"))
if old_step3_check.replace("\r\n", "\n") in content_norm:
    content_norm = content_norm.replace(old_step3_check.replace("\r\n", "\n"), new_step3_check.replace("\r\n", "\n"))

p.write_text(content_norm, encoding="utf-8")
print("[+] Updated push_catalog_to_github with detailed error tracking!")
