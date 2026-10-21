from pathlib import Path

p = Path("scripts/auto_video_harvester.py")
content = p.read_text(encoding="utf-8")

old_push = """            gh_token, _ = GitHubPublisher.get_stored_credentials()
            repo_url = f"https://x-access-token:{gh_token}@github.com/Holy3holy-dev/H3H-Backgrounds.git"
            rel_cat = str(self.catalog_path.relative_to(PROJECT_ROOT)).replace("\\\\", "/")

            subprocess.run(["git", "add", rel_cat, str(self.log_file.relative_to(PROJECT_ROOT))], check=True)
            subprocess.run(["git", "commit", "-m", f"feat(harvest): automated batch harvest {harvested_count} {self.mode} video themes ({self.codec.upper()})"], check=True)
            if self.mode == "after_dark":
                subprocess.run(["git", "push", repo_url, "HEAD:refs/heads/after-dark"], check=True)
            subprocess.run(["git", "push", repo_url, "HEAD:refs/heads/main"], check=True)
            print(f"[SUCCESS] Successfully pushed {harvested_count} new video backgrounds to GitHub!")"""

new_push = """            gh_token, _ = GitHubPublisher.get_stored_credentials()
            repo_url = f"https://x-access-token:{gh_token}@github.com/Holy3holy-dev/H3H-Backgrounds.git"
            rel_cat = str(self.catalog_path.relative_to(PROJECT_ROOT)).replace("\\\\", "/")

            # Pull remote changes first to prevent collision with Telegram bot community uploads
            try:
                subprocess.run(["git", "pull", "--rebase", repo_url, "main"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

            subprocess.run(["git", "add", rel_cat, str(self.log_file.relative_to(PROJECT_ROOT))], check=True)
            subprocess.run(["git", "commit", "-m", f"feat(harvest): automated batch harvest {harvested_count} {self.mode} video themes ({self.codec.upper()})"], check=True)
            
            for push_att in range(1, 4):
                try:
                    if self.mode == "after_dark":
                        subprocess.run(["git", "push", repo_url, "HEAD:refs/heads/after-dark"], check=True)
                    subprocess.run(["git", "push", repo_url, "HEAD:refs/heads/main"], check=True)
                    print(f"[SUCCESS] Successfully pushed {harvested_count} new video backgrounds to GitHub!")
                    break
                except Exception as pe:
                    print(f"[!] Git push attempt {push_att}/3 failed: {pe}. Rebasing...")
                    subprocess.run(["git", "pull", "--rebase", repo_url, "main"], check=False)
                    time.sleep(2)"""

content_norm = content.replace("\r\n", "\n")
old_norm = old_push.replace("\r\n", "\n")
new_norm = new_push.replace("\r\n", "\n")

if old_norm in content_norm:
    content_norm = content_norm.replace(old_norm, new_norm)
    p.write_text(content_norm, encoding="utf-8")
    print("[+] Successfully patched auto_video_harvester.py with rebase & retry push!")
else:
    print("[-] Target push block not found")
