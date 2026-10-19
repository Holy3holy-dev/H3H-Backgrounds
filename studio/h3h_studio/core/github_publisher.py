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
