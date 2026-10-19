import math
import shutil
from pathlib import Path
from typing import List, Optional
from .encoder import EncodingProfile, PROFILES


class KenBurnsGenerator:
    @staticmethod
    def build_artwork_command(
        image_path: Path,
        output_path: Path,
        duration_sec: float = 15.0,
        effect_type: str = "sine_zoom",
        profile: Optional[EncodingProfile] = None,
        add_vignette: bool = True
    ) -> List[str]:
        if profile is None:
            profile = PROFILES["720p_30fps"]

        ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
        total_frames = int(duration_sec * profile.fps)

        # Mathematical seamless sine-wave expressions (guaranteed 100% loop seam match)
        if effect_type == "sine_zoom":
            # Zooms smoothly from 1.05 to 1.18 and back to 1.05
            z_expr = f"'1.10+0.07*sin(2*PI*on/{total_frames})'"
            x_expr = "'iw/2-(iw/zoom/2)'"
            y_expr = "'ih/2-(ih/zoom/2)'"
        elif effect_type == "horizontal_drift":
            # Pans horizontally left-to-right and back
            z_expr = "'1.15'"
            x_expr = f"'(iw-iw/zoom)*(0.5+0.4*sin(2*PI*on/{total_frames}))'"
            y_expr = "'ih/2-(ih/zoom/2)'"
        elif effect_type == "diagonal_float":
            # Gentle floating motion
            z_expr = f"'1.12+0.05*cos(2*PI*on/{total_frames})'"
            x_expr = f"'(iw-iw/zoom)*(0.5+0.3*sin(2*PI*on/{total_frames}))'"
            y_expr = f"'(ih-ih/zoom)*(0.5+0.3*cos(2*PI*on/{total_frames}))'"
        else:
            z_expr = "'1.10'"
            x_expr = "'iw/2-(iw/zoom/2)'"
            y_expr = "'ih/2-(ih/zoom/2)'"

        zoompan_filter = (
            f"zoompan=z={z_expr}:x={x_expr}:y={y_expr}:d={total_frames}:"
            f"s={profile.width}x{profile.height}:fps={profile.fps}"
        )

        filter_chain = zoompan_filter
        if add_vignette:
            filter_chain += ",vignette=PI/4"
        filter_chain += ",format=yuv420p"

        cmd = [
            ffmpeg, "-y",
            "-loop", "1",
            "-i", str(image_path),
            "-vf", filter_chain,
            "-t", f"{duration_sec:.2f}",
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
            "-an",
            "-movflags", "+faststart",
            str(output_path)
        ]

        return cmd
