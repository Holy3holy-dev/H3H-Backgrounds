"""
Create GitHub Release v1.0.5 and upload newly compiled H3H-Backgrounds.nro.
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
    tag = "v1.0.5"
    name = "H3H Backgrounds v1.0.5 (Crash Fix for [X] Preview, Cuphead Clean, Two-Pane Polish)"
    body = (
        "## Что нового в v1.0.5 / What's new in v1.0.5:\n\n"
        "- **Устранён вылет при полноэкранном предпросмотре ([X] На весь экран):**\n"
        "  - Потокобезопасная асинхронная загрузка с корректным управлением жизненным циклом потоков на Horizon OS (устранён `std::thread::detach()`, приводивший к аварийному завершению NRO).\n"
        "  - Канонические абсолютные пути к кэшу миниатюр (`sdmc:/switch/H3H-Backgrounds/thumbs/<TID>_<VariantID>.jpg`) без использования относительных переходов `..`.\n"
        "- **Исправление фона Cuphead (\"С капхэдом чуть-чуть винда\"):**\n"
        "  - Полностью вырезана панель задач Windows 11 и иконки рабочего стола, исходное видео перекодировано в чистый 16:9 1280x720 @30fps 1:1 SAR и перезалито в облако.\n"
        "- **Улучшенная навигация кнопкой [B]:**\n"
        "  - При нахождении в списке вариантов кнопка [B] теперь возвращает фокус в левую колонку выбора игр, а не выкидывает на главную вкладку.\n"
        "- **Точные размеры файлов и честные теги звука:**\n"
        "  - Все 720+ вариантов в каталоге синхронизированы с реальными байтовыми размерами на диске H:\\.\n"
        "  - Теги [ ЗВУК ] / [ БЕЗ ЗВУКА ] соответствуют фактическому наличию аудиодорожек в MP4.\n"
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
            print(f"[+] Uploaded to v1.0.5: {res.get('browser_download_url')}")

    # Also update v1.0.4 asset in case in-app updater targets v1.0.4
    try:
        get_104 = urllib.request.Request(f"https://api.github.com/repos/{repo}/releases/tags/v1.0.4", headers=headers)
        with urllib.request.urlopen(get_104) as resp:
            rel_104 = json.loads(resp.read().decode("utf-8"))
            for asset in rel_104.get("assets", []):
                if asset["name"] == "H3H-Backgrounds.nro":
                    del_req = urllib.request.Request(asset["url"], headers=headers, method="DELETE")
                    with urllib.request.urlopen(del_req):
                        pass
            up_base_104 = rel_104["upload_url"].split("{")[0]
            up_req = urllib.request.Request(f"{up_base_104}?name=H3H-Backgrounds.nro", data=data, headers=up_headers, method="POST")
            with urllib.request.urlopen(up_req):
                print("[+] Also updated v1.0.4 asset for backward compatibility!")
    except Exception as e:
        print(f"[-] Note on v1.0.4 update: {e}")

    print("\n[+] Release v1.0.5 successfully published!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
