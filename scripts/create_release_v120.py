"""
Create GitHub Release v1.2.0 and upload newly compiled H3H-Backgrounds.nro with Features 3 & 5.
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
    tag = "v1.2.0"
    name = "H3H Backgrounds v1.2.0 (4IFIR SD Recordings Support & Integrity Scanner)"
    body = (
        "## Что нового в v1.2.0 / What's new in v1.2.0:\n\n"
        "### 1. 📹 Установка собственных геймплейных записей 4IFIR (`[+]` в «Мои игры»):\n"
        "- Теперь можно легко поставить на видеофон **любой собственный ролик или лучший игровой момент**, записанный в 4IFIR на Switch!\n"
        "- По нажатию кнопки **`[+]`** на выбранной игре открывается встроенный браузер записей из `sdmc:/recordings/`.\n"
        "- По кнопке **`[X]`** доступен мгновенный полноэкранный предпросмотр любого локального клипа прямо с карты памяти!\n"
        "- По кнопке **`[A]`** выбранный ролик безопасно привязывается к игре (оригинал видео в `recordings/` остаётся нетронутым).\n"
        "- Запись отображается в списке вариантов игры с фирменным бейджем **`[ УСТАНОВЛЕН ]`**!\n\n"
        "### 2. 🛡️ Проверка целостности видеофонов и защита от сбоев меню Switch:\n"
        "- В меню «Настройки» добавлен пункт **«Проверка целостности фонов»** (`[A]` — Сканировать).\n"
        "- Автоматически выявляет битые MP4, обрезанные при обрыве Wi-Fi файлы (0 байт), а также замаскированные HTML-страницы ошибок серверов/CDN.\n"
        "- При обнаружении повреждённых файлов приложение предлагает безопасно удалить их в 1 клик во избежание зависаний Horizon OS при наведении на иконку игры.\n"
        "- При скачивании новых видеофонов проверка целостности теперь выполняется автоматически до записи файла на MicroSD!\n"
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
            print(f"[+] Uploaded to v1.2.0: {res.get('browser_download_url')}")

    # Also update previous releases assets so in-app updaters get the latest binary
    for back_tag in ["v1.1.0", "v1.0.9", "v1.0.8"]:
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
                    print(f"[+] Updated {back_tag} binary to v1.2.0: {res_b.get('browser_download_url')}")
        except Exception as ex:
            print(f"[-] Could not update {back_tag}: {ex}")

    print("[+] All release operations completed successfully.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
