import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List, Optional


@dataclass
class EncodingProfile:
    name: str
    description: str
    width: int
    height: int
    fps: float
    crf: int
    maxrate_kbps: int
    bufsize_kbps: int
    profile: str = "high"
    level: str = "4.1"
    codec: str = "h264"


PROFILES: Dict[str, EncodingProfile] = {
    "720p_30fps": EncodingProfile(
        name="4IFIR 720p 30fps (Рекомендуемый H.264)",
        description="Оптимальный баланс: минимальная нагрузка на память Tegra X1, плавное воспроизведение, малый размер.",
        width=1280,
        height=720,
        fps=30.0,
        crf=20,
        maxrate_kbps=3500,
        bufsize_kbps=7000,
        profile="high",
        level="4.1",
        codec="h264"
    ),
    "720p_30fps_hevc": EncodingProfile(
        name="4IFIR 720p 30fps (HEVC / H.265 Экономный)",
        description="Аппаратное декодирование NVDEC: на 35-45% меньше размер файла при аналогичном качестве.",
        width=1280,
        height=720,
        fps=30.0,
        crf=22,
        maxrate_kbps=2200,
        bufsize_kbps=4500,
        profile="main",
        level="4.1",
        codec="hevc"
    ),
    "720p_60fps": EncodingProfile(
        name="4IFIR 720p 60fps (Плавный геймплей H.264)",
        description="Для динамичных экшен-фрагментов и быстрого геймплея.",
        width=1280,
        height=720,
        fps=60.0,
        crf=21,
        maxrate_kbps=4500,
        bufsize_kbps=9000,
        profile="high",
        level="4.1",
        codec="h264"
    ),
    "1080p_30fps": EncodingProfile(
        name="4IFIR 1080p 30fps (ТВ режим H.264)",
        description="Высокая чёткость для игры в док-станции на большом экране.",
        width=1920,
        height=1080,
        fps=30.0,
        crf=22,
        maxrate_kbps=6000,
        bufsize_kbps=12000,
        profile="high",
        level="4.1",
        codec="h264"
    ),
    "1080p_30fps_hevc": EncodingProfile(
        name="4IFIR 1080p 30fps (ТВ режим HEVC / H.265)",
        description="Full HD 1080p с пониженным битрейтом и аппаратным ускорением NVDEC.",
        width=1920,
        height=1080,
        fps=30.0,
        crf=23,
        maxrate_kbps=3800,
        bufsize_kbps=7500,
        profile="main",
        level="4.1",
        codec="hevc"
    )
}


class Encoder:
    @staticmethod
    def get_ffmpeg_path() -> Optional[str]:
        return shutil.which("ffmpeg")

    @classmethod
    def build_transcode_command(
        cls,
        input_path: Path,
        output_path: Path,
        profile: EncodingProfile,
        mute_audio: bool = True,
        start_sec: Optional[float] = None,
        duration_sec: Optional[float] = None,
        loop_crossfade_sec: Optional[float] = None
    ) -> List[str]:
        ffmpeg = cls.get_ffmpeg_path() or "ffmpeg"
        cmd = [ffmpeg, "-y"]

        if start_sec is not None and start_sec > 0:
            cmd.extend(["-ss", f"{start_sec:.3f}"])

        if duration_sec is not None and duration_sec > 0 and loop_crossfade_sec is None:
            cmd.extend(["-t", f"{duration_sec:.3f}"])

        cmd.extend(["-i", str(input_path)])

        # Video filter chain
        scale_filter = (
            f"scale={profile.width}:{profile.height}:force_original_aspect_ratio=decrease,"
            f"pad={profile.width}:{profile.height}:(ow-iw)/2:(oh-ih)/2,"
            f"fps={profile.fps},"
            f"format=yuv420p"
        )

        if loop_crossfade_sec and loop_crossfade_sec > 0 and duration_sec and duration_sec > loop_crossfade_sec * 2:
            # Seamless crossfade loop filter: split, offset, and xfade
            # main duration = duration_sec - loop_crossfade_sec
            main_dur = duration_sec - loop_crossfade_sec
            filter_complex = (
                f"[0:v]trim=0:{duration_sec},setpts=PTS-STARTPTS,{scale_filter},split=2[v0][v1];"
                f"[v0]trim=0:{main_dur},setpts=PTS-STARTPTS[base];"
                f"[v1]trim={main_dur}:{duration_sec},setpts=PTS-STARTPTS[tail];"
                f"[tail][base]xfade=transition=fade:duration={loop_crossfade_sec}:offset=0[v]"
            )
            cmd.extend(["-filter_complex", filter_complex, "-map", "[v]"])
        else:
            cmd.extend(["-vf", scale_filter])

        # Codec configuration for 4IFIR
        if getattr(profile, "codec", "h264") == "hevc":
            cmd.extend([
                "-c:v", "libx265",
                "-preset", "medium",
                "-crf", str(profile.crf),
                "-maxrate", f"{profile.maxrate_kbps}k",
                "-bufsize", f"{profile.bufsize_kbps}k",
                "-g", str(int(profile.fps * 2)),
                "-keyint_min", str(int(profile.fps)),
                "-tag:v", "hvc1",
                "-movflags", "+faststart"
            ])
        else:
            cmd.extend([
                "-c:v", "libx264",
                "-preset", "slow",
                "-profile:v", profile.profile,
                "-level", profile.level,
                "-crf", str(profile.crf),
                "-maxrate", f"{profile.maxrate_kbps}k",
                "-bufsize", f"{profile.bufsize_kbps}k",
                "-g", str(int(profile.fps * 2)),
                "-keyint_min", str(int(profile.fps)),
                "-sc_threshold", "0",
                "-movflags", "+faststart"
            ])

        # Audio configuration
        if mute_audio:
            cmd.append("-an")
        else:
            cmd.extend(["-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2"])

        cmd.append(str(output_path))
        return cmd

    @staticmethod
    def calculate_file_sha256(file_path: Path) -> str:
        sha = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                sha.update(chunk)
        return sha.hexdigest().lower()

    @classmethod
    def generate_catalog_entry(
        cls,
        title_id: str,
        game_title: str,
        variant_name: str,
        variant_id: str,
        style: str,
        author: str,
        output_file: Path,
        profile: EncodingProfile,
        duration_sec: float,
        has_audio: bool,
        notes: str = ""
    ) -> Dict[str, Any]:
        size_bytes = output_file.stat().st_size
        sha256 = cls.calculate_file_sha256(output_file)

        return {
            "titleId": title_id.upper(),
            "title": game_title,
            "variants": [
                {
                    "id": variant_id,
                    "name": variant_name,
                    "style": style,
                    "version": "1.0",
                    "url": f"https://github.com/h3h-backgrounds/assets/releases/download/v1.0.0/{title_id.upper()}.mp4",
                    "previewUrl": f"https://raw.githubusercontent.com/h3h-backgrounds/assets/main/previews/{title_id.upper()}.webp",
                    "sizeBytes": size_bytes,
                    "sha256": sha256,
                    "durationSec": round(duration_sec, 1),
                    "author": author,
                    "codec": getattr(profile, "codec", "h264"),
                    "width": profile.width,
                    "height": profile.height,
                    "fps": profile.fps,
                    "hasAudio": has_audio,
                    "notes": notes or f"Encoded with H3H Studio ({profile.name})"
                }
            ]
        }
