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
        if not re.match(r"^0100[0-9A-F]{12}$", clean_tid):
            raise ValueError(f"Invalid Title ID format '{clean_tid}'. Must be 16 hexadecimal chars starting with 0100.")

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
    def scan_archive_or_folder(cls, source_path: Path) -> List[Dict[str, Any]]:
        """
        Scans a .zip archive or directory for MP4 videos, extracts Title IDs from filenames,
        and matches them against the 7,200+ Switch database.
        """
        import zipfile
        import tempfile
        from .online_fetcher import OnlineFetcher

        source = Path(source_path)
        if not source.exists():
            return []

        search_dirs = []
        if source.is_file() and source.suffix.lower() == ".zip":
            extract_dir = Path(tempfile.gettempdir()) / f"h3h_batch_{source.stem}"
            extract_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(source, "r") as zf:
                zf.extractall(extract_dir)
            search_dirs.append(extract_dir)
        elif source.is_dir():
            search_dirs.append(source)
        else:
            return []

        mp4_files = []
        for d in search_dirs:
            for p in d.rglob("*"):
                if p.is_file() and p.suffix.lower() == ".mp4":
                    mp4_files.append(p)

        db = OnlineFetcher._load_db()
        db_by_tid = {item["titleId"].upper(): item for item in db if item.get("titleId")}

        results = []
        for vid in sorted(mp4_files, key=lambda x: x.name):
            fname = vid.name
            m = re.search(r"0100[0-9A-Fa-f]{12}", fname)
            tid = m.group(0).upper() if m else ""

            variant_name = "Default"
            base_no_ext = vid.stem
            if tid:
                rem = base_no_ext.replace(m.group(0), "").strip(" _-[]()")
                if rem:
                    variant_name = rem.replace("_", " ").title()

            db_entry = db_by_tid.get(tid, {}) if tid else {}
            game_title = db_entry.get("title", "")
            if not game_title:
                game_title = f"Switch Title ({tid})" if tid else vid.stem

            comp = ComplianceValidator.validate_mp4(vid)

            results.append({
                "path": str(vid),
                "filename": vid.name,
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
        Deletes a video background asset from GitHub Releases and removes its entry from catalog.json.
        """
        clean_tid = title_id.strip().upper()
        clean_vid = variant_id.strip()

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "H3H-Background-Studio"
        }

        if progress_cb:
            progress_cb("Поиск ассета в релизе GitHub...")

        # 1. Look up release and delete asset
        try:
            rel_url = f"https://api.github.com/repos/{repo}/releases/tags/{release_tag}"
            req = urllib.request.Request(rel_url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                rel_data = json.loads(resp.read().decode("utf-8"))

            target_asset_names = [
                f"{clean_tid}_{clean_vid}.mp4",
                f"{clean_tid}.mp4"
            ]
            for asset in rel_data.get("assets", []):
                aname = asset.get("name", "")
                if aname in target_asset_names or (clean_tid in aname and clean_vid in aname):
                    if progress_cb:
                        progress_cb(f"Удаление ассета {aname} из GitHub Releases...")
                    del_req = urllib.request.Request(asset["url"], headers=headers, method="DELETE")
                    try:
                        with urllib.request.urlopen(del_req, timeout=15):
                            pass
                    except Exception:
                        pass
                    break
        except Exception as e:
            print(f"[-] Asset deletion warning: {e}")

        # 2. Update catalog.json
        if progress_cb:
            progress_cb("Обновление каталога catalog.json...")

        cat_data = cls.fetch_catalog(token, repo)
        updated_games = []
        removed = False

        for g in cat_data.get("games", []):
            if g.get("titleId", "").upper() == clean_tid:
                new_variants = [v for v in g.get("variants", []) if v.get("id") != clean_vid]
                if len(new_variants) != len(g.get("variants", [])):
                    removed = True
                if new_variants:
                    g["variants"] = new_variants
                    updated_games.append(g)
            else:
                updated_games.append(g)

        if not removed:
            if progress_cb:
                progress_cb("Вариант не найден в каталоге.")
            return False

        cat_data["games"] = updated_games
        cat_data["updatedAt"] = datetime.now(timezone.utc).isoformat()
        cat_data["totalGames"] = len(updated_games)
        cat_data["totalVariants"] = sum(len(g.get("variants", [])) for g in updated_games)

        # Save local catalog
        catalog_path = Path(__file__).parent.parent.parent.parent / "catalog" / "data" / "catalog.json"
        try:
            catalog_path.parent.mkdir(parents=True, exist_ok=True)
            with open(catalog_path, "w", encoding="utf-8") as cf:
                json.dump(cat_data, cf, ensure_ascii=False, indent=2)
        except Exception:
            pass

        # Commit to GitHub
        if progress_cb:
            progress_cb("Фиксация изменений catalog.json в GitHub...")

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
                "message": f"feat(catalog): delete background {clean_tid} ({clean_vid})",
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
            print(f"[-] Warning: Failed to commit deleted catalog item to GitHub: {e}")

        if progress_cb:
            progress_cb("Удаление успешно завершено!")
        return True
