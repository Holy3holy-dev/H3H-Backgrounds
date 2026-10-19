import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Any, Optional


@dataclass
class StudioProject:
    version: int = 1
    mode: str = "custom"  # "artwork", "gameplay", "custom"
    game_title: str = ""
    title_id: str = ""
    variant_name: str = ""
    style: str = "Cinematic"
    author: str = ""
    input_file: str = ""
    output_profile: str = "720p_30fps"
    mute_audio: bool = True
    start_sec: float = 0.0
    duration_sec: float = 15.0
    loop_crossfade_sec: float = 1.0
    artwork_effect: str = "sine_zoom"
    add_vignette: bool = True

    def save(self, file_path: Path):
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, file_path: Path) -> "StudioProject":
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
