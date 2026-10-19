import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional


@dataclass
class VideoAnalysis:
    file_path: str
    container: str = ""
    codec: str = ""
    profile: str = ""
    level: str = ""
    width: int = 0
    height: int = 0
    fps: float = 0.0
    pixel_format: str = ""
    duration_sec: float = 0.0
    bitrate_kbps: int = 0
    has_audio: bool = False
    audio_codec: str = ""
    is_faststart: bool = False
    is_compliant: bool = False
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


class VideoAnalyzer:
    @staticmethod
    def get_ffprobe_path() -> Optional[str]:
        return shutil.which("ffprobe")

    @classmethod
    def analyze_file(cls, file_path: Path) -> VideoAnalysis:
        path = Path(file_path).resolve()
        analysis = VideoAnalysis(file_path=str(path))

        ffprobe = cls.get_ffprobe_path()
        if not ffprobe:
            analysis.issues.append("FFprobe utility not found in system PATH")
            return analysis

        if not path.exists():
            analysis.issues.append(f"File not found: {path}")
            return analysis

        cmd = [
            ffprobe,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(path)
        ]

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(res.stdout)
        except Exception as e:
            analysis.issues.append(f"Failed to probe file: {e}")
            return analysis

        # Parse container format
        fmt = data.get("format", {})
        analysis.container = fmt.get("format_name", "")
        duration_str = fmt.get("duration", "0")
        try:
            analysis.duration_sec = float(duration_str)
        except ValueError:
            analysis.duration_sec = 0.0

        try:
            analysis.bitrate_kbps = int(int(fmt.get("bit_rate", "0")) / 1000)
        except ValueError:
            analysis.bitrate_kbps = 0

        # Parse video and audio streams
        video_stream = None
        for s in data.get("streams", []):
            if s.get("codec_type") == "video" and video_stream is None:
                video_stream = s
            elif s.get("codec_type") == "audio":
                analysis.has_audio = True
                analysis.audio_codec = s.get("codec_name", "")

        if not video_stream:
            analysis.issues.append("No video stream found in file")
            return analysis

        analysis.codec = video_stream.get("codec_name", "").lower()
        analysis.profile = video_stream.get("profile", "")
        level_raw = video_stream.get("level", "")
        analysis.level = str(level_raw) if level_raw is not None else ""
        analysis.width = int(video_stream.get("width", 0))
        analysis.height = int(video_stream.get("height", 0))
        analysis.pixel_format = video_stream.get("pix_fmt", "")

        # Frame rate calculation
        r_fps = video_stream.get("r_frame_rate", "30/1")
        if "/" in r_fps:
            num, den = r_fps.split("/")
            try:
                analysis.fps = round(float(num) / float(den), 2) if float(den) > 0 else 30.0
            except ValueError:
                analysis.fps = 30.0
        else:
            try:
                analysis.fps = float(r_fps)
            except ValueError:
                analysis.fps = 30.0

        # Faststart check (moov atom position)
        analysis.is_faststart = cls._check_faststart(path)

        # 4IFIR Compliance Rule Checking
        cls._evaluate_compliance(analysis)

        return analysis

    @classmethod
    def _check_faststart(cls, path: Path) -> bool:
        """Checks if moov atom precedes mdat atom in MP4 file."""
        try:
            with open(path, "rb") as f:
                # Read first 1MB of header
                head = f.read(1024 * 1024)
                moov_pos = head.find(b"moov")
                mdat_pos = head.find(b"mdat")
                if moov_pos != -1 and (mdat_pos == -1 or moov_pos < mdat_pos):
                    return True
        except Exception:
            pass
        return False

    @classmethod
    def _evaluate_compliance(cls, a: VideoAnalysis):
        compliant = True

        # 1. Codec check (H.264 and HEVC are supported by Tegra X1 on 4IFIR)
        if a.codec not in ("h264", "hevc", "h265"):
            compliant = False
            a.issues.append(f"Non-compliant codec: '{a.codec}'. 4IFIR requires H.264 or HEVC.")
            a.recommendations.append("Transcode to H.264 (AVC) or HEVC.")

        # 2. Pixel format check
        if a.pixel_format not in ("yuv420p", "yuvj420p"):
            compliant = False
            a.issues.append(
                f"Incompatible pixel format: '{a.pixel_format}'. 10-bit or non-4:2:0 chroma causes hardware decode dropouts on Tegra X1."
            )
            a.recommendations.append("Convert to standard 8-bit yuv420p.")

        # 3. Resolution check
        if a.width > 1920 or a.height > 1080:
            compliant = False
            a.issues.append(f"Excessive resolution: {a.width}x{a.height}. Exceeds 1080p maximum limit.")
            a.recommendations.append("Downscale to 1280x720 or 1920x1080.")
        elif a.width > 1280 or a.height > 720:
            a.recommendations.append("Consider 1280x720 downscale to conserve ~60% video RAM bandwidth.")

        # 4. Container check
        if "mp4" not in a.container and "mov" not in a.container:
            compliant = False
            a.issues.append(f"Container '{a.container}' is not MP4.")
            a.recommendations.append("Remux or transcode into standard .mp4 container.")

        # 5. Faststart recommendation
        if not a.is_faststart:
            a.recommendations.append("Enable +faststart flag for instant menu playback.")

        # 6. Framerate check
        if a.fps > 60.5:
            compliant = False
            a.issues.append(f"Frame rate {a.fps} fps exceeds 60 fps limit.")
            a.recommendations.append("Cap frame rate at 30 fps or 60 fps CFR.")

        a.is_compliant = compliant and (len(a.issues) == 0)
