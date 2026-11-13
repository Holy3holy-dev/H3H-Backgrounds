with open("scripts/generate_batch_hq_icons.py", "r", encoding="utf-8") as f:
    text = f.read()

# Add imports
text = text.replace(
    "from h3h_studio.core.google_drive import GoogleDriveClient",
    "from h3h_studio.core.google_drive import GoogleDriveClient\nfrom h3h_studio.core.github_publisher import GitHubPublisher\nfrom tg_bot.config import detect_local_proxy"
)

old_push = """        # Sync with upstream to avoid parallel conflicts
        subprocess.run(["git", "pull", "--rebase", "origin", "main"], check=False)
        # Commit and push to git
        subprocess.run(["git", "add", "catalog/data/catalog.json"], check=False)
        msg = f"feat(icons): add {processed_count} high-quality 4IFIR video icons (Lanczos 1.2M) [skip render] [skip ci]"
        subprocess.run(["git", "commit", "-m", msg], check=False)
        subprocess.run(["git", "push", "origin", "main"], check=False)
        print(f"[+] Pushed to GitHub main: {msg}")"""

new_push = """        # Sync and push with authenticated GitHub token
        gh_token, _ = GitHubPublisher.get_stored_credentials()
        local_proxy = detect_local_proxy()
        repo_url = f"https://x-access-token:{gh_token}@github.com/Holy3holy-dev/H3H-Backgrounds.git" if gh_token else "origin"
        git_env = os.environ.copy()
        git_env["GIT_EDITOR"] = ":"
        git_env["GIT_TERMINAL_PROMPT"] = "0"
        if local_proxy:
            git_env["http_proxy"] = local_proxy
            git_env["https_proxy"] = local_proxy

        subprocess.run(["git", "pull", "--rebase", repo_url, "main"], env=git_env, check=False)
        subprocess.run(["git", "add", "catalog/data/catalog.json"], check=False)
        msg = f"feat(icons): add {processed_count} high-quality 4IFIR video icons (Lanczos 1.2M) [skip render] [skip ci]"
        subprocess.run(["git", "commit", "-m", msg], env=git_env, check=False)
        res_push = subprocess.run(["git", "push", repo_url, "HEAD:refs/heads/main"], env=git_env, capture_output=True, text=True)
        if res_push.returncode == 0:
            print(f"[+] Pushed to GitHub main: {msg}")
        else:
            print(f"[-] Git push notice: {res_push.stderr}")"""

text = text.replace(old_push, new_push)

with open("scripts/generate_batch_hq_icons.py", "w", encoding="utf-8") as f:
    f.write(text)

print("[+] Successfully patched scripts/generate_batch_hq_icons.py for authenticated git push!")
