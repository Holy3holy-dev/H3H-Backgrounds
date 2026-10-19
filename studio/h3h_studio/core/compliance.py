"""
4IFIR Compliance Validator for H3H Studio.
Checks video files against 4IFIR custom firmware hardware decode specifications.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List
from .analyzer import VideoAnalyzer


@dataclass
class ComplianceResult:
    is_valid: bool = False
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    width: int = 0
    height: int = 0
    fps: float = 0.0
    codec: str = ""
    bitrate_kbps: int = 0
    duration_sec: float = 0.0
    has_audio: bool = False


class ComplianceValidator:
    """Validates MP4 files against 4IFIR Tegra X1 hardware decoder capabilities."""

    @classmethod
    def validate_mp4(cls, video_path: Path) -> ComplianceResult:
        analysis = VideoAnalyzer.analyze_file(Path(video_path))
        return ComplianceResult(
            is_valid=analysis.is_compliant,
            errors=analysis.issues,
            warnings=analysis.recommendations,
            width=analysis.width,
            height=analysis.height,
            fps=analysis.fps,
            codec=analysis.codec,
            bitrate_kbps=analysis.bitrate_kbps,
            duration_sec=analysis.duration_sec,
            has_audio=analysis.has_audio,
        )

    validate = validate_mp4
