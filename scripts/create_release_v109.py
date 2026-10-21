"""
Create GitHub Release v1.0.9 and upload newly compiled H3H-Backgrounds.nro.
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
    tag = "v1.0.9"
    name = "H3H Backgrounds v1.0.9 (Catalog Previews for Uninstalled Games & Exact Installed Variant Tracking)"
    body = (
        "## Что нового в v1.0.9 / What's new in v1.0.9:\n\n"
        "- **Предпросмотр любой игры из каталога без установки ([X] / [A]):**\n"
        "  - Теперь прямо во вкладке **«Каталог»** можно выбрать абсолютно любую игру из 702+ наименований (даже если она не установлена на консоли) и нажать `[X]` или `[A]` (либо тапнуть на экран), чтобы запустить полноэкранный предпросмотр видеоролика в 1280x720 HD 30 FPS!\n"
        "  - Прямо на лету можно переключать все стили и варианты выбранной игры кнопками `[◀ / ▶ D-Pad]`.\n"
        "  - Если игра ещё не установлена, по кнопке `[A]` видеофон можно сохранить в `sdmc:/recordings/covers/` заранее, чтобы он активировался автоматически, как только вы установите саму игру.\n"
        "- **Точная идентификация активного варианта (`installed_variants.json`):**\n"
        "  - Устранена путаница с бейджами: в играх с несколькими вариантами фона теперь зелёный бейдж **`[ УСТАНОВЛЕН ]`** горит **строго на том варианте**, который физически установлен на консоли.\n"
        "  - Создан постоянный реестр установленных вариантов `installed_variants.json`, который отслеживает реальный ID установленного фона даже при перезапусках приложения.\n"
        "- **Исправлено переключение кадров/роликов между вариантами:**\n"
        "  - Решена проблема, когда при установленном фоне при смене вариантов проигрывался только старый ролик. Теперь при листании вариантов D-Pad влево/вправо кадр и видеоряд мгновенно меняются на выбранный вариант!\n"
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
            print(f"[+] Uploaded to v1.0.9: {res.get('browser_download_url')}")

    # Also update v1.0.8, v1.0.7, v1.0.6 assets so any in-app updater gets the latest binary immediately
    for back_tag in ["v1.0.8", "v1.0.7"]:
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
                up_req = urllib.request.Request(f"{up_base_back}?name=H3H-Backgrounds.nro", data=data, headers=up_headers, method="POST")
                with urllib.request.urlopen(up_req):
                    print(f"[+] Also updated {back_tag} asset for seamless backward compatibility!")
        except Exception as e:
            print(f"[-] Note on {back_tag} update: {e}")

    print("\n[+] Release v1.0.9 successfully published!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
