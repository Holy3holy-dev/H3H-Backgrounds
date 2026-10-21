import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path("studio").resolve()))
from h3h_studio.core.github_publisher import GitHubPublisher

def main():
    token, _ = GitHubPublisher.get_stored_credentials()
    if not token:
        print("ERROR: GitHub token not found.")
        return 1

    repo_url = f"https://x-access-token:{token}@github.com/Holy3holy-dev/H3H-Backgrounds.git"

    # Git add modified files
    subprocess.run(["git", "add", "downloader/", "version.json", "scripts/apply_v124_blackscreen_root_fix.py", "scripts/fix_helper_placement.py", "scripts/create_release_v124.py"], check=True)
    
    commit_res = subprocess.run(["git", "commit", "-m", "fix(render): fix black screen on Switch GLES2 via explicit SDL_Rect fullscreen coordinates, direct GPU SDL_LockTexture decode, and fopen devoptab loading (v1.2.4)"], capture_output=True, text=True)
    print("Commit output:", commit_res.stdout, commit_res.stderr)

    print("Pushing to main...")
    push_res = subprocess.run(["git", "push", repo_url, "main"], capture_output=True, text=True)
    print("Push output:", push_res.stdout, push_res.stderr)

if __name__ == "__main__":
    main()
