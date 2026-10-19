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
from typing import Dict, Any, Optional, Tuple

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

    @classmethod
    def get_stored_credentials(cls) -> Tuple[Optional[str], Optional[str]]:
        """
        Attempts to read GitHub credentials from Windows Credential Manager or environment.
        """
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            return token, os.environ.get("GITHUB_USER", "Holy3holy-dev")

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

            # 1. Search Title ID in filename (prefer 0100..., but accept any 16-hex chars)
            m = re.search(r"\b(0100[0-9A-Fa-f]{12})\b", fname, re.IGNORECASE)
            if not m:
                m = re.search(r"\b([0-9A-Fa-f]{16})\b", fname)
            # 2. If not found in filename, search in relative path (folder names like recordings/covers/...)
            if not m:
                m = re.search(r"\b(0100[0-9A-Fa-f]{12})\b", rel_str, re.IGNORECASE)
            if not m:
                m = re.search(r"\b([0-9A-Fa-f]{16})\b", rel_str)

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
