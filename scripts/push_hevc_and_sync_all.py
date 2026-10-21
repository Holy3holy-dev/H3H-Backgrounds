import sys
import subprocess
from pathlib import Path

sys.path.insert(0, 'studio')
from h3h_studio.core.github_publisher import GitHubPublisher

gh_token, _ = GitHubPublisher.get_stored_credentials()
if not gh_token:
    print("[-] No GitHub token!")
    sys.exit(1)

repo_name = "Holy3holy-dev/H3H-Backgrounds"
repo_url = f"https://x-access-token:{gh_token}@github.com/{repo_name}.git"

# 1. Commit HEVC changes
print("[*] Staging HEVC changes...")
subprocess.run(["git", "add", "tg_bot/bot.py", "studio/h3h_studio/core/encoder.py"])
subprocess.run(["git", "commit", "-m", "feat: add HEVC (H.265) encoding and toggle in TG bot & Studio encoder with NVDEC compatibility (hvc1 tag)"])

# 2. Push main (contains bot fixes, HEVC support, and After Dark catalog for backward compatibility with v1)
print("[*] Pushing 'main' to GitHub...")
res1 = subprocess.run(["git", "push", repo_url, "main"], capture_output=True, text=True)
print("Main push result:\n", res1.stdout, res1.stderr)

# 3. Push after-dark branch
print("[*] Pushing 'after-dark' branch to GitHub...")
res2 = subprocess.run(["git", "push", repo_url, "HEAD:refs/heads/after-dark"], capture_output=True, text=True)
print("After-Dark push result:\n", res2.stdout, res2.stderr)

if res1.returncode == 0:
    print("[+] SUCCESS! Main and After-Dark branches synced.")
    sys.exit(0)
else:
    sys.exit(1)
