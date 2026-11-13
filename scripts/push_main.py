import os
import sys
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "studio"))
sys.path.insert(0, str(PROJECT_ROOT))

from h3h_studio.core.github_publisher import GitHubPublisher
from tg_bot.config import detect_local_proxy

gh_token, _ = GitHubPublisher.get_stored_credentials()
if not gh_token:
    print("[-] GitHub token not found!")
    sys.exit(1)

local_proxy = detect_local_proxy()
repo_url = f"https://x-access-token:{gh_token}@github.com/Holy3holy-dev/H3H-Backgrounds.git"

git_env = os.environ.copy()
git_env["GIT_EDITOR"] = ":"
git_env["GIT_TERMINAL_PROMPT"] = "0"
if local_proxy:
    git_env["http_proxy"] = local_proxy
    git_env["https_proxy"] = local_proxy

print("[*] Fetching latest remote commits...")
subprocess.run(["git", "fetch", repo_url, "main"], env=git_env, check=True)

print("[*] Pushing with --force to publish clean consolidated history...")
res = subprocess.run(["git", "push", "--force", repo_url, "HEAD:refs/heads/main"], env=git_env, capture_output=True, text=True)
print("STDOUT:", res.stdout)
print("STDERR:", res.stderr)
print("Exit code:", res.returncode)
