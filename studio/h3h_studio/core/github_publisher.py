"""
GitHub Video Background Publisher for H3H Backgrounds.
Uploads 4IFIR-compliant MP4 backgrounds to GitHub Releases and updates catalog/data/catalog.json.
"""

import base64
import ctypes
import hashlib
import json
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

from .compliance import ComplianceValidator


class CREDENTIAL(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", wintypes.FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_byte)),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR)
    ]


class GitHubPublisher:
    DEFAULT_REPO = "Holy3holy-dev/H3H-Backgrounds"
    DEFAULT_TAG = "v1.0.0"

    CONFIG_FILE = Path.home() / ".h3h_github.json"

    @classmethod
    def save_stored_credentials(cls, token: str, user: str = "Holy3holy-dev", repo: str = DEFAULT_REPO) -> None:
        """Saves GitHub credentials to ~/.h3h_github.json."""
        try:
            data = {"token": token.strip(), "user": user.strip(), "repo": repo.strip()}
            cls.CONFIG_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            print(f"[-] Failed to save GitHub credentials to {cls.CONFIG_FILE}: {e}")

    @classmethod
    def get_stored_credentials(cls) -> Tuple[Optional[str], Optional[str]]:
        """
        Attempts to read GitHub credentials from ~/.h3h_github.json, environment, or Windows Credential Manager.
        """
        # 1. Check local persistent config file
        if cls.CONFIG_FILE.exists():
            try:
                data = json.loads(cls.CONFIG_FILE.read_text(encoding="utf-8"))
                tok = data.get("token")
                usr = data.get("user", "Holy3holy-dev")
                if tok and tok.strip():
                    return tok.strip(), usr
            except Exception:
                pass

        # 2. Check environment variable
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            return token, os.environ.get("GITHUB_USER", "Holy3holy-dev")

        # 3. Check Windows Credential Manager
        try:
            advapi32 = ctypes.WinDLL("advapi32.dll")
            CredReadW = advapi32.CredReadW
            CredReadW.argtypes = [
                wintypes.LPCWSTR,
                wintypes.DWORD,
                wintypes.DWORD,
                ctypes.POINTER(ctypes.POINTER(CREDENTIAL))
            ]
            CredReadW.restype = wintypes.BOOL

            cred_ptr = ctypes.POINTER(CREDENTIAL)()
            if CredReadW("git:https://github.com", 1, 0, ctypes.byref(cred_ptr)):
                cred = cred_ptr.contents
                raw = ctypes.string_at(cred.CredentialBlob, cred.CredentialBlobSize)
                token = raw.decode("utf-16le", errors="ignore").strip()
                user = cred.UserName or "Holy3holy-dev"
                return token, user
        except Exception as e:
            print(f"[-] Failed to read credentials from Windows Credential Manager: {e}")

        return None, None

    @classmethod
    def compute_sha256(cls, file_path: Path) -> str:
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()

    @classmethod
    def upload_video(
        cls,
        video_path: Path,
        title_id: str,
        game_title: str,
        variant_name: str,
        style: str,
        author: str,
        token: str,
        repo: str = DEFAULT_REPO,
        release_tag: str = DEFAULT_TAG,
        description: str = "",
        progress_cb: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Full publication flow:
        1. Compliance inspection
        2. SHA-256 calculation
        3. Upload MP4 asset to GitHub Releases
        4. Update catalog/data/catalog.json
        """
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        # Validate Title ID
        clean_tid = title_id.strip().upper()
        if not re.match(r"^[0-9A-Fa-f]{16}$", clean_tid):
            raise ValueError(f"Invalid Title ID format '{clean_tid}'. Must be 16 hexadecimal characters.")

        if progress_cb:
            progress_cb("Проверка соответствия стандартам 4IFIR...")

        # Compliance Check
        comp = ComplianceValidator.validate_mp4(video_path)
        if not comp.is_valid:
            errors = "; ".join(comp.errors)
            raise ValueError(f"Видео не соответствует требованиям 4IFIR: {errors}")

        if progress_cb:
            progress_cb("Вычисление контрольной суммы SHA-256...")

        file_size = video_path.stat().st_size
        sha256_hash = cls.compute_sha256(video_path)

        # Asset filename in release: 01007EF00011E000_variant.mp4
        safe_variant_id = re.sub(r"[^a-zA-Z0-9_\-]", "", variant_name.lower().replace(" ", "-"))
        if not safe_variant_id:
            safe_variant_id = "default"
        asset_name = f"{clean_tid}_{safe_variant_id}.mp4"

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "H3H-Background-Studio"
        }

        if progress_cb:
            progress_cb(f"Получение релиза GitHub '{release_tag}'...")

        # 1. Get Release info
        rel_url = f"https://api.github.com/repos/{repo}/releases/tags/{release_tag}"
        req = urllib.request.Request(rel_url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                rel_data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                # Create release if it doesn't exist
                if progress_cb:
                    progress_cb(f"Создание нового релиза '{release_tag}'...")
                create_url = f"https://api.github.com/repos/{repo}/releases"
                payload = {
                    "tag_name": release_tag,
                    "target_commitish": "main",
                    "name": f"H3H Backgrounds {release_tag}",
                    "body": "Official video background repository for Nintendo Switch 4IFIR.",
                    "draft": False,
                    "prerelease": False
                }
                c_req = urllib.request.Request(
                    create_url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={**headers, "Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(c_req, timeout=15) as c_resp:
                    rel_data = json.loads(c_resp.read().decode("utf-8"))
            else:
                raise RuntimeError(f"GitHub API Error {e.code}: {e.read().decode('utf-8', errors='ignore')}")

        # 2. Check if asset already exists in release, delete if so to overwrite
        for existing in rel_data.get("assets", []):
            if existing["name"] == asset_name:
                if progress_cb:
                    progress_cb(f"Удаление существующего ассета {asset_name}...")
                del_req = urllib.request.Request(existing["url"], headers=headers, method="DELETE")
                try:
                    with urllib.request.urlopen(del_req, timeout=15):
                        pass
                except Exception:
                    pass

        # 3. Upload asset
        upload_base = rel_data["upload_url"].split("{")[0]
        upload_url = f"{upload_base}?name={urllib.parse.quote(asset_name)}"

        if progress_cb:
            progress_cb(f"Загрузка {asset_name} ({file_size / 1024 / 1024:.2f} MB) на GitHub...")

        with open(video_path, "rb") as vf:
            video_bytes = vf.read()

        u_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/octet-stream",
            "User-Agent": "H3H-Background-Studio"
        }
        u_req = urllib.request.Request(upload_url, data=video_bytes, headers=u_headers, method="POST")
        with urllib.request.urlopen(u_req, timeout=120) as u_resp:
            uploaded_asset = json.loads(u_resp.read().decode("utf-8"))

        download_url = uploaded_asset.get("browser_download_url")

        # 4. Update catalog
        if progress_cb:
            progress_cb("Обновление каталога video backgrounds...")

        # Update local catalog file first
        catalog_path = Path(__file__).parent.parent.parent.parent / "catalog" / "data" / "catalog.json"
        cat_data = {"schemaVersion": 1, "updatedAt": "", "totalGames": 0, "totalVariants": 0, "games": []}
        if catalog_path.exists():
            try:
                with open(catalog_path, "r", encoding="utf-8") as cf:
                    cat_data = json.load(cf)
            except Exception:
                pass

        # Find or add game
        game_entry = None
        for g in cat_data.get("games", []):
            if g.get("titleId", "").upper() == clean_tid:
                game_entry = g
                break

        if not game_entry:
            game_entry = {
                "titleId": clean_tid,
                "title": game_title,
                "publisher": "Nintendo Switch",
                "iconUrl": f"https://raw.githubusercontent.com/Langegen/switch-game-collection/main/covers/{clean_tid}.jpg",
                "variants": []
            }
            cat_data.setdefault("games", []).append(game_entry)

        # Variant entry
        new_variant = {
            "id": safe_variant_id,
            "name": variant_name,
            "style": style,
            "version": "1.0",
            "url": download_url,
            "previewUrl": "",
            "sizeBytes": file_size,
            "sha256": sha256_hash,
            "durationSec": round(comp.duration_sec, 2),
            "author": author or "Anonymous",
            "codec": comp.codec or "h264",
            "width": comp.width,
            "height": comp.height,
            "fps": round(comp.fps, 1),
            "hasAudio": comp.has_audio,
            "notes": description or f"4IFIR verified: {comp.width}x{comp.height} @{round(comp.fps)}fps"
        }

        # Replace or append variant
        existing_idx = -1
        for idx, var in enumerate(game_entry.get("variants", [])):
            if var.get("id") == safe_variant_id:
                existing_idx = idx
                break

        if existing_idx >= 0:
            game_entry["variants"][existing_idx] = new_variant
        else:
            game_entry.setdefault("variants", []).append(new_variant)

        cat_data["updatedAt"] = datetime.now(timezone.utc).isoformat()
        cat_data["totalGames"] = len(cat_data["games"])
        cat_data["totalVariants"] = sum(len(g.get("variants", [])) for g in cat_data["games"])

        # Write local
        catalog_path.parent.mkdir(parents=True, exist_ok=True)
        with open(catalog_path, "w", encoding="utf-8") as cf:
            json.dump(cat_data, cf, ensure_ascii=False, indent=2)

        # Update on GitHub via contents API
        if progress_cb:
            progress_cb("Синхронизация каталога с GitHub репозиторием...")

        try:
            content_url = f"https://api.github.com/repos/{repo}/contents/catalog/data/catalog.json"
            c_get_req = urllib.request.Request(content_url, headers=headers)
            file_sha = None
            try:
                with urllib.request.urlopen(c_get_req, timeout=15) as cg_resp:
                    c_info = json.loads(cg_resp.read().decode("utf-8"))
                    file_sha = c_info.get("sha")
            except urllib.error.HTTPError as e:
                if e.code != 404:
                    pass

            raw_cat_bytes = json.dumps(cat_data, ensure_ascii=False, indent=2).encode("utf-8")
            b64_content = base64.b64encode(raw_cat_bytes).decode("ascii")

            put_payload = {
                "message": f"feat(catalog): add background {clean_tid} ({variant_name}) by {author}",
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
        except Exception as e:
            print(f"[-] Warning: Failed to commit catalog.json to GitHub directly: {e}")

        if progress_cb:
            progress_cb("Публикация завершена успешно!")

        return {
            "success": True,
            "titleId": clean_tid,
            "variantId": safe_variant_id,
            "downloadUrl": download_url,
            "sha256": sha256_hash,
            "sizeBytes": file_size,
            "targetCoverName": f"{clean_tid}.mp4",
            "sdCardPath": f"sdmc:/recordings/covers/{clean_tid}.mp4"
        }

    @classmethod
    def scan_archive_or_folder(cls, source_path: Path, progress_cb: Optional[callable] = None) -> List[Dict[str, Any]]:
        """
        Scans a .zip/.7z/.rar archive or directory for MP4 videos, extracts Title IDs from filenames
        or subfolder paths, and matches them against the Switch database.
        """
        import zipfile
        import tempfile
        import shutil
        import subprocess
        from .online_fetcher import OnlineFetcher

        source = Path(source_path)
        if not source.exists():
            return []

        search_dirs = []
        base_scan_dir = None

        if source.is_file():
            ext = source.suffix.lower()
            extract_dir = Path(tempfile.mkdtemp(prefix=f"h3h_batch_{source.stem}_"))
            base_scan_dir = extract_dir

            extracted_successfully = False
            tar_cmd = shutil.which("tar")
            if tar_cmd:
                if progress_cb:
                    progress_cb(f"Распаковка архива {source.name} со всеми подпапками...")
                try:
                    res = subprocess.run([tar_cmd, "-xf", str(source), "-C", str(extract_dir)], capture_output=True)
                    if res.returncode == 0:
                        extracted_successfully = True
                except Exception as e:
                    print(f"[-] tar extraction error: {e}")

            if not extracted_successfully and ext == ".zip":
                if progress_cb:
                    progress_cb("Чтение структуры и подпапок ZIP-архива...")
                try:
                    with zipfile.ZipFile(source, "r") as zf:
                        video_extensions = (".mp4", ".m4v", ".mov", ".mkv")
                        all_members = [
                            m for m in zf.infolist()
                            if not m.is_dir()
                            and not m.filename.startswith("__MACOSX")
                            and not Path(m.filename).name.startswith("._")
                        ]
                        video_members = [
                            m for m in all_members
                            if m.filename.lower().endswith(video_extensions)
                        ]
                        target_members = video_members if video_members else all_members
                        total_extract = len(target_members)

                        for idx, member in enumerate(target_members):
                            norm_rel = member.filename.replace("\\", "/").strip("/")
                            dest_file = extract_dir / Path(norm_rel)
                            dest_file.parent.mkdir(parents=True, exist_ok=True)

                            if progress_cb:
                                progress_cb(f"Извлечение [{idx+1}/{total_extract}]: {norm_rel}...")

                            with zf.open(member) as src_f, open(dest_file, "wb") as dst_f:
                                shutil.copyfileobj(src_f, dst_f)
                    extracted_successfully = True
                except Exception as ze:
                    print(f"[-] zipfile fallback error: {ze}")

            search_dirs.append(extract_dir)
        elif source.is_dir():
            search_dirs.append(source)
            base_scan_dir = source
        else:
            return []

        if progress_cb:
            progress_cb("Рекурсивный поиск видеофайлов во всех папках архива...")

        video_extensions = {".mp4", ".m4v", ".mov", ".mkv"}
        found_videos = []
        for d in search_dirs:
            for p in d.rglob("*"):
                if p.is_file() and p.suffix.lower() in video_extensions and not p.name.startswith("._"):
                    found_videos.append(p)

        if not found_videos:
            return []

        if progress_cb:
            progress_cb(f"Найдено {len(found_videos)} видеофайлов. Загрузка базы Switch...")

        db = OnlineFetcher._load_db()
        db_by_tid = {item["titleId"].upper(): item for item in db if item.get("titleId")}

        results = []
        total = len(found_videos)
        generic_names = {"video", "cover", "background", "loop", "main", "intro", "out", "output", "recording", "recordings", "covers", "gameplay"}

        for idx, vid in enumerate(sorted(found_videos, key=lambda x: x.name)):
            fname = vid.name
            rel_str = str(vid.relative_to(base_scan_dir if base_scan_dir else vid.parent)).replace("\\", "/")

            if progress_cb:
                progress_cb(f"Анализ видео [{idx+1}/{total}]: {rel_str}...")

            # 1. Search Title ID in filename (prefer 0100..., but accept any 16-hex chars, supports _ and -)
            m = re.search(r"(?<![0-9A-Za-z])(0100[0-9A-Fa-f]{12})(?![0-9A-Za-z])", fname, re.IGNORECASE)
            if not m:
                m = re.search(r"(?<![0-9A-Za-z])([0-9A-Fa-f]{16})(?![0-9A-Za-z])", fname)
            # 2. If not found in filename, search in relative path (folder names like recordings/covers/...)
            if not m:
                m = re.search(r"(?<![0-9A-Za-z])(0100[0-9A-Fa-f]{12})(?![0-9A-Za-z])", rel_str, re.IGNORECASE)
            if not m:
                m = re.search(r"(?<![0-9A-Za-z])([0-9A-Fa-f]{16})(?![0-9A-Za-z])", rel_str)

            matched_id = m.group(1) if m else ""
            tid = matched_id.upper() if matched_id else ""

            # Determine variant name
            base_no_ext = vid.stem
            variant_name = "Default"
            if tid:
                if matched_id in fname:
                    rem = base_no_ext.replace(matched_id, "").strip(" _-[]()")
                    if rem and rem.lower() not in generic_names:
                        variant_name = rem.replace("_", " ").title()
                else:
                    if base_no_ext.lower() not in generic_names:
                        variant_name = base_no_ext.replace("_", " ").title()

            db_entry = db_by_tid.get(tid, {}) if tid else {}
            game_title = db_entry.get("title", "")
            if not game_title:
                game_title = f"Switch Title ({tid})" if tid else vid.stem

            comp = ComplianceValidator.validate_mp4(vid)

            results.append({
                "path": str(vid),
                "filename": rel_str if "/" in rel_str else vid.name,
                "titleId": tid,
                "gameTitle": game_title,
                "variantName": variant_name,
                "style": "Animated Art" if "art" in fname.lower() else "Gameplay",
                "sizeBytes": vid.stat().st_size,
                "isValid": comp.is_valid,
                "errors": comp.errors,
                "width": comp.width,
                "height": comp.height,
                "fps": comp.fps,
                "durationSec": comp.duration_sec,
                "hasAudio": comp.has_audio,
                "codec": comp.codec,
            })

        if progress_cb:
            progress_cb(f"Сканирование завершено: найдено {len(results)} видео.")

        return results

    @classmethod
    def upload_batch_videos(
        cls,
        items: List[Dict[str, Any]],
        token: str,
        repo: str = DEFAULT_REPO,
        release_tag: str = DEFAULT_TAG,
        author: str = "Holy3holy-dev",
        progress_cb: Optional[callable] = None
    ) -> List[Dict[str, Any]]:
        """
        Uploads multiple MP4 files to GitHub Releases and commits all entries into catalog.json in one atomic update.
        """
        if not items:
            return []

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "H3H-Background-Studio"
        }

        # 1. Get or create release
        if progress_cb:
            progress_cb(f"Подключение к релизу '{release_tag}' на GitHub...")

        rel_url = f"https://api.github.com/repos/{repo}/releases/tags/{release_tag}"
        req = urllib.request.Request(rel_url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                rel_data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                create_url = f"https://api.github.com/repos/{repo}/releases"
                payload = {
                    "tag_name": release_tag,
                    "target_commitish": "main",
                    "name": f"H3H Backgrounds {release_tag}",
                    "body": "Official video background repository for Nintendo Switch 4IFIR.",
                    "draft": False,
                    "prerelease": False
                }
                c_req = urllib.request.Request(
                    create_url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={**headers, "Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(c_req, timeout=15) as c_resp:
                    rel_data = json.loads(c_resp.read().decode("utf-8"))
            else:
                raise RuntimeError(f"GitHub API Error {e.code}: {e.read().decode('utf-8', errors='ignore')}")

        upload_base = rel_data["upload_url"].split("{")[0]

        # 2. Load catalog
        catalog_path = Path(__file__).parent.parent.parent.parent / "catalog" / "data" / "catalog.json"
        cat_data = {"schemaVersion": 1, "updatedAt": "", "totalGames": 0, "totalVariants": 0, "games": []}
        if catalog_path.exists():
            try:
                with open(catalog_path, "r", encoding="utf-8") as cf:
                    cat_data = json.load(cf)
            except Exception:
                pass

        results = []
        total = len(items)

        for idx, it in enumerate(items):
            vid_path = Path(it["path"])
            clean_tid = it.get("titleId", "").strip().upper()
            if not clean_tid or len(clean_tid) != 16:
                continue

            variant_name = it.get("variantName", "Default")
            safe_variant_id = re.sub(r"[^a-zA-Z0-9_\-]", "", variant_name.lower().replace(" ", "-"))
            if not safe_variant_id:
                safe_variant_id = "default"

            asset_name = f"{clean_tid}_{safe_variant_id}.mp4"

            if progress_cb:
                progress_cb(f"[{idx+1}/{total}] Вычисление SHA-256 для {asset_name}...")

            file_size = vid_path.stat().st_size
            sha256_hash = cls.compute_sha256(vid_path)

            # Check if asset exists, delete to overwrite
            for existing in rel_data.get("assets", []):
                if existing["name"] == asset_name:
                    del_req = urllib.request.Request(existing["url"], headers=headers, method="DELETE")
                    try:
                        with urllib.request.urlopen(del_req, timeout=15):
                            pass
                    except Exception:
                        pass

            if progress_cb:
                progress_cb(f"[{idx+1}/{total}] Загрузка {asset_name} ({file_size / 1024 / 1024:.2f} MB)...")

            with open(vid_path, "rb") as vf:
                video_bytes = vf.read()

            upload_url = f"{upload_base}?name={urllib.parse.quote(asset_name)}"
            u_headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/octet-stream",
                "User-Agent": "H3H-Background-Studio"
            }
            u_req = urllib.request.Request(upload_url, data=video_bytes, headers=u_headers, method="POST")
            with urllib.request.urlopen(u_req, timeout=180) as u_resp:
                uploaded_asset = json.loads(u_resp.read().decode("utf-8"))

            download_url = uploaded_asset.get("browser_download_url")

            # Update catalog memory structure
            game_entry = None
            for g in cat_data.get("games", []):
                if g.get("titleId", "").upper() == clean_tid:
                    game_entry = g
                    break

            if not game_entry:
                game_entry = {
                    "titleId": clean_tid,
                    "title": it.get("gameTitle", f"Switch Title {clean_tid}"),
                    "publisher": "Nintendo Switch",
                    "iconUrl": f"https://raw.githubusercontent.com/Langegen/switch-game-collection/main/covers/{clean_tid}.jpg",
                    "variants": []
                }
                cat_data.setdefault("games", []).append(game_entry)

            new_variant = {
                "id": safe_variant_id,
                "name": variant_name,
                "style": it.get("style", "Gameplay"),
                "version": "1.0",
                "url": download_url,
                "previewUrl": "",
                "sizeBytes": file_size,
                "sha256": sha256_hash,
                "durationSec": round(float(it.get("durationSec", 15.0)), 2),
                "author": author or "Anonymous",
                "codec": it.get("codec", "h264"),
                "width": it.get("width", 1280),
                "height": it.get("height", 720),
                "fps": round(float(it.get("fps", 30.0)), 1),
                "hasAudio": bool(it.get("hasAudio", False)),
                "notes": f"Batch published: {it.get('width', 1280)}x{it.get('height', 720)} @{round(float(it.get('fps', 30.0)))}fps"
            }

            existing_idx = -1
            for var_idx, var in enumerate(game_entry.get("variants", [])):
                if var.get("id") == safe_variant_id:
                    existing_idx = var_idx
                    break

            if existing_idx >= 0:
                game_entry["variants"][existing_idx] = new_variant
            else:
                game_entry.setdefault("variants", []).append(new_variant)

            results.append({
                "titleId": clean_tid,
                "variantId": safe_variant_id,
                "filename": it["filename"],
                "downloadUrl": download_url,
                "sizeBytes": file_size,
                "sha256": sha256_hash
            })

        # Save catalog locally
        cat_data["updatedAt"] = datetime.now(timezone.utc).isoformat()
        cat_data["totalGames"] = len(cat_data["games"])
        cat_data["totalVariants"] = sum(len(g.get("variants", [])) for g in cat_data["games"])

        catalog_path.parent.mkdir(parents=True, exist_ok=True)
        with open(catalog_path, "w", encoding="utf-8") as cf:
            json.dump(cat_data, cf, ensure_ascii=False, indent=2)

        # Commit catalog to GitHub
        if progress_cb:
            progress_cb("Фиксация обновлённого каталога catalog.json в GitHub...")

        try:
            content_url = f"https://api.github.com/repos/{repo}/contents/catalog/data/catalog.json"
            c_get_req = urllib.request.Request(content_url, headers=headers)
            file_sha = None
            try:
                with urllib.request.urlopen(c_get_req, timeout=15) as cg_resp:
                    c_info = json.loads(cg_resp.read().decode("utf-8"))
                    file_sha = c_info.get("sha")
            except urllib.error.HTTPError as e:
                if e.code != 404:
                    pass

            raw_cat_bytes = json.dumps(cat_data, ensure_ascii=False, indent=2).encode("utf-8")
            b64_content = base64.b64encode(raw_cat_bytes).decode("ascii")

            put_payload = {
                "message": f"feat(catalog): batch update with {len(results)} backgrounds by {author}",
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
        except Exception as e:
            print(f"[-] Warning: Failed to commit catalog.json in batch: {e}")

        if progress_cb:
            progress_cb(f"Успешно опубликовано {len(results)} видеофонов!")

        return results

    @classmethod
    def fetch_catalog(cls, token: Optional[str] = None, repo: str = DEFAULT_REPO) -> Dict[str, Any]:
        """Fetches the latest catalog either from GitHub or local file fallback."""
        if token:
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "H3H-Background-Studio"
            }
            content_url = f"https://api.github.com/repos/{repo}/contents/catalog/data/catalog.json"
            try:
                req = urllib.request.Request(content_url, headers=headers)
                with urllib.request.urlopen(req, timeout=10) as resp:
                    c_info = json.loads(resp.read().decode("utf-8"))
                    content_b64 = c_info.get("content", "")
                    content_bytes = base64.b64decode(content_b64)
                    return json.loads(content_bytes.decode("utf-8"))
            except Exception:
                pass

        catalog_path = Path(__file__).parent.parent.parent.parent / "catalog" / "data" / "catalog.json"
        if catalog_path.exists():
            try:
                with open(catalog_path, "r", encoding="utf-8") as cf:
                    return json.load(cf)
            except Exception:
                pass

        return {"schemaVersion": 1, "games": []}

    @classmethod
    def delete_published_variants(
        cls,
        items: List[Dict[str, str]],
        token: str,
        repo: str = DEFAULT_REPO,
        release_tag: str = DEFAULT_TAG,
        progress_cb: Optional[callable] = None,
        local_catalog_path: Optional[Path] = None
    ) -> int:
        """
        Deletes multiple video background assets from GitHub Releases and removes
        their entries from catalog.json in a single atomic commit.
        """
        if not items:
            return 0

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "H3H-Background-Studio"
        }

        # 1. Fetch release assets once
        rel_assets = []
        try:
            rel_url = f"https://api.github.com/repos/{repo}/releases/tags/{release_tag}"
            req = urllib.request.Request(rel_url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                rel_data = json.loads(resp.read().decode("utf-8"))
                rel_assets = rel_data.get("assets", [])
        except Exception as e:
            print(f"[-] Release fetch warning during batch delete: {e}")

        # Delete matched assets from GitHub Release
        deleted_assets_count = 0
        total_items = len(items)

        for idx, it in enumerate(items, 1):
            clean_tid = it.get("titleId", "").strip().upper()
            clean_vid = it.get("variantId", "").strip()
            if not clean_tid or not clean_vid:
                continue

            target_asset_names = [
                f"{clean_tid}_{clean_vid}.mp4",
                f"{clean_tid}.mp4"
            ]
            for asset in rel_assets:
                aname = asset.get("name", "")
                if aname in target_asset_names or (clean_tid in aname and clean_vid in aname):
                    if progress_cb:
                        progress_cb(f"[{idx}/{total_items}] Удаление {aname} из GitHub Releases...")
                    del_req = urllib.request.Request(asset["url"], headers=headers, method="DELETE")
                    try:
                        with urllib.request.urlopen(del_req, timeout=15):
                            deleted_assets_count += 1
                    except Exception:
                        pass
                    break

        # 2. Update catalog.json
        if progress_cb:
            progress_cb("Обновление каталога catalog.json...")

        cat_data = cls.fetch_catalog(token, repo)
        items_to_remove = {(it.get("titleId", "").strip().upper(), it.get("variantId", "").strip()) for it in items}

        updated_games = []
        removed_variants_count = 0

        for g in cat_data.get("games", []):
            g_tid = g.get("titleId", "").strip().upper()
            keep_variants = []
            for v in g.get("variants", []):
                v_id = v.get("id", "").strip()
                if (g_tid, v_id) in items_to_remove:
                    removed_variants_count += 1
                else:
                    keep_variants.append(v)
            if keep_variants:
                g["variants"] = keep_variants
                updated_games.append(g)

        if removed_variants_count == 0:
            if progress_cb:
                progress_cb("Выбранные варианты не найдены в каталоге.")
            return 0

        cat_data["games"] = updated_games
        cat_data["updatedAt"] = datetime.now(timezone.utc).isoformat()
        cat_data["totalGames"] = len(updated_games)
        cat_data["totalVariants"] = sum(len(g.get("variants", [])) for g in updated_games)

        # Save local catalog
        target_path = local_catalog_path or (Path(__file__).parent.parent.parent.parent / "catalog" / "data" / "catalog.json")
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with open(target_path, "w", encoding="utf-8") as cf:
                json.dump(cat_data, cf, ensure_ascii=False, indent=2)
        except Exception:
            pass

        # 3. Commit to GitHub in single atomic transaction
        if progress_cb:
            progress_cb(f"Фиксация удаления {removed_variants_count} видеофонов в GitHub...")

        try:
            content_url = f"https://api.github.com/repos/{repo}/contents/catalog/data/catalog.json"
            c_get_req = urllib.request.Request(content_url, headers=headers)
            file_sha = None
            try:
                with urllib.request.urlopen(c_get_req, timeout=15) as cg_resp:
                    c_info = json.loads(cg_resp.read().decode("utf-8"))
                    file_sha = c_info.get("sha")
            except Exception:
                pass

            raw_cat_bytes = json.dumps(cat_data, ensure_ascii=False, indent=2).encode("utf-8")
            b64_content = base64.b64encode(raw_cat_bytes).decode("ascii")

            put_payload = {
                "message": f"feat(catalog): batch delete {removed_variants_count} background(s)",
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
        except Exception as e:
            print(f"[-] Warning: Failed to commit deleted catalog items to GitHub: {e}")

        if progress_cb:
            progress_cb(f"Удаление {removed_variants_count} видеофонов успешно завершено!")

        return removed_variants_count

    @classmethod
    def delete_published_variant(
        cls,
        title_id: str,
        variant_id: str,
        token: str,
        repo: str = DEFAULT_REPO,
        release_tag: str = DEFAULT_TAG,
        progress_cb: Optional[callable] = None
    ) -> bool:
        """
        Deletes a single video background asset from GitHub Releases and removes its entry from catalog.json.
        """
        count = cls.delete_published_variants(
            items=[{"titleId": title_id, "variantId": variant_id}],
            token=token,
            repo=repo,
            release_tag=release_tag,
            progress_cb=progress_cb
        )
        return count > 0

    @classmethod
    def check_repo_permissions(cls, token: Optional[str], repo: str = DEFAULT_REPO) -> Dict[str, Any]:
        """
        Checks whether the provided GitHub token has push/write permissions on the target repository.
        Returns {'has_push': bool, 'role': str, 'login': str, 'error': Optional[str]}.
        """
        if not token:
            return {"has_push": False, "role": "guest", "login": "", "error": "Токен не указан"}

        if not repo or "/" not in repo:
            repo = cls.DEFAULT_REPO

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "H3H-Background-Studio"
        }

        login = ""
        try:
            u_req = urllib.request.Request("https://api.github.com/user", headers=headers)
            with urllib.request.urlopen(u_req, timeout=10) as u_resp:
                u_info = json.loads(u_resp.read().decode("utf-8"))
                login = u_info.get("login", "")
        except Exception:
            pass

        try:
            r_req = urllib.request.Request(f"https://api.github.com/repos/{repo}", headers=headers)
            with urllib.request.urlopen(r_req, timeout=10) as r_resp:
                r_info = json.loads(r_resp.read().decode("utf-8"))
                perms = r_info.get("permissions", {})
                has_push = bool(perms.get("push", False) or perms.get("admin", False))
                role = "admin" if perms.get("admin") else ("write" if perms.get("push") else "read")
                return {"has_push": has_push, "role": role, "login": login, "error": None}
        except urllib.error.HTTPError as he:
            return {"has_push": False, "role": "none", "login": login, "error": f"HTTP {he.code}"}
        except Exception as e:
            return {"has_push": False, "role": "error", "login": login, "error": str(e)}

    @classmethod
    def create_proposal_markdown(cls, proposal_data: Dict[str, Any]) -> str:
        """Formats a proposal issue markdown body containing embedded JSON payload."""
        gtitle = proposal_data.get("gameTitle", "Unknown Game")
        tid = proposal_data.get("titleId", "").upper()
        vname = proposal_data.get("variantName", "Default")
        vid = proposal_data.get("variantId", "default")
        style = proposal_data.get("style", "Gameplay")
        author = proposal_data.get("author", "Anonymous")
        url = proposal_data.get("url", "")
        size_mb = proposal_data.get("sizeBytes", 0) / (1024 * 1024)
        codec = proposal_data.get("codec", "h264")
        w = proposal_data.get("width", 1280)
        h = proposal_data.get("height", 720)
        fps = proposal_data.get("fps", 30)
        audio_str = "Да" if proposal_data.get("hasAudio") else "Нет"
        notes = proposal_data.get("notes", "")

        json_block = json.dumps(proposal_data, ensure_ascii=False, indent=2)

        return (
            f"### 🎬 Заявка на добавление видеофона в H3H-Backgrounds\n\n"
            f"- **Игра:** {gtitle} (`{tid}`)\n"
            f"- **Вариант:** {vname} (`{vid}`)\n"
            f"- **Стиль:** {style}\n"
            f"- **Автор:** {author}\n"
            f"- **Разрешение:** {w}x{h} @{fps}fps | **Кодек:** {codec} | **Звук:** {audio_str}\n"
            f"- **Размер:** {size_mb:.2f} MB\n"
            f"- **Ссылка на скачивание:** [{url}]({url})\n"
            f"- **Примечания:** {notes}\n\n"
            f"```json:h3h-proposal\n{json_block}\n```\n"
        )

    @classmethod
    def submit_catalog_proposal(
        cls,
        proposal_data: Dict[str, Any],
        token: Optional[str] = None,
        repo: str = DEFAULT_REPO
    ) -> Dict[str, Any]:
        """
        Submits a proposal to the GitHub repository as an issue labeled 'catalog-proposal'.
        If token is provided, submits via GitHub API.
        If no token, returns a web URL for manual 1-click opening in browser.
        """
        tid = proposal_data.get("titleId", "").upper()
        gtitle = proposal_data.get("gameTitle", "Switch Game")
        vname = proposal_data.get("variantName", "Default")
        title = f"[Proposal] {tid} - {gtitle} ({vname})"
        body = cls.create_proposal_markdown(proposal_data)

        if token:
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json",
                "Content-Type": "application/json",
                "User-Agent": "H3H-Background-Studio"
            }
            payload = {
                "title": title,
                "body": body,
                "labels": ["catalog-proposal"]
            }
            req = urllib.request.Request(
                f"https://api.github.com/repos/{repo}/issues",
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                created = json.loads(resp.read().decode("utf-8"))
                return {
                    "success": True,
                    "issue_number": created.get("number"),
                    "html_url": created.get("html_url"),
                    "manual": False
                }

        # Fallback: Web URL for opening in browser
        params = urllib.parse.urlencode({
            "title": title,
            "body": body,
            "labels": "catalog-proposal"
        })
        web_url = f"https://github.com/{repo}/issues/new?{params}"
        return {
            "success": True,
            "issue_number": None,
            "html_url": web_url,
            "manual": True
        }

    @classmethod
    def fetch_catalog_proposals(
        cls,
        token: Optional[str] = None,
        repo: str = DEFAULT_REPO
    ) -> List[Dict[str, Any]]:
        """
        Fetches all open issues with the label 'catalog-proposal'.
        Parses their embedded JSON metadata into structured dictionaries.
        """
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "H3H-Background-Studio"
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        url = f"https://api.github.com/repos/{repo}/issues?labels=catalog-proposal&state=open&per_page=100"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            issues = json.loads(resp.read().decode("utf-8"))

        proposals = []
        for iss in issues:
            if "pull_request" in iss:
                continue

            body = iss.get("body", "") or ""
            # Search for ```json:h3h-proposal ... ``` or generic ```json ... ```
            m = re.search(r"```(?:json:h3h-proposal|json)\s*(\{.*?\})\s*```", body, re.DOTALL)
            parsed_data = {}
            if m:
                try:
                    parsed_data = json.loads(m.group(1))
                except Exception:
                    pass

            proposals.append({
                "issue_number": iss["number"],
                "html_url": iss["html_url"],
                "created_at": iss.get("created_at", ""),
                "submitter": iss.get("user", {}).get("login", "Unknown"),
                "title": iss.get("title", ""),
                "data": parsed_data
            })

        return proposals

    @classmethod
    def approve_proposal(
        cls,
        issue_number: int,
        proposal_data: Dict[str, Any],
        token: str,
        repo: str = DEFAULT_REPO,
        progress_cb: Optional[callable] = None,
        local_catalog_path: Optional[Path] = None
    ) -> bool:
        """
        Approves a community proposal by appending the variant to catalog.json,
        committing it to GitHub in a single atomic transaction, and closing the issue.
        """
        if not proposal_data:
            raise ValueError("Данные заявки пусты или повреждены")

        clean_tid = proposal_data.get("titleId", "").strip().upper()
        if not clean_tid or len(clean_tid) != 16:
            raise ValueError(f"Некорректный Title ID: {clean_tid}")

        if progress_cb:
            progress_cb("Загрузка текущего каталога...")

        cat_data = cls.fetch_catalog(token, repo)
        game_entry = None
        for g in cat_data.get("games", []):
            if g.get("titleId", "").upper() == clean_tid:
                game_entry = g
                break

        if not game_entry:
            game_entry = {
                "titleId": clean_tid,
                "title": proposal_data.get("gameTitle", f"Switch Title {clean_tid}"),
                "publisher": "Nintendo Switch",
                "iconUrl": f"https://raw.githubusercontent.com/Langegen/switch-game-collection/main/covers/{clean_tid}.jpg",
                "variants": []
            }
            cat_data.setdefault("games", []).append(game_entry)

        v_name = proposal_data.get("variantName", "Default")
        safe_vid = proposal_data.get("variantId") or re.sub(r"[^a-zA-Z0-9_\-]", "", v_name.lower().replace(" ", "-"))
        if not safe_vid:
            safe_vid = "default"

        new_variant = {
            "id": safe_vid,
            "name": v_name,
            "style": proposal_data.get("style", "Gameplay"),
            "version": proposal_data.get("version", "1.0"),
            "url": proposal_data.get("url", ""),
            "previewUrl": proposal_data.get("previewUrl", ""),
            "sizeBytes": proposal_data.get("sizeBytes", 0),
            "sha256": proposal_data.get("sha256", ""),
            "durationSec": round(float(proposal_data.get("durationSec", 15.0)), 2),
            "author": proposal_data.get("author", "Community"),
            "codec": proposal_data.get("codec", "h264"),
            "width": int(proposal_data.get("width", 1280)),
            "height": int(proposal_data.get("height", 720)),
            "fps": round(float(proposal_data.get("fps", 30.0)), 1),
            "hasAudio": bool(proposal_data.get("hasAudio", False)),
            "notes": proposal_data.get("notes", f"Approved proposal #{issue_number}")
        }

        # Replace or append variant
        existing_idx = -1
        for idx, var in enumerate(game_entry.get("variants", [])):
            if var.get("id") == safe_vid:
                existing_idx = idx
                break

        if existing_idx >= 0:
            game_entry["variants"][existing_idx] = new_variant
        else:
            game_entry.setdefault("variants", []).append(new_variant)

        cat_data["updatedAt"] = datetime.now(timezone.utc).isoformat()
        cat_data["totalGames"] = len(cat_data["games"])
        cat_data["totalVariants"] = sum(len(g.get("variants", [])) for g in cat_data["games"])

        # Save local catalog
        target_path = local_catalog_path or (Path(__file__).parent.parent.parent.parent / "catalog" / "data" / "catalog.json")
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with open(target_path, "w", encoding="utf-8") as cf:
                json.dump(cat_data, cf, ensure_ascii=False, indent=2)
        except Exception:
            pass

        # Commit to GitHub
        if progress_cb:
            progress_cb("Фиксация изменений catalog.json в GitHub...")

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
            "User-Agent": "H3H-Background-Studio"
        }

        content_url = f"https://api.github.com/repos/{repo}/contents/catalog/data/catalog.json"
        c_get_req = urllib.request.Request(content_url, headers=headers)
        file_sha = None
        try:
            with urllib.request.urlopen(c_get_req, timeout=15) as cg_resp:
                c_info = json.loads(cg_resp.read().decode("utf-8"))
                file_sha = c_info.get("sha")
        except Exception:
            pass

        raw_cat_bytes = json.dumps(cat_data, ensure_ascii=False, indent=2).encode("utf-8")
        b64_content = base64.b64encode(raw_cat_bytes).decode("ascii")

        put_payload = {
            "message": f"feat(catalog): approve proposal #{issue_number} - {clean_tid} ({safe_vid})",
            "content": b64_content
        }
        if file_sha:
            put_payload["sha"] = file_sha

        put_req = urllib.request.Request(
            content_url,
            data=json.dumps(put_payload).encode("utf-8"),
            headers=headers,
            method="PUT"
        )
        with urllib.request.urlopen(put_req, timeout=15):
            pass

        # Post approval comment and close issue
        if progress_cb:
            progress_cb("Закрытие заявки на GitHub...")

        try:
            comment_payload = {
                "body": f"✓ **Заявка одобрена!**\nВидеофон успешно добавлен в онлайн-каталог `catalog.json`.\nСпасибо за вклад в сообщество H3H!"
            }
            com_req = urllib.request.Request(
                f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments",
                data=json.dumps(comment_payload).encode("utf-8"),
                headers=headers,
                method="POST"
            )
            with urllib.request.urlopen(com_req, timeout=10):
                pass
        except Exception:
            pass

        try:
            close_payload = {"state": "closed"}
            close_req = urllib.request.Request(
                f"https://api.github.com/repos/{repo}/issues/{issue_number}",
                data=json.dumps(close_payload).encode("utf-8"),
                headers=headers,
                method="PATCH"
            )
            with urllib.request.urlopen(close_req, timeout=10):
                pass
        except Exception:
            pass

        if progress_cb:
            progress_cb("✓ Заявка успешно одобрена и добавлена в каталог!")

        return True

    @classmethod
    def reject_proposal(
        cls,
        issue_number: int,
        reason: str,
        token: str,
        repo: str = DEFAULT_REPO,
        progress_cb: Optional[callable] = None
    ) -> bool:
        """
        Rejects a community proposal by adding a reason comment and closing the issue.
        """
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
            "User-Agent": "H3H-Background-Studio"
        }

        if progress_cb:
            progress_cb(f"Отклонение заявки #{issue_number}...")

        try:
            comment_text = f"❌ **Заявка отклонена модератором.**\n\n**Причина:** {reason.strip() if reason.strip() else 'Не соответствует требованиям качества / формата.'}"
            com_req = urllib.request.Request(
                f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments",
                data=json.dumps({"body": comment_text}).encode("utf-8"),
                headers=headers,
                method="POST"
            )
            with urllib.request.urlopen(com_req, timeout=10):
                pass
        except Exception:
            pass

        try:
            close_req = urllib.request.Request(
                f"https://api.github.com/repos/{repo}/issues/{issue_number}",
                data=json.dumps({"state": "closed"}).encode("utf-8"),
                headers=headers,
                method="PATCH"
            )
            with urllib.request.urlopen(close_req, timeout=10):
                pass
        except Exception as e:
            raise RuntimeError(f"Не удалось закрыть заявку: {e}")

        if progress_cb:
            progress_cb("Заявка отклонена и закрыта.")

        return True

