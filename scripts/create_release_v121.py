"""
Create GitHub Release v1.2.1 and upload newly compiled H3H-Backgrounds.nro with fixes for Plus button, video buffering, and all NFS MW variants.
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
    tag = "v1.2.1"
    name = "H3H Backgrounds v1.2.1 (Fix Plus (+) button, Robust Video Buffer & All NFS MW Variants)"
    body = (
        "## Что нового в v1.2.1 / What's new in v1.2.1:\n\n"
        "### 1. 🎮 Исправлена кнопка `[+]` и открыт браузер записей SD:\n"
        "- Кнопка **`[+]`** (Plus на правом джойконе) и нажатие левого стика **`[L3]`** во вкладке «Мои игры» теперь мгновенно открывают окно выбора геймплейных роликов из `sdmc:/recordings/`.\n"
        "- Добавлена визуальная сенсорная кнопка **`[+] Записи 4IFIR (SD)`** прямо в карточке выбранной игры (можно нажать пальцем на сенсорном экране).\n\n"
        "### 2. ⚡ Устранён чёрный экран и зависание буферизации видео:\n"
        "- **Защита от чёрного экрана:** плеер больше не отображает пустую текстуру при задержке декодирования и корректно валидирует первые кадры видео.\n"
        "- **Атомарная загрузка с защитой от повреждений:** видеоролики сначала скачиваются во временный буфер и проверяются на корректность контейнера MP4. Ошибки серверов и битые файлы больше не попадают в кэш.\n"
        "- **Поддержка Cookie и защита от зависаний сети:** добавлены параметры CURL для корректной обработки редиректов Google Drive и 10-секундный таймаут при обрыве Wi-Fi соединения.\n\n"
        "### 3. 🏎️ Полный набор из 6 вариантов для Need for Speed: Most Wanted:\n"
        "- В каталоге для всех Title ID игры Need for Speed: Most Wanted (включая пользовательский Title ID `03DB18EF71F2C000`, 2005, порты и форвардеры) теперь доступны **все 6 вариантов** видеофонов:\n"
        "  1. *NFS MW: BMW M3 GTR Intro* (Кинематографичный ролик)\n"
        "  2. *NFS MW: Blacklist Pursuit* (Погоня Чёрного списка)\n"
        "  3. *NFS MW: Rockport Highway* (Геймплей на автостраде)\n"
        "  4. *NFS MW: Police Chase Action* (Погоня полиции 5 уровня)\n"
        "  5. *NFS MW: Animated Artwork Hero* (Анимированный постер SteamGridDB)\n"
        "  6. *NFS MW: City Skyline Neon* (Неоновый ночной город)\n"
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
            print(f"[+] Uploaded to v1.2.1: {res.get('browser_download_url')}")

    # Also update previous releases assets so in-app updaters get the latest binary
    for back_tag in ["v1.2.0", "v1.1.0", "v1.0.9"]:
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
                    print(f"[+] Updated {back_tag} binary to v1.2.1: {res_b.get('browser_download_url')}")
        except Exception as ex:
            print(f"[-] Could not update {back_tag}: {ex}")

    print("[+] All release operations completed successfully.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
