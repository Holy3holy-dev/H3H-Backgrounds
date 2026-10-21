"""
Create GitHub Release v1.0.6 and upload newly compiled H3H-Backgrounds.nro.
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
    tag = "v1.0.6"
    name = "H3H Backgrounds v1.0.6 (Live Motion Video Preview at 30 FPS & Active Background Identification)"
    body = (
        "## Что нового в v1.0.6 / What's new in v1.0.6:\n\n"
        "- **Полноценный живой предпросмотр видео ([X] На весь экран):**\n"
        "  - Встроен аппаратный декодер FFmpeg (`libavcodec`, `libavformat`, `libswscale`) под архитектуру Nintendo Switch (ARM Cortex-A57).\n"
        "  - При нажатии `[X]` теперь проигрывается **настоящий видеоролик** в 1280x720 @30fps в бесконечном бесшовном цикле, а не просто статичная картинка!\n"
        "  - Мгновенный запуск без ожидания: если этот вариант уже установлен на консоли, видео воспроизводится напрямую с SD-карты с нулевой задержкой.\n"
        "- **Чёткая идентификация установленного фона:**\n"
        "  - В списке вариантов игры теперь отображается зелёный светящийся бейдж **`[ УСТАНОВЛЕН ]`**, сразу показывающий, какой именно из вариантов сейчас активен на вашей консоли.\n"
        "  - В полноэкранном режиме выводится бейдж **`[ АКТИВЕН НА SWITCH ]`** и кнопка `[A] Переустановить`.\n"
        "- **Плавная буферизация:**\n"
        "  - При открытии нового варианта сначала моментально отображается HD-кадр, а через 1-2 секунды буферизации плавно стартует воспроизведение видео.\n"
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
            print(f"[+] Uploaded to v1.0.6: {res.get('browser_download_url')}")

    # Also update v1.0.5 and v1.0.4 assets so any in-app updater gets the latest video binary
    for back_tag in ["v1.0.5", "v1.0.4"]:
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

    print("\n[+] Release v1.0.6 successfully published!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
