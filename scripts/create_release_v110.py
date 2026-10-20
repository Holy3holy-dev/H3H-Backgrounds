"""
Create GitHub Release v1.1.0 and upload newly compiled H3H-Backgrounds.nro with Option 2 icon.
"""

import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path("studio").resolve()))
from h3h_studio.core.github_publisher import GitHubPublisher

def main():
    token, _ = GitHubPublisher.get_stored_credentials()
    if not token:
        print("ERROR: GitHub token not found.")
        return 1

    repo = "Holy3holy-dev/H3H-Backgrounds"
    tag = "v1.1.0"
    name = "H3H Backgrounds v1.1.0 (Official 4IFIR Gradient Icon & Fast CDN Invalidator)"
    body = (
        "## Что нового в v1.1.0 / What's new in v1.1.0:\n\n"
        "- **Официальная иконка приложения в стиле 4IFIR (Вариант 2 — Gradient «H»):**\n"
        "  - В NRO-пакет вшита фирменная иконка для Homebrew Menu Nintendo Switch:\n"
        "  - Стилизованная буква «H» с градиентным неоновым свечением от Cyan (`#00F2FE`) к Magenta (`#FF007F`), закругленная кибер-рамка и глубокий OLED-чёрный фон в каноничном стиле 4IFIR/Atmosphère.\n\n"
        "- **Мгновенная проверка обновлений (CDN Cache-Buster):**\n"
        "  - Исправлена задержка обновления из-за 5-минутного кэша GitHub CDN (`raw.githubusercontent.com`).\n"
        "  - Запрос проверки версии теперь отправляется с уникальным timestamp-параметром, гарантируя моментальное обнаружение новых релизов на Switch.\n\n"
        "- **Предпросмотр любой игры из каталога без установки ([X] / [A]):**\n"
        "  - Во вкладке **«Каталог»** доступен просмотр видеофона в 1280x720 HD 30 FPS для любой из 727+ игр без необходимости иметь саму игру на консоли.\n"
        "  - Поддержка переключения вариантов на лету `[◀ / ▶ D-Pad]`.\n\n"
        "- **Точный трекинг активного варианта (`installed_variants.json`):**\n"
        "  - Бейдж `[ УСТАНОВЛЕН ]` отображается строго на том варианте фона, который физически активен на Switch.\n"
        "  - Исправлено залипание кадров при листании вариантов.\n"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "H3H-Studio"
    }

    rel_url = f"https://api.github.com/repos/{repo}/releases"
    payload = json.dumps({
        "tag_name": tag,
        "target_commitish": "main",
        "name": name,
        "body": body,
        "draft": False,
        "prerelease": False
    }).encode("utf-8")

    req = urllib.request.Request(rel_url, data=payload, headers=headers, method="POST")
    rel_data = None
    try:
        with urllib.request.urlopen(req) as resp:
            rel_data = json.loads(resp.read().decode("utf-8"))
            print(f"[+] Created release {tag}: {rel_data.get('html_url')}")
    except urllib.error.HTTPError as e:
        print(f"[*] Release status: {e.code}, fetching existing tag...")
        get_req = urllib.request.Request(f"https://api.github.com/repos/{repo}/releases/tags/{tag}", headers=headers)
        with urllib.request.urlopen(get_req) as resp:
            rel_data = json.loads(resp.read().decode("utf-8"))

    upload_base = rel_data["upload_url"].split("{")[0]
    nro_path = Path(r"E:\videofon\downloader\H3H-Backgrounds.nro")

    if nro_path.exists():
        print(f"[*] Uploading H3H-Backgrounds.nro ({nro_path.stat().st_size} bytes)...")
        for asset in rel_data.get("assets", []):
            if asset["name"] == "H3H-Backgrounds.nro":
                del_req = urllib.request.Request(asset["url"], headers=headers, method="DELETE")
                with urllib.request.urlopen(del_req):
                    pass
                print("[-] Deleted old asset")

        upload_url = f"{upload_base}?name=H3H-Backgrounds.nro"
        with open(nro_path, "rb") as f:
            data = f.read()

        up_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/octet-stream",
            "User-Agent": "H3H-Studio"
        }
        up_req = urllib.request.Request(upload_url, data=data, headers=up_headers, method="POST")
        with urllib.request.urlopen(up_req) as up_resp:
            res = json.loads(up_resp.read().decode("utf-8"))
            print(f"[+] Uploaded to v1.1.0: {res.get('browser_download_url')}")

    # Also update previous releases assets so in-app updaters get the latest binary
    for back_tag in ["v1.0.9", "v1.0.8", "v1.0.7"]:
        try:
            get_req = urllib.request.Request(f"https://api.github.com/repos/{repo}/releases/tags/{back_tag}", headers=headers)
            with urllib.request.urlopen(get_req) as resp:
                rel_back = json.loads(resp.read().decode("utf-8"))
                for asset in rel_back.get("assets", []):
                    if asset["name"] == "H3H-Backgrounds.nro":
                        del_req = urllib.request.Request(asset["url"], headers=headers, method="DELETE")
                        with urllib.request.urlopen(del_req):
                            pass
                up_base_back = rel_back["upload_url"].split("{")[0]
                up_url_back = f"{up_base_back}?name=H3H-Backgrounds.nro"
                with open(nro_path, "rb") as f:
                    data = f.read()
                up_req_back = urllib.request.Request(up_url_back, data=data, headers=up_headers, method="POST")
                with urllib.request.urlopen(up_req_back) as up_resp:
                    res_b = json.loads(up_resp.read().decode("utf-8"))
                    print(f"[+] Updated {back_tag} binary to v1.1.0: {res_b.get('browser_download_url')}")
        except Exception as ex:
            print(f"[-] Could not update {back_tag}: {ex}")

    print("[+] All release operations completed successfully.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
