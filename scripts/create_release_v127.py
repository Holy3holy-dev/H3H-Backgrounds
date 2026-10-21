import json
import sys
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path("studio").resolve()))
from h3h_studio.core.github_publisher import GitHubPublisher

def main():
    token, _ = GitHubPublisher.get_stored_credentials()
    if not token:
        print("ERROR: GitHub token not found.")
        return 1

    repo = "Holy3holy-dev/H3H-Backgrounds"
    tag = "v1.2.7"
    name = "H3H Backgrounds & After Dark v1.2.7 (Collection Browser, Live Mini-Previews & B-Only Exit)"
    body = (
        "## Что нового в v1.2.7 / What's new in v1.2.7:\n\n"
        "### 🖼 1. Полноценная Галерея коллекций (Collection Browser) и статические мини-превью\n"
        "- **Вход в коллекции по кнопке [A]:** Больше не нужно листать 50+ фонов вслепую в полноэкранном плеере. Нажатие [A] на карточке коллекции (включая After Dark) открывает удобную полноразмерную галерею.\n"
        "- **Список названий:** Слева отображается структурированный список фонов с названиями, разрешением, кодеком и метками звука ([ЗВУК] / [БЕЗ ЗВУКА]).\n"
        "- **Статические мини-превью в реальном времени (16:9):** Справа выводится окно с картинкой выбранного фона, загружаемой на лету.\n"
        "- **Быстрый переход:** Стрелки [◀ / ▶] перелистывают список сразу по 5 позиций.\n"
        "- **Прямое назначение:** Кнопка [A] / [Y] сразу открывает Target Game Picker для привязки фона к любой установленной игре.\n\n"
        "### 🎮 2. Единственный вариант выхода из приложения — кнопка [B]\n"
        "- Случайные закрытия приложения по клавише «+» (Plus) полностью исключены.\n"
        "- Теперь выход в Homebrew Menu происходит строго по нажатию кнопки [B] из главного меню (Home или список «Мои игры»), а во всех остальных экранах и меню [B] аккуратно возвращает на шаг назад.\n\n"
        "### 🔔 3. Фоновая автопроверка обновлений при запуске\n"
        "- При старте приложение само в фоне опрашивает GitHub. Если вышла новая версия — снизу на несколько секунд всплывает уведомление о наличии обновления.\n\n"
        "### 🤖 4. Официальный Telegram-бот сообщества\n"
        "- Загрузка видео и ZIP-архивов напрямую в базу Switch.\n"
        "- Оптимизированная облачная конвертация (-threads 2, fast_bilinear, crf 23).\n"
        "- Прямая запись потока (-c copy) для готовых 720p роликов.\n\n"
        "### ⚡ 5. Аппаратный HEVC (H.265) & расширение каталога\n"
        "- Поддержка тега hvc1 с аппаратным ускорением на чипе Tegra X1.\n"
        "- В основную ветку добавлены сотни хитов и хоумбрю-портов (NFS Underground, GTA, Doom, Quake, Portal, SM64, Zelda).\n"
        "- В After Dark добавлены подборки для игр с взрослым контентом (NieR, Bayonetta, Xenoblade, Persona 5, Catherine, Senran Kagura, DOA Xtreme, Azur Lane).\n"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "H3H-Studio"
    }

    # 1. Commit and push modified files
    print("[*] Committing modified files...")
    subprocess.run([
        "git", "add",
        "version.json",
        "downloader/include/core/config.hpp",
        "downloader/src/ui/app.cpp",
        "scripts/build_nro_after_dark.py"
    ], check=True)
    subprocess.run([
        "git", "commit", "-m",
        "release: v1.2.7 (Collection Browser, Mini-Previews, B-only Exit, Startup Update Check)"
    ], check=False)

    repo_url = f"https://x-access-token:{token}@github.com/Holy3holy-dev/H3H-Backgrounds.git"
    print("[*] Pushing to main...")
    subprocess.run(["git", "pull", "--rebase", repo_url, "main"], check=False)
    subprocess.run(["git", "push", repo_url, "HEAD:refs/heads/main"], check=True)

    # 2. Check if release v1.2.7 exists
    rel_url = f"https://api.github.com/repos/{repo}/releases/tags/{tag}"
    req = urllib.request.Request(rel_url, headers=headers)
    release_data = None
    try:
        with urllib.request.urlopen(req) as resp:
            release_data = json.loads(resp.read().decode())
            print(f"[+] Release {tag} already exists (id: {release_data['id']})")
            
            # Update release name & body
            patch_payload = json.dumps({"name": name, "body": body}).encode()
            patch_req = urllib.request.Request(
                f"https://api.github.com/repos/{repo}/releases/{release_data['id']}",
                data=patch_payload,
                headers=headers,
                method="PATCH"
            )
            with urllib.request.urlopen(patch_req) as p_resp:
                release_data = json.loads(p_resp.read().decode())
                print(f"[+] Updated release description for {tag}")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"[*] Release {tag} does not exist. Creating new release...")
            create_payload = json.dumps({
                "tag_name": tag,
                "target_commitish": "main",
                "name": name,
                "body": body,
                "draft": False,
                "prerelease": False
            }).encode()
            create_req = urllib.request.Request(
                f"https://api.github.com/repos/{repo}/releases",
                data=create_payload,
                headers=headers,
                method="POST"
            )
            with urllib.request.urlopen(create_req) as resp:
                release_data = json.loads(resp.read().decode())
                print(f"[+] Created release {tag} (id: {release_data['id']})")
        else:
            print(f"[-] HTTP error: {e}")
            return 1

    upload_url_tmpl = release_data.get("upload_url", "")
    base_upload_url = upload_url_tmpl.split("{")[0]

    # Upload both NROs
    nros = [
        ("H3H-Backgrounds.nro", Path("downloader/H3H-Backgrounds.nro")),
        ("H3H-AfterDark.nro", Path("downloader/H3H-AfterDark.nro"))
    ]

    for asset_name, nro_file in nros:
        if not nro_file.exists():
            print(f"[-] Missing file: {nro_file}")
            continue

        # Delete existing asset if any
        for existing in release_data.get("assets", []):
            if existing.get("name") == asset_name:
                print(f"[*] Deleting existing {asset_name} (id: {existing['id']})...")
                del_req = urllib.request.Request(
                    f"https://api.github.com/repos/{repo}/releases/assets/{existing['id']}",
                    headers=headers,
                    method="DELETE"
                )
                try:
                    urllib.request.urlopen(del_req)
                except Exception:
                    pass

        print(f"[*] Uploading {asset_name} ({nro_file.stat().st_size} bytes)...")
        data = nro_file.read_bytes()
        up_req = urllib.request.Request(
            f"{base_upload_url}?name={asset_name}",
            data=data,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/octet-stream",
                "User-Agent": "H3H-Studio"
            },
            method="POST"
        )
        with urllib.request.urlopen(up_req) as resp:
            up_res = json.loads(resp.read().decode())
            print(f"[+] Uploaded {asset_name}: {up_res.get('browser_download_url')}")

    print("\n[SUCCESS] Release v1.2.7 published with both H3H-Backgrounds.nro and H3H-AfterDark.nro!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
