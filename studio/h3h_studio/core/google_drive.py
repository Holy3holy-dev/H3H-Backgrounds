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
        tid_regex = re.compile(r"(0100[0-9A-Fa-f]{12})", re.IGNORECASE)

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
        if not re.match(r"^0100[0-9A-Fa-f]{12}$", clean_tid):
            raise ValueError(f"Некорректный Title ID: '{clean_tid}' (должен быть 16 hex-символов, начиная с 0100)")

        vpath = Path(video_path)
        if not vpath.exists():
            raise FileNotFoundError(f"Файл видео не найден: {vpath}")

        if progress_cb:
            progress_cb("Проверка соответствия стандартам 4IFIR...")

        comp = ComplianceValidator.validate(vpath)
        if not comp.is_compliant:
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
            if game_title and (game_entry.get("title", "").startswith("Game 0100") or not game_entry.get("title")):
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
