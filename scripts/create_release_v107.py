"""
Create GitHub Release v1.0.7 and upload newly compiled H3H-Backgrounds.nro.
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
    tag = "v1.0.7"
    name = "H3H Backgrounds v1.0.7 (Pixel-Perfect UI, Stale Cache Auto-Purge, & Fixed Version Display)"
    body = (
        "## Что нового в v1.0.7 / What's new in v1.0.7:\n\n"
        "- **Исправлена верстка и наложения в меню (Pixel-Perfect layout):**\n"
        "  - Полностью разделены колонки в карточке варианта: технические характеристики (1280x720 @30fps | 7.4 MB), зеленый бейдж `[ УСТАНОВЛЕН ]`, плашка `[ ЗВУК ]` и кнопка `[A] Переустановить` больше никогда не накладываются друг на друга.\n"
        "  - В окне обновления NRO длина строки теперь жестко ограничена рамками диалога (`dw - 70`), текст больше не уезжает за экран.\n"
        "- **Исправлено отображение версии в настройках:**\n"
        "  - В строке «Обновление приложения (NRO)» устранена старая статическая надпись v1.0.3. Теперь корректно выводится актуальная версия `v1.0.7 [A - Проверить]`.\n"
        "- **Автоматическая очистка устаревшего кэша видео:**\n"
        "  - Функция предпросмотра теперь проверяет соответствие размера файла в кэше с каталогом. Если фон был обновлен на чистую версию (как Red Dead Redemption и Cuphead), старый кэш с посторонним интерфейсом автоматически удаляется и скачивается чистый ролик.\n"
        "- **Монолитный HUD в полноэкранном плеере:**\n"
        "  - Нижняя плашка управления сделана монолитной (#0D111A), чтобы кадры и надписи из проигрываемого видео не просвечивали сквозь кнопки.\n"
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
            print(f"[+] Uploaded to v1.0.7: {res.get('browser_download_url')}")

    # Also update latest, v1.0.6, v1.0.5, and v1.0.4 assets so any in-app updater gets the new binary
    for back_tag in ["v1.0.6", "v1.0.5", "v1.0.4"]:
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

    print("\n[+] Release v1.0.7 successfully published!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
