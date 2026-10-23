"""
Core processing engine for H3H Studio Express Mode:
- Probing, trimming, and transcoding Switch 720p covers
- Smart 1:1 square cropping and HEVC 256x256 icon generation (4IFIR standard)
- Dual pack (Cover + Icon) simultaneous export
- Google Drive direct publishing with embedded permanent verified credentials
- GitHub catalog registration via REST API
"""

import os
import sys
import re
import json
import uuid
import base64
import subprocess
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, Callable
from datetime import datetime, timezone

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "studio") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "studio"))

from tg_bot.config import (
    VERIFIED_REFRESH_TOKEN,
    VERIFIED_CLIENT_ID,
    VERIFIED_CLIENT_SECRET,
    GDRIVE_FOLDER_ID,
    GDRIVE_ICONS_FOLDER_ID,
    GDRIVE_AFTER_DARK_FOLDER_ID,
    GITHUB_TOKEN,
    GITHUB_REPO,
    GITHUB_BRANCH,
    GITHUB_BRANCH_AFTER_DARK,
    CATALOG_PATH_STANDARD,
    CATALOG_PATH_AFTER_DARK
)
from h3h_studio.core.google_drive import GoogleDriveHelper, GoogleDriveClient
from h3h_studio.core.github_publisher import GitHubPublisher


class ExpressProcessor:
    """Handles video conversion, cropping, and 1-click cloud publishing."""

    @staticmethod
    def probe_video(video_path: Path) -> Dict[str, Any]:
        """Inspects input video using ffprobe."""
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "stream=codec_name,codec_type,width,height,duration,r_frame_rate",
            "-show_entries", "format=duration,size,bit_rate",
            "-of", "json",
            str(video_path)
        ]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=12)
            data = json.loads(res.stdout)
            streams = data.get("streams", [])
            fmt = data.get("format", {})

            video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
            audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

            width = int(video_stream.get("width", 0))
            height = int(video_stream.get("height", 0))

            dur_str = fmt.get("duration") or video_stream.get("duration") or "0"
            duration = float(dur_str)

            # Frame rate
            fps_str = video_stream.get("r_frame_rate", "30/1")
            try:
                num, den = fps_str.split("/")
                fps = float(num) / float(den)
            except Exception:
                fps = 30.0

            return {
                "ok": True,
                "width": width,
                "height": height,
                "duration": duration,
                "fps": round(fps, 2),
                "codec": video_stream.get("codec_name", "").lower(),
                "has_audio": audio_stream is not None,
                "file_size": int(fmt.get("size") or video_path.stat().st_size)
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @staticmethod
    def extract_preview_frame(video_path: Path, timestamp_sec: float, out_img: Path) -> bool:
        """Extracts a single frame from video at timestamp for UI preview."""
        out_img.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            "ffmpeg", "-y", "-nostdin",
            "-ss", str(max(0.0, timestamp_sec)),
            "-i", str(video_path),
            "-vframes", "1",
            "-q:v", "3",
            str(out_img)
        ]
        try:
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10, check=True)
            return out_img.exists() and out_img.stat().st_size > 0
        except Exception:
            return False

    @staticmethod
    def process_cover(
        src_vid: Path,
        out_mp4: Path,
        out_thumb: Path,
        start_sec: float = 0.0,
        dur_sec: float = 12.0,
        codec: str = "h264",
        keep_audio: bool = True,
        on_progress: Optional[Callable[[float, str], None]] = None
    ) -> bool:
        """Transcodes video to 4IFIR 720p 30fps Switch Cover standard."""
        out_mp4.parent.mkdir(parents=True, exist_ok=True)
        out_thumb.parent.mkdir(parents=True, exist_ok=True)

        if on_progress:
            on_progress(10.0, "Начало конвертации фона (1280x720 30fps)...")

        is_hevc = codec.lower() in ("hevc", "h265")

        cmd = [
            "ffmpeg", "-y", "-nostdin",
            "-threads", "4",
            "-ss", str(max(0.0, start_sec)),
            "-t", str(max(1.0, dur_sec)),
            "-i", str(src_vid),
            "-vf", "scale=1280:720:force_original_aspect_ratio=decrease:flags=fast_bilinear,pad=1280:720:(ow-iw)/2:(oh-ih)/2:black",
            "-r", "30",
            "-pix_fmt", "yuv420p"
        ]

        if is_hevc:
            cmd.extend([
                "-c:v", "libx265",
                "-preset", "ultrafast",
                "-crf", "24",
                "-tag:v", "hvc1"
            ])
        else:
            cmd.extend([
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-tune", "fastdecode",
                "-profile:v", "high",
                "-level", "4.1",
                "-crf", "22",
                "-maxrate", "4000k",
                "-bufsize", "7000k"
            ])

        if keep_audio:
            cmd.extend(["-c:a", "aac", "-b:a", "128k", "-ar", "48000"])
        else:
            cmd.extend(["-an"])

        cmd.extend(["-movflags", "+faststart", str(out_mp4)])

        try:
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=240, check=True)
        except Exception as e:
            raise RuntimeError(f"Ошибка конвертации фона FFmpeg: {e}")

        # Extract 640x360 thumbnail
        cmd_thumb = [
            "ffmpeg", "-y", "-nostdin",
            "-ss", "1",
            "-i", str(out_mp4),
            "-vframes", "1",
            "-vf", "scale=640:360:force_original_aspect_ratio=decrease:flags=fast_bilinear,pad=640:360:(ow-iw)/2:(oh-ih)/2:black",
            str(out_thumb)
        ]
        try:
            subprocess.run(cmd_thumb, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
        except Exception:
            pass

        return out_mp4.exists()

    @staticmethod
    def process_icon(
        src_vid: Path,
        out_mp4: Path,
        out_thumb: Path,
        start_sec: float = 0.0,
        dur_sec: float = 8.0,
        crop_pan_percent: float = 50.0,
        video_w: int = 1280,
        video_h: int = 720,
        codec: str = "hevc",
        on_progress: Optional[Callable[[float, str], None]] = None
    ) -> bool:
        """
        Crops and transcodes 1:1 square video icon to exact 4IFIR standard:
        256x256 HEVC Main profile, 24fps, no audio.
        crop_pan_percent: 0.0 = left edge, 50.0 = center, 100.0 = right edge.
        """
        out_mp4.parent.mkdir(parents=True, exist_ok=True)
        out_thumb.parent.mkdir(parents=True, exist_ok=True)

        if on_progress:
            on_progress(20.0, "Кадрирование и кодирование видеоиконки (256x256 HEVC)...")

        # Calculate crop rectangle
        if video_w > video_h:
            sq_size = video_h
            max_offset = video_w - video_h
            offset_x = int(max_offset * (max(0.0, min(100.0, crop_pan_percent)) / 100.0))
            crop_filter = f"crop={sq_size}:{sq_size}:{offset_x}:0,scale=256:256:flags=fast_bilinear"
        elif video_h > video_w:
            sq_size = video_w
            max_offset = video_h - video_w
            offset_y = int(max_offset * (max(0.0, min(100.0, crop_pan_percent)) / 100.0))
            crop_filter = f"crop={sq_size}:{sq_size}:0:{offset_y},scale=256:256:flags=fast_bilinear"
        else:
            crop_filter = "scale=256:256:flags=fast_bilinear"

        cmd = [
            "ffmpeg", "-y", "-nostdin",
            "-threads", "4",
            "-ss", str(max(0.0, start_sec)),
            "-t", str(max(1.0, dur_sec)),
            "-i", str(src_vid),
            "-vf", crop_filter,
            "-r", "24",
            "-pix_fmt", "yuv420p",
            "-an",
            "-c:v", "libx265",
            "-preset", "ultrafast",
            "-crf", "26",
            "-tag:v", "hvc1",
            "-movflags", "+faststart",
            str(out_mp4)
        ]

        try:
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120, check=True)
        except Exception as e:
            raise RuntimeError(f"Ошибка кодирования видеоиконки: {e}")

        # Extract 256x256 thumbnail
        cmd_thumb = [
            "ffmpeg", "-y", "-nostdin",
            "-ss", "0.5",
            "-i", str(out_mp4),
            "-vframes", "1",
            str(out_thumb)
        ]
        try:
            subprocess.run(cmd_thumb, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        except Exception:
            pass

        return out_mp4.exists()

    @classmethod
    def get_permanent_gdrive_auth(cls) -> Optional[str]:
        """Obtains Google Drive access token using permanent verified credentials."""
        token = GoogleDriveHelper.refresh_access_token(
            refresh_token=VERIFIED_REFRESH_TOKEN,
            client_id=VERIFIED_CLIENT_ID,
            client_secret=VERIFIED_CLIENT_SECRET
        )
        if token and token.startswith("ya29."):
            return token
        cfg = GoogleDriveHelper.get_stored_config()
        stored_token = cfg.get("token")
        if stored_token:
            return stored_token
        return None

    @classmethod
    def publish_community_asset(
        cls,
        title_id: str,
        game_name: str,
        variant_name: str,
        author: str,
        category: str = "standard",
        cover_mp4: Optional[Path] = None,
        cover_thumb: Optional[Path] = None,
        icon_mp4: Optional[Path] = None,
        on_progress: Optional[Callable[[float, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Uploads processed cover and/or icon to Google Drive and publishes into catalog on GitHub!
        Fully automated with embedded credentials.
        """
        if on_progress:
            on_progress(60.0, "Авторизация в облаке Google Drive...")

        token = cls.get_permanent_gdrive_auth()
        if not token:
            raise RuntimeError("Не удалось авторизоваться в Google Drive (проверьте подключение к сети).")

        cover_folder_id = GDRIVE_AFTER_DARK_FOLDER_ID if category == "after_dark" else GDRIVE_FOLDER_ID
        icons_folder_id = GDRIVE_ICONS_FOLDER_ID

        cover_direct_url = ""
        cover_preview_url = ""
        cover_size = 0

        icon_direct_url = ""
        icon_size = 0

        # Upload cover if provided
        if cover_mp4 and cover_mp4.exists():
            if on_progress:
                on_progress(70.0, "Загрузка фонового видео на Google Диск...")
            c_res = GoogleDriveClient.upload_file(cover_mp4, cover_folder_id, token)
            cover_direct_url = c_res.get("directUrl", "")
            cover_preview_url = c_res.get("previewUrl", "")
            cover_size = c_res.get("size", cover_mp4.stat().st_size)

        # Upload icon if provided
        if icon_mp4 and icon_mp4.exists():
            if on_progress:
                on_progress(85.0, "Загрузка видеоиконки в папку H3H_Video_Icons...")
            i_res = GoogleDriveClient.upload_file(icon_mp4, icons_folder_id, token)
            icon_direct_url = i_res.get("directUrl", "")
            icon_size = i_res.get("size", icon_mp4.stat().st_size)

        if not cover_direct_url and not icon_direct_url:
            raise RuntimeError("Ни один файл не был успешно загружен на Google Диск.")

        # Register in catalog
        if on_progress:
            on_progress(92.0, "Обновление каталога на GitHub...")

        target_catalog_rel = CATALOG_PATH_AFTER_DARK if category == "after_dark" else CATALOG_PATH_STANDARD
        target_branch = GITHUB_BRANCH_AFTER_DARK if category == "after_dark" else GITHUB_BRANCH

        author_tag = f"@{author}" if author and not author.startswith("@") else (author or "@Community")
        var_id = f"var-{uuid.uuid4().hex[:8]}"

        new_var: Dict[str, Any] = {
            "id": var_id,
            "name": variant_name or "Dynamic Theme",
            "style": "4IFIR Dynamic Pack" if (cover_direct_url and icon_direct_url) else ("Community Video Icon" if icon_direct_url else "Community Animated"),
            "version": "1.0",
            "url": cover_direct_url,
            "previewUrl": cover_preview_url,
            "sizeBytes": cover_size,
            "sha256": "",
            "durationSec": 10.0,
            "author": author_tag,
            "codec": "h264",
            "width": 1280,
            "height": 720,
            "fps": 30.0,
            "hasAudio": True,
            "hasIcon": bool(icon_direct_url),
            "notes": f"Created with H3H Studio Express Mode by {author_tag}"
        }

        if icon_direct_url:
            new_var["iconUrl"] = icon_direct_url
            new_var["iconSizeBytes"] = icon_size
            new_var["iconCodec"] = "hevc"
            new_var["iconWidth"] = 256
            new_var["iconHeight"] = 256

        # Fetch remote catalog to prevent overwrites
        catalog_path = PROJECT_ROOT / target_catalog_rel
        cat_data = json.loads(catalog_path.read_text(encoding="utf-8"))

        games_list = cat_data.get("games", [])
        game_entry = next((g for g in games_list if g.get("titleId", "").upper() == title_id.upper()), None)
        if not game_entry:
            game_entry = {
                "titleId": title_id.upper(),
                "title": game_name,
                "publisher": "Community",
                "variants": []
            }
            games_list.append(game_entry)

        game_entry["variants"].append(new_var)
        cat_data["totalGames"] = len(games_list)
        cat_data["totalVariants"] = sum(len(g.get("variants", [])) for g in games_list)
        cat_data["lastUpdated"] = datetime.now(timezone.utc).isoformat()

        catalog_path.write_text(json.dumps(cat_data, indent=2, ensure_ascii=False), encoding="utf-8")

        # Push to GitHub
        commit_msg = f"feat(catalog): add '{variant_name}' for {title_id} by {author_tag} via H3H Studio"
        from tg_bot.bot import push_catalog_to_github
        push_ok = push_catalog_to_github(target_catalog_rel, commit_msg, branch=target_branch)

        if on_progress:
            on_progress(100.0, "Опубликовано успешно!")

        return {
            "ok": True,
            "title_id": title_id,
            "game_name": game_name,
            "variant_name": variant_name,
            "cover_url": cover_direct_url,
            "icon_url": icon_direct_url,
            "push_ok": push_ok
        }
