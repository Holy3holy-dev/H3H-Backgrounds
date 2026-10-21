from pathlib import Path

path = Path('studio/h3h_studio/core/google_drive.py')
text = path.read_text(encoding='utf-8')

target = '        if progress_cb:\n            progress_cb("Каталог успешно синхронизирован с GitHub!")\n\n        return True\n'
new_code = '''        if progress_cb:
            progress_cb("Каталог успешно синхронизирован с GitHub!")

        return True

    @classmethod
    def sync_file_to_github(
        cls,
        file_path: Path,
        repo_path: str,
        token: str,
        repo: str = "Holy3holy-dev/H3H-Backgrounds",
        commit_message: str = "chore: sync file to repository",
        progress_cb: None = None
    ) -> bool:
        """
        Commits any local file (such as harvest log or catalog) directly to GitHub repository via REST API.
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Файл не найден: {file_path}")

        raw_bytes = file_path.read_bytes()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "H3H-Studio"
        }

        content_url = f"https://api.github.com/repos/{repo}/contents/{repo_path.lstrip('/')}"
        c_get_req = urllib.request.Request(content_url, headers=headers)
        file_sha = None
        try:
            with urllib.request.urlopen(c_get_req, timeout=15) as cg_resp:
                c_info = json.loads(cg_resp.read().decode("utf-8"))
                file_sha = c_info.get("sha")
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise e

        b64_content = base64.b64encode(raw_bytes).decode("ascii")
        put_payload = {
            "message": commit_message,
            "content": b64_content
        }
        if file_sha:
            put_payload["sha"] = file_sha

        put_req = urllib.request.Request(
            content_url,
            data=json.dumps(put_payload).encode("utf-8"),
            headers={**headers, "Content-Type": "application/json"},
            method="PUT"
        )
        with urllib.request.urlopen(put_req, timeout=15):
            pass

        if progress_cb:
            progress_cb(f"Файл {repo_path} успешно синхронизирован с GitHub!")

        return True
'''

assert target in text, "Target string not found in google_drive.py"
text = text.replace(target, new_code)
path.write_text(text, encoding='utf-8')
print("Successfully patched google_drive.py!")
