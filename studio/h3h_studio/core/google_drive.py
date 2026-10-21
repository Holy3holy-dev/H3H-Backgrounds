"""
Google Drive integration and catalog publisher for H3H Studio.
Enables linking video backgrounds hosted on Google Drive (up to 5TB)
directly into catalog/data/catalog.json with automatic direct download URLs.
"""

import re
import json
import base64
import urllib.request
import urllib.parse
import urllib.error
import time
import socket
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timezone

from .analyzer import VideoAnalyzer
from .compliance import ComplianceValidator
from .github_publisher import GitHubPublisher
from .online_fetcher import OnlineFetcher


class GoogleDriveHelper:
    """
    Utilities for extracting Google Drive file IDs, converting sharing links to
    direct download streams, and registering Google Drive-hosted videos into the catalog.
    """

    FILE_ID_PATTERNS = [
        r"drive\.google\.com/file/d/([a-zA-Z0-9_-]+)",
        r"drive\.google\.com/open\?id=([a-zA-Z0-9_-]+)",
        r"drive\.google\.com/uc\?(?:.*&)?id=([a-zA-Z0-9_-]+)",
        r"drive\.usercontent\.google\.com/download\?(?:.*&)?id=([a-zA-Z0-9_-]+)",
        r"lh3\.googleusercontent\.com/d/([a-zA-Z0-9_-]+)",
        r"docs\.google\.com/uc\?(?:.*&)?id=([a-zA-Z0-9_-]+)",
        r"^([a-zA-Z0-9_-]{25,50})$",  # Raw Google Drive ID
    ]

    FOLDER_ID_PATTERNS = [
        r"drive\.google\.com/(?:drive/)?(?:u/\d+/)?folders/([a-zA-Z0-9_-]+)",
        r"drive\.google\.com/open\?id=([a-zA-Z0-9_-]+)",
        r"^([a-zA-Z0-9_-]{19,64})$",
    ]

    CONFIG_FILE = Path.home() / ".h3h_google_drive.json"

    @classmethod
    def extract_folder_id(cls, url_or_id: str) -> Optional[str]:
        """
        Extracts Google Drive folder ID from a URL or raw ID string.
        """
        if not url_or_id:
            return None
        cleaned = url_or_id.strip()
        for pattern in cls.FOLDER_ID_PATTERNS:
            match = re.search(pattern, cleaned)
            if match:
                return match.group(1)
        return None

    @classmethod
    def refresh_access_token(cls, refresh_token: str) -> Optional[str]:
        """
        Refreshes access token via OAuth Playground refresh endpoint.
        Returns the new 'ya29...' access token or None.
        """
        if not refresh_token or not refresh_token.strip():
            return None
        url = "https://developers.google.com/oauthplayground/refreshAccessToken"
        payload = {
            "token_uri": "https://oauth2.googleapis.com/token",
            "refresh_token": refresh_token.strip()
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0"
            }
        )
        for attempt in range(1, 5):
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    msg_b64 = data.get("Response", {}).get("message-body", "")
                    if msg_b64:
                        body_str = base64.b64decode(msg_b64).decode("utf-8")
                        token_data = json.loads(body_str)
                        new_tok = token_data.get("access_token")
                        if new_tok and new_tok.startswith("ya29."):
                            return new_tok
            except Exception as e:
                print(f"[-] Auto-refresh attempt {attempt}/4 error: {e}")
                if attempt < 4:
                    time.sleep(2 * attempt)
        return None

    @classmethod
    def get_stored_config(cls) -> Dict[str, Any]:
        """
        Loads persisted Google Drive configuration (token, default folder, author).
        """
        cfg = {}
        if cls.CONFIG_FILE.exists():
            try:
                with open(cls.CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            except Exception as e:
                print(f"[-] Warning reading {cls.CONFIG_FILE}: {e}")
        
        # Override / inject from environment variables (for Docker / Render cloud deployment)
        import os
        if os.getenv("GDRIVE_REFRESH_TOKEN"):
            cfg["refresh_token"] = os.getenv("GDRIVE_REFRESH_TOKEN").strip()
        if os.getenv("GDRIVE_TOKEN"):
            cfg["token"] = os.getenv("GDRIVE_TOKEN").strip()
        if os.getenv("GDRIVE_FOLDER_ID"):
            cfg["folder_id"] = os.getenv("GDRIVE_FOLDER_ID").strip()
            cfg["project_folder_id"] = os.getenv("GDRIVE_FOLDER_ID").strip()
        return cfg

    @classmethod
    def save_stored_config(cls, data: Dict[str, Any]) -> bool:
        """
        Persists Google Drive configuration to ~/.h3h_google_drive.json.
        """
        try:
            existing = cls.get_stored_config()
            existing.update(data)
            with open(cls.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"[-] Warning saving {cls.CONFIG_FILE}: {e}")
            return False

    @classmethod
    def extract_file_id(cls, url_or_id: str) -> Optional[str]:
        """
        Extracts Google Drive file ID from a URL or raw ID string.
        """
        if not url_or_id:
            return None
        cleaned = url_or_id.strip()
        for pattern in cls.FILE_ID_PATTERNS:
            match = re.search(pattern, cleaned)
            if match:
                return match.group(1)
        return None

    @classmethod
    def to_direct_download_url(cls, url_or_id: str) -> Optional[str]:
        """
        Converts any Google Drive file URL into a direct download URL compatible
        with libcurl / Switch Downloader.
        """
        file_id = cls.extract_file_id(url_or_id)
        if not file_id:
            return None
        return f"https://drive.google.com/uc?export=download&id={file_id}"

    @classmethod
    def to_preview_url(cls, url_or_id: str) -> Optional[str]:
        """
        Generates an instant CDN thumbnail preview URL from Google Drive.
        """
        file_id = cls.extract_file_id(url_or_id)
        if not file_id:
            return None
        return f"https://drive.google.com/thumbnail?id={file_id}&sz=w640"

    @classmethod
    def parse_batch_links(cls, text: str) -> List[Dict[str, str]]:
        """
        Parses multi-line text with Title ID and Google Drive links.
        Supported formats per line:
          - 01005CA01580E000 https://drive.google.com/file/d/xxxx/view
          - 01005CA01580E000, https://drive.google.com/file/d/xxxx/view
          - 01005CA01580E000 = https://drive.google.com/file/d/xxxx/view
          - https://drive.google.com/file/d/xxxx/view (if containing Title ID or standalone)
        """
        results = []
        tid_regex = re.compile(r"(?<![0-9A-Za-z])([0-9A-Fa-f]{16})(?![0-9A-Za-z])", re.IGNORECASE)

        for line in text.strip().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            tid_match = tid_regex.search(line)
            title_id = tid_match.group(1).upper() if tid_match else ""

            # Find Google Drive URL or ID
            drive_id = None
            for part in re.split(r"[\s,;=\|\t]+", line):
                extracted = cls.extract_file_id(part)
                if extracted and extracted != title_id:
                    drive_id = extracted
                    break

            if drive_id:
                results.append({
                    "titleId": title_id,
                    "driveId": drive_id,
                    "directUrl": f"https://drive.google.com/uc?export=download&id={drive_id}",
                    "previewUrl": f"https://drive.google.com/thumbnail?id={drive_id}&sz=w640",
                    "rawLine": line
                })

        return results

    @classmethod
    def register_drive_video(
        cls,
        catalog_path: Path,
        video_path: Path,
        drive_url_or_id: str,
        title_id: str,
        game_title: str = "",
        variant_name: str = "Standard",
        style: str = "Animated Art",
        author: str = "Anonymous",
        description: str = "",
        progress_cb: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Validates local video, extracts metadata, computes SHA-256,
        and adds/updates the variant with Google Drive download URL in catalog.json.
        """
        drive_id = cls.extract_file_id(drive_url_or_id)
        if not drive_id:
            raise ValueError(f"Не удалось распознать Google Drive ID из ссылки: {drive_url_or_id}")

        direct_url = cls.to_direct_download_url(drive_id)
        preview_url = cls.to_preview_url(drive_id)

        clean_tid = title_id.strip().upper()
        if not re.match(r"^[0-9A-Fa-f]{16}$", clean_tid):
            raise ValueError(f"Некорректный Title ID: '{clean_tid}' (должен содержать 16 hex-символов)")

        vpath = Path(video_path)
        if not vpath.exists():
            raise FileNotFoundError(f"Файл видео не найден: {vpath}")

        if progress_cb:
            progress_cb("Проверка соответствия стандартам 4IFIR...")

        comp = ComplianceValidator.validate(vpath)
        if not comp.is_valid:
            err_details = "; ".join(comp.errors)
            raise ValueError(f"Видео не соответствует требованиям 4IFIR: {err_details}")

        if progress_cb:
            progress_cb("Вычисление контрольной суммы SHA-256...")

        sha256_hash = GitHubPublisher.compute_sha256(vpath)
        file_size = vpath.stat().st_size

        if not game_title:
            matched_title = OnlineFetcher.get_title_by_id(clean_tid)
            game_title = matched_title if matched_title else f"Game {clean_tid}"

        catalog_path = Path(catalog_path)
        cat_data = {"schemaVersion": 1, "updatedAt": "", "games": []}
        if catalog_path.exists():
            try:
                with open(catalog_path, "r", encoding="utf-8") as cf:
                    cat_data = json.load(cf)
            except Exception as e:
                print(f"[-] Catalog load warning: {e}")

        # Find or create game entry
        game_entry = None
        for g in cat_data.get("games", []):
            if g.get("titleId", "").upper() == clean_tid:
                game_entry = g
                break

        if not game_entry:
            game_entry = {
                "titleId": clean_tid,
                "title": game_title,
                "publisher": "Unknown",
                "variants": []
            }
            cat_data.setdefault("games", []).append(game_entry)
        else:
            if game_title and (game_entry.get("title", "").startswith("Game ") or not game_entry.get("title")):
                game_entry["title"] = game_title

        safe_variant_id = re.sub(r"[^a-z0-9_-]", "-", variant_name.lower()).strip("-")
        if len(safe_variant_id) < 3:
            safe_variant_id = f"var-{safe_variant_id}"

        new_variant = {
            "id": safe_variant_id,
            "name": variant_name or "Standard",
            "style": style if style in ["Cinematic", "Gameplay", "Animated Art", "Minimal", "Dark", "Retro", "Music"] else "Animated Art",
            "version": "1.0",
            "url": direct_url,
            "previewUrl": preview_url,
            "sizeBytes": file_size,
            "sha256": sha256_hash,
            "durationSec": round(comp.duration_sec, 2),
            "author": author or "Anonymous",
            "codec": comp.codec or "h264",
            "width": comp.width,
            "height": comp.height,
            "fps": round(comp.fps, 1),
            "hasAudio": comp.has_audio,
            "notes": description or f"Google Drive Hosted (4IFIR: {comp.width}x{comp.height} @{round(comp.fps)}fps)"
        }

        # Update or append variant
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

        catalog_path.parent.mkdir(parents=True, exist_ok=True)
        with open(catalog_path, "w", encoding="utf-8") as cf:
            json.dump(cat_data, cf, ensure_ascii=False, indent=2)

        if progress_cb:
            progress_cb("Запись в catalog.json успешно сохранена!")

        return {
            "success": True,
            "titleId": clean_tid,
            "variantId": safe_variant_id,
            "directUrl": direct_url,
            "previewUrl": preview_url,
            "sha256": sha256_hash,
            "sizeBytes": file_size
        }

    @classmethod
    def sync_catalog_to_github(
        cls,
        catalog_path: Path,
        token: str,
        repo: str = "Holy3holy-dev/H3H-Backgrounds",
        progress_cb: Optional[callable] = None
    ) -> bool:
        """
        Commits the updated catalog.json containing Google Drive links to the GitHub repository.
        """
        catalog_path = Path(catalog_path)
        if not catalog_path.exists():
            raise FileNotFoundError(f"Каталог не найден: {catalog_path}")

        with open(catalog_path, "r", encoding="utf-8") as cf:
            cat_data = json.load(cf)

        if progress_cb:
            progress_cb("Синхронизация catalog.json с GitHub...")

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "H3H-Studio"
        }

        content_url = f"https://api.github.com/repos/{repo}/contents/catalog/data/catalog.json"
        c_get_req = urllib.request.Request(content_url, headers=headers)
        file_sha = None
        try:
            with urllib.request.urlopen(c_get_req, timeout=15) as cg_resp:
                c_info = json.loads(cg_resp.read().decode("utf-8"))
                file_sha = c_info.get("sha")
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise e

        raw_cat_bytes = json.dumps(cat_data, ensure_ascii=False, indent=2).encode("utf-8")
        b64_content = base64.b64encode(raw_cat_bytes).decode("ascii")

        put_payload = {
            "message": "feat(catalog): sync Google Drive video backgrounds catalog",
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

        if progress_cb:
            progress_cb("Каталог успешно синхронизирован с GitHub!")

        return True

    @classmethod
    def sync_file_to_github(
        cls,
        file_path: Path,
        repo_path: str,
        token: str,
        repo: str = "Holy3holy-dev/H3H-Backgrounds",
        commit_message: str = "chore: sync file to repository",
        progress_cb: None = None
    ) -> bool:
        """
        Commits any local file (such as harvest log or catalog) directly to GitHub repository via REST API.
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Файл не найден: {file_path}")

        raw_bytes = file_path.read_bytes()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "H3H-Studio"
        }

        content_url = f"https://api.github.com/repos/{repo}/contents/{repo_path.lstrip('/')}"
        c_get_req = urllib.request.Request(content_url, headers=headers)
        file_sha = None
        try:
            with urllib.request.urlopen(c_get_req, timeout=15) as cg_resp:
                c_info = json.loads(cg_resp.read().decode("utf-8"))
                file_sha = c_info.get("sha")
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise e

        b64_content = base64.b64encode(raw_bytes).decode("ascii")
        put_payload = {
            "message": commit_message,
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

        if progress_cb:
            progress_cb(f"Файл {repo_path} успешно синхронизирован с GitHub!")

        return True


class GoogleDriveClient:
    """
    Client for interacting with Google Drive v3 REST API.
    Supports token validation, folder listing, folder creation,
    permission management, resumable chunked video uploads,
    and automatic catalog registration.
    """
    CHUNK_SIZE = 5 * 1024 * 1024  # 5MB chunk for resumable uploads

    @classmethod
    def test_connection(cls, token: str) -> Dict[str, Any]:
        """
        Queries Google Drive about endpoint for user identity and storage quota.
        """
        if not token or not token.strip():
            raise ValueError("Токен авторизации Google Drive не указан")

        url = "https://www.googleapis.com/drive/v3/about?fields=user(displayName,emailAddress),storageQuota(limit,usage,usageInDrive)"
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {token.strip()}",
                "Accept": "application/json"
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                user_data = data.get("user", {})
                quota_data = data.get("storageQuota", {})
                limit = int(quota_data.get("limit", 0))
                usage = int(quota_data.get("usage", 0))
                limit_gb = limit / (1024 ** 3)
                usage_gb = usage / (1024 ** 3)
                free_gb = max(0.0, limit_gb - usage_gb) if limit > 0 else 0.0
                quota_str = f"Занято {usage_gb:.1f} ГБ из {limit_gb:.1f} ГБ (свободно {free_gb:.1f} ГБ)" if limit > 0 else f"Занято {usage_gb:.1f} ГБ"
                return {
                    "success": True,
                    "ok": True,
                    "user": user_data.get("displayName", "Google User"),
                    "displayName": user_data.get("displayName", "Google User"),
                    "email": user_data.get("emailAddress", ""),
                    "emailAddress": user_data.get("emailAddress", ""),
                    "limit": limit,
                    "limit_gb": limit_gb,
                    "usage": usage,
                    "usage_gb": usage_gb,
                    "usageInDrive": int(quota_data.get("usageInDrive", 0)),
                    "free": max(0, limit - usage) if limit > 0 else 0,
                    "free_gb": free_gb,
                    "quota_str": quota_str
                }
        except urllib.error.HTTPError as he:
            return {"success": False, "ok": False, "error": f"HTTP Error {he.code}: {he.reason}"}
        except Exception as e:
            return {"success": False, "ok": False, "error": str(e)}

    @classmethod
    def list_folder_files(cls, folder_id: str, token: str) -> List[Dict[str, Any]]:
        """
        Lists files inside a Google Drive folder.
        """
        if not token or not token.strip():
            raise ValueError("Токен авторизации Google Drive не указан")
        clean_fid = GoogleDriveHelper.extract_folder_id(folder_id) or folder_id.strip()
        if not clean_fid:
            raise ValueError("Некорректный ID папки Google Drive")

        files: List[Dict[str, Any]] = []
        page_token = None
        while True:
            params = {
                "q": f"'{clean_fid}' in parents and trashed = false",
                "fields": "nextPageToken, files(id, name, mimeType, size, webContentLink, webViewLink, createdTime)",
                "pageSize": "1000"
            }
            if page_token:
                params["pageToken"] = page_token

            query = urllib.parse.urlencode(params)
            url = f"https://www.googleapis.com/drive/v3/files?{query}"
            req = urllib.request.Request(
                url,
                headers={
                    "Authorization": f"Bearer {token.strip()}",
                    "Accept": "application/json"
                }
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for f in data.get("files", []):
                    if "size" in f:
                        try:
                            f["size"] = int(f["size"])
                        except (ValueError, TypeError):
                            f["size"] = 0
                    files.append(f)
                page_token = data.get("nextPageToken")
                if not page_token:
                    break
        return files

    @classmethod
    def create_folder(cls, folder_name: str, parent_id: Optional[str], token: str) -> Dict[str, Any]:
        """
        Creates a new folder on Google Drive.
        """
        if not token or not token.strip():
            raise ValueError("Токен авторизации Google Drive не указан")
        if not folder_name or not folder_name.strip():
            raise ValueError("Имя папки не может быть пустым")

        url = "https://www.googleapis.com/drive/v3/files"
        meta: Dict[str, Any] = {
            "name": folder_name.strip(),
            "mimeType": "application/vnd.google-apps.folder"
        }
        if parent_id:
            clean_pid = GoogleDriveHelper.extract_folder_id(parent_id) or parent_id.strip()
            if clean_pid:
                meta["parents"] = [clean_pid]

        data_bytes = json.dumps(meta).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data_bytes,
            headers={
                "Authorization": f"Bearer {token.strip()}",
                "Content-Type": "application/json; charset=UTF-8"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))

    @classmethod
    def make_public(cls, file_id: str, token: str) -> bool:
        """
        Grants 'anyone:reader' permission to a Google Drive file or folder so it
        can be downloaded directly by Switch CFW without authorization headers.
        """
        if not token or not token.strip():
            raise ValueError("Токен авторизации Google Drive не указан")
        clean_fid = GoogleDriveHelper.extract_file_id(file_id) or GoogleDriveHelper.extract_folder_id(file_id) or file_id.strip()
        if not clean_fid:
            raise ValueError("Некорректный ID файла Google Drive")

        url = f"https://www.googleapis.com/drive/v3/files/{clean_fid}/permissions"
        payload = {"role": "reader", "type": "anyone"}
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data_bytes,
            headers={
                "Authorization": f"Bearer {token.strip()}",
                "Content-Type": "application/json; charset=UTF-8"
            },
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.status in (200, 201)
        except urllib.error.HTTPError as e:
            if e.code in (200, 201):
                return True
            raise e

    @classmethod
    def upload_file(
        cls,
        file_path: Path,
        folder_id: Optional[str],
        token: str,
        progress_cb: Optional[callable] = None,
        max_retries_per_chunk: int = 5
    ) -> Dict[str, Any]:
        """
        Resumable chunked upload of a local video file to Google Drive.
        Features automatic retry backoff, socket timeout recovery, and
        resumable state query (Google Drive v3 protocol).
        Automatically sets public read permissions upon completion.
        """
        if not token or not token.strip():
            raise ValueError("Токен авторизации Google Drive не указан")
        p = Path(file_path)
        if not p.exists() or not p.is_file():
            raise FileNotFoundError(f"Файл для загрузки не найден: {p}")

        total_bytes = p.stat().st_size
        clean_parent = None
        if folder_id:
            clean_parent = GoogleDriveHelper.extract_folder_id(folder_id) or folder_id.strip()

        # Step 1: Initiate resumable upload session (with retry)
        init_url = "https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable"
        metadata: Dict[str, Any] = {"name": p.name}
        if clean_parent:
            metadata["parents"] = [clean_parent]

        init_data = json.dumps(metadata).encode("utf-8")
        init_req = urllib.request.Request(
            init_url,
            data=init_data,
            headers={
                "Authorization": f"Bearer {token.strip()}",
                "Content-Type": "application/json; charset=UTF-8",
                "X-Upload-Content-Type": "video/mp4",
                "X-Upload-Content-Length": str(total_bytes)
            },
            method="POST"
        )

        session_url = None
        for init_attempt in range(1, 4):
            try:
                with urllib.request.urlopen(init_req, timeout=45) as init_resp:
                    session_url = init_resp.headers.get("Location")
                    if session_url:
                        break
            except Exception as e:
                if init_attempt == 3:
                    raise RuntimeError(f"Google Drive API не удалось инициализировать сессию загрузки: {e}")
                time.sleep(1.5 * init_attempt)

        if not session_url:
            raise RuntimeError("Google Drive API не вернул Location для сессии загрузки")

        # Step 2: Upload chunks with resumable recovery & exponential backoff
        uploaded_bytes = 0
        file_info: Dict[str, Any] = {}

        with open(p, "rb") as f:
            while uploaded_bytes < total_bytes:
                f.seek(uploaded_bytes)
                chunk = f.read(cls.CHUNK_SIZE)
                if not chunk:
                    break
                chunk_len = len(chunk)
                start_byte = uploaded_bytes
                end_byte = uploaded_bytes + chunk_len - 1

                chunk_success = False
                last_chunk_err = None

                for attempt in range(1, max_retries_per_chunk + 1):
                    chunk_req = urllib.request.Request(
                        session_url,
                        data=chunk,
                        headers={
                            "Content-Length": str(chunk_len),
                            "Content-Range": f"bytes {start_byte}-{end_byte}/{total_bytes}",
                            "Content-Type": "video/mp4"
                        },
                        method="PUT"
                    )

                    try:
                        # 120s timeout per 5MB chunk to avoid premature socket timeout on slower links
                        with urllib.request.urlopen(chunk_req, timeout=120) as chunk_resp:
                            uploaded_bytes += chunk_len
                            pct = (uploaded_bytes / total_bytes) * 100 if total_bytes > 0 else 100.0
                            if progress_cb:
                                progress_cb(f"Загрузка {p.name}: {pct:.1f}% ({uploaded_bytes // (1024*1024)}/{total_bytes // (1024*1024)} MB)")
                            if chunk_resp.status in (200, 201):
                                resp_body = chunk_resp.read().decode("utf-8")
                                if resp_body:
                                    file_info = json.loads(resp_body)
                                chunk_success = True
                                break
                    except urllib.error.HTTPError as he:
                        if he.code == 308:
                            # 308 Resume Incomplete is expected for non-final chunks
                            uploaded_bytes += chunk_len
                            pct = (uploaded_bytes / total_bytes) * 100 if total_bytes > 0 else 100.0
                            if progress_cb:
                                progress_cb(f"Загрузка {p.name}: {pct:.1f}% ({uploaded_bytes // (1024*1024)}/{total_bytes // (1024*1024)} MB)")
                            chunk_success = True
                            break
                        elif he.code in (500, 502, 503, 504, 429):
                            last_chunk_err = he
                            wait_s = min(25, 2 ** attempt)
                            if progress_cb:
                                progress_cb(f"Сервер Google временно занят (HTTP {he.code}), повтор {attempt}/{max_retries_per_chunk} через {wait_s}с...")
                            time.sleep(wait_s)
                        else:
                            raise he
                    except (urllib.error.URLError, TimeoutError, socket.timeout, OSError, Exception) as net_err:
                        last_chunk_err = net_err
                        wait_s = min(25, 2 ** attempt)
                        if progress_cb:
                            progress_cb(f"Пауза сети/таймаут ({net_err}), проверка статуса и повтор {attempt}/{max_retries_per_chunk} через {wait_s}с...")
                        time.sleep(wait_s)

                        # Query upload status to check where Google actually got up to (Resumable protocol)
                        try:
                            q_req = urllib.request.Request(
                                session_url,
                                headers={"Content-Range": f"bytes */{total_bytes}"},
                                method="PUT"
                            )
                            with urllib.request.urlopen(q_req, timeout=30) as q_resp:
                                if q_resp.status in (200, 201):
                                    resp_body = q_resp.read().decode("utf-8")
                                    if resp_body:
                                        file_info = json.loads(resp_body)
                                    uploaded_bytes = total_bytes
                                    chunk_success = True
                                    break
                        except urllib.error.HTTPError as q_he:
                            if q_he.code == 308:
                                rng = q_he.headers.get("Range")
                                if rng and rng.startswith("bytes=0-"):
                                    server_last = int(rng.split("-")[1])
                                    if server_last >= end_byte:
                                        # Chunk was successfully received despite socket read timeout!
                                        uploaded_bytes = server_last + 1
                                        chunk_success = True
                                        break
                                    elif server_last >= start_byte:
                                        # Partially received, resume from server_last + 1
                                        uploaded_bytes = server_last + 1
                                        chunk_success = True
                                        break
                        except Exception:
                            pass

                if not chunk_success and uploaded_bytes < total_bytes:
                    raise RuntimeError(f"Не удалось передать фрагмент видеофайла {p.name}: {last_chunk_err}")

        file_id = file_info.get("id")
        if not file_id:
            raise RuntimeError(f"Не удалось получить ID созданного файла после загрузки: {file_info}")

        # Step 3: Make public
        try:
            cls.make_public(file_id, token)
        except Exception as perm_err:
            print(f"[-] Warning: could not set public permission on {file_id}: {perm_err}")

        return {
            "id": file_id,
            "name": file_info.get("name", p.name),
            "size": total_bytes,
            "directUrl": GoogleDriveHelper.to_direct_download_url(file_id),
            "previewUrl": GoogleDriveHelper.to_preview_url(file_id)
        }

    @classmethod
    def upload_batch_archive(
        cls,
        source_path: Path,
        folder_id: str,
        token: str,
        author: str = "Anonymous",
        catalog_path: Optional[Path] = None,
        progress_cb: Optional[callable] = None,
        selected_items: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Scans an archive/folder, uploads each selected video to Google Drive,
        and registers each into the catalog.
        Skips re-uploading files already present on Google Drive to save bandwidth.
        """
        if selected_items is None:
            selected_items = GitHubPublisher.scan_archive_or_folder(source_path, progress_cb=progress_cb)

        if not selected_items:
            return []

        if catalog_path is None:
            catalog_path = Path("catalog/data/catalog.json")
        else:
            catalog_path = Path(catalog_path)

        # Pre-scan remote folder to avoid re-uploading existing files
        remote_files: Dict[str, Dict[str, Any]] = {}
        if folder_id:
            try:
                for rf in cls.list_folder_files(folder_id, token):
                    rf_name = rf.get("name", "")
                    if rf_name:
                        remote_files[rf_name] = rf
            except Exception as e:
                print(f"[-] Note: could not pre-list remote folder files: {e}")

        results = []
        total = len(selected_items)
        for idx, item in enumerate(selected_items, 1):
            fpath_raw = item.get("path") or item.get("video_path") or item.get("filePath")
            fpath = Path(fpath_raw) if fpath_raw else None
            if not fpath or not fpath.exists():
                continue

            tid = item.get("titleId", "").strip().upper()
            title = item.get("gameTitle", "") or (OnlineFetcher.get_title_by_id(tid) if tid else fpath.stem)
            fname = item.get("filename", fpath.name)

            # Check if file is already present on Google Drive
            existing_remote = remote_files.get(fname) or remote_files.get(fpath.name)
            if existing_remote and existing_remote.get("id"):
                existing_id = existing_remote["id"]
                if progress_cb:
                    progress_cb(f"[{idx}/{total}] Файл уже на Google Диске (пропуск загрузки): {fname}...")
                upload_res = {
                    "id": existing_id,
                    "name": existing_remote.get("name", fname),
                    "size": existing_remote.get("size", fpath.stat().st_size),
                    "directUrl": GoogleDriveHelper.to_direct_download_url(existing_id),
                    "previewUrl": GoogleDriveHelper.to_preview_url(existing_id)
                }
                try:
                    cls.make_public(existing_id, token)
                except Exception:
                    pass
            else:
                if progress_cb:
                    progress_cb(f"[{idx}/{total}] Загрузка на Google Диск: {fname}...")

                upload_res = None
                for file_attempt in range(1, 3):
                    try:
                        upload_res = cls.upload_file(
                            file_path=fpath,
                            folder_id=folder_id,
                            token=token,
                            progress_cb=progress_cb
                        )
                        break
                    except Exception as upload_err:
                        if file_attempt < 2:
                            if progress_cb:
                                progress_cb(f"Повтор загрузки {fname} после паузы...")
                            time.sleep(3)
                        else:
                            raise upload_err

                remote_files[upload_res["name"]] = {"id": upload_res["id"], "name": upload_res["name"], "size": upload_res["size"]}

            # Register in catalog
            reg_res = GoogleDriveHelper.register_drive_video(
                catalog_path=catalog_path,
                video_path=fpath,
                drive_url_or_id=upload_res["id"],
                title_id=tid,
                game_title=title,
                variant_name="Standard",
                author=author,
                progress_cb=progress_cb
            )
            results.append({**item, **upload_res, **reg_res})

        return results

    @classmethod
    def scan_and_register_remote_folder(
        cls,
        folder_id: str,
        token: str,
        author: str = "Anonymous",
        catalog_path: Optional[Path] = None,
        progress_cb: Optional[callable] = None
    ) -> List[Dict[str, Any]]:
        """
        Scans remote files in Google Drive folder (uploaded by user via browser),
        extracts Title IDs from filenames, ensures files are public, and
        registers them into the catalog.
        """
        if catalog_path is None:
            catalog_path = Path("catalog/data/catalog.json")
        else:
            catalog_path = Path(catalog_path)

        if progress_cb:
            progress_cb("Запрос списка файлов из папки Google Диска...")

        files = cls.list_folder_files(folder_id, token)
        tid_regex = re.compile(r"(?<![0-9A-Za-z])([0-9A-Fa-f]{16})(?![0-9A-Za-z])", re.IGNORECASE)

        # Filter video files or files containing Title ID
        video_candidates = []
        for f in files:
            name = f.get("name", "")
            mime = f.get("mimeType", "")
            is_video = mime.startswith("video/") or name.lower().endswith((".mp4", ".mkv", ".webm", ".mov", ".avi"))
            if is_video or tid_regex.search(name):
                video_candidates.append(f)

        if not video_candidates:
            if progress_cb:
                progress_cb("В папке Google Диска не найдено подходящих видеофайлов.")
            return []

        # Load existing catalog
        cat_data = {"schemaVersion": 1, "updatedAt": "", "games": []}
        if catalog_path.exists():
            try:
                with open(catalog_path, "r", encoding="utf-8") as cf:
                    cat_data = json.load(cf)
            except Exception:
                pass

        registered_items = []
        total = len(video_candidates)

        for idx, f in enumerate(video_candidates, 1):
            fname = f.get("name", "")
            fid = f.get("id", "")
            fsize = int(f.get("size", 15000000))

            m = tid_regex.search(fname)
            tid = m.group(1).upper() if m else ""
            if not tid:
                continue

            game_title = OnlineFetcher.get_title_by_id(tid) or f"Game {tid}"
            if progress_cb:
                progress_cb(f"[{idx}/{total}] Обработка: {fname} ({tid} — {game_title})...")

            try:
                cls.make_public(fid, token)
            except Exception as e:
                print(f"[-] Warning setting public permission on {fid}: {e}")

            direct_url = GoogleDriveHelper.to_direct_download_url(fid)
            preview_url = GoogleDriveHelper.to_preview_url(fid)

            # Find or create game
            game_entry = None
            for g in cat_data.get("games", []):
                if g.get("titleId", "").upper() == tid:
                    game_entry = g
                    break

            if not game_entry:
                game_entry = {
                    "titleId": tid,
                    "title": game_title,
                    "publisher": "Unknown",
                    "variants": []
                }
                cat_data.setdefault("games", []).append(game_entry)
            else:
                if game_title and (game_entry.get("title", "").startswith("Game ") or not game_entry.get("title")):
                    game_entry["title"] = game_title

            variant_name = "Standard (Google Drive)"
            safe_var_id = "gdrive-standard"
            new_var = {
                "id": safe_var_id,
                "name": variant_name,
                "style": "Animated Art",
                "version": "1.0",
                "url": direct_url,
                "previewUrl": preview_url,
                "sizeBytes": fsize,
                "sha256": "",
                "durationSec": 20.0,
                "author": author or "GoogleDrive",
                "codec": "h264",
                "width": 1280,
                "height": 720,
                "fps": 30.0,
                "hasAudio": True,
                "notes": f"Google Drive Browser Upload: {fname}"
            }

            existing_idx = -1
            for v_idx, v in enumerate(game_entry.get("variants", [])):
                if v.get("id") == safe_var_id:
                    existing_idx = v_idx
                    break

            if existing_idx >= 0:
                game_entry["variants"][existing_idx] = new_var
            else:
                game_entry.setdefault("variants", []).append(new_var)

            registered_items.append({
                "titleId": tid,
                "gameTitle": game_title,
                "fileId": fid,
                "filename": fname,
                "directUrl": direct_url,
                "previewUrl": preview_url,
                "sizeBytes": fsize
            })

        cat_data["updatedAt"] = datetime.now(timezone.utc).isoformat()
        cat_data["totalGames"] = len(cat_data["games"])
        cat_data["totalVariants"] = sum(len(g.get("variants", [])) for g in cat_data["games"])

        catalog_path.parent.mkdir(parents=True, exist_ok=True)
        with open(catalog_path, "w", encoding="utf-8") as cf:
            json.dump(cat_data, cf, ensure_ascii=False, indent=2)

        if progress_cb:
            progress_cb(f"Успешно зарегистрировано {len(registered_items)} видеофонов в catalog.json!")

        return registered_items

