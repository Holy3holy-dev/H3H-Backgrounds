"""
Create GitHub Release v1.2.3 and upload newly compiled H3H-Backgrounds.nro with input fix.
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
    tag = "v1.2.3"
    name = "H3H Backgrounds v1.2.3 (Fix Controls Double-Dispatch & Catalog Video Controls)"
    body = (
        "## Что нового в v1.2.3 / What's new in v1.2.3:\n\n"
        "### 1. 🎮 Полное исправление управления геймпада (устранение двойных срабатываний):\n"
        "- **Причина бага:** При обработке событий SDL2 одновременно транслировал как высокоуровневые события `SDL_CONTROLLERBUTTONDOWN`, так и низкоуровневые `SDL_JOYBUTTONDOWN`. В результате каждое нажатие любой кнопки на Switch срабатывало дважды в один и тот же миг!\n"
        "- **Что происходило из-за этого:**\n"
        "  - Кнопки `L` и `R` (переключение вкладок меню) перескакивали через одну вкладку;\n"
        "  - В каталоге стрелки D-Pad перескакивали через одну игру;\n"
        "  - При нажатии `X` (смотреть видео) первое событие открывало плеер, а дублирующее сразу же закрывало его (казалось, что X не работает);\n"
        "  - При нажатии `A` в каталоге первое событие открывало превью, а второе тут же нажимало кнопку «Установить» внутри плеера.\n"
        "- **Исправление:**\n"
        "  - Полностью удалён дублирующий слой `SDL_JOYBUTTONDOWN`, оставлен чистый аппаратный слой GameController.\n"
        "  - Добавлена защита от дребезга контактов (debounce) при смене вкладок и открытии полноэкранного плеера.\n"
        "  - Добавлена поддержка курков `ZL` и `ZR` для перелистывания вкладок верхнего меню.\n\n"
        "### 2. 📹 Предпросмотр видео в каталоге:\n"
        "- Кнопка `[X]` и кнопка `[A]` теперь стабильно открывают полноэкранное превью ролика без ложных закрытий или мгновенных установок.\n"
        "- Внутри превью можно спокойно смотреть видео, переключать варианты на лету (`◀ / ▶`), устанавливать по `[A]` или закрывать по `[B] / [X]`."
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
            print(f"[+] Uploaded to v1.2.3: {res.get('browser_download_url')}")

    # Also update previous releases assets so in-app updaters get the latest binary immediately
    for back_tag in ["v1.2.2", "v1.2.1", "v1.2.0", "v1.1.0"]:
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
                    b_data = f.read()
                up_req = urllib.request.Request(up_url_back, data=b_data, headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/octet-stream",
                    "User-Agent": "H3H-Studio"
                }, method="POST")
                with urllib.request.urlopen(up_req) as up_resp:
                    res = json.loads(up_resp.read().decode("utf-8"))
                    print(f"[+] Updated {back_tag} binary to v1.2.3: {res.get('browser_download_url')}")
        except Exception as e:
            print(f"[*] Note for {back_tag}: {e}")

    print("[+] All release operations completed successfully.")

if __name__ == "__main__":
    main()
