import sys
import subprocess
from pathlib import Path

sys.path.insert(0, "studio")
from h3h_studio.core.github_publisher import GitHubPublisher

gh_token, _ = GitHubPublisher.get_stored_credentials()
if not gh_token:
    print("[-] No GitHub token!")
    sys.exit(1)

repo_name = "Holy3holy-dev/H3H-Backgrounds"
repo_url = f"https://x-access-token:{gh_token}@github.com/{repo_name}.git"

print("[*] Adding changed version and build files...")
subprocess.run(["git", "add", "version.json", "downloader/include/core/config.hpp", "downloader/Makefile", "downloader/H3H-Backgrounds.nro", "scripts/bump_version_135.py", "scripts/create_release_v135.py", "scripts/test_render_switch_overlay.py"])
subprocess.run(["git", "commit", "-m", "chore(release): bump version to 1.3.5 with standalone video icons & Switch Home UI overlay"])

print("[*] Pushing 'main' to GitHub...")
res1 = subprocess.run(["git", "push", repo_url, "main"], capture_output=True, text=True)
print("Main push result:", res1.stdout, res1.stderr)

if res1.returncode == 0:
    print("[+] Main branch successfully pushed!")
    sys.exit(0)
else:
    print("[!] Push failed!")
    sys.exit(1)
