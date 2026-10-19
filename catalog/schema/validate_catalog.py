#!/usr/bin/env python3
"""
Catalog Validation Tool for H3H Backgrounds.
Validates catalog JSON files against schema, integrity rules, security limits,
and Title ID formatting.
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple

TITLE_ID_REGEX = re.compile(r"^0100[0-9A-Fa-f]{12}$")
SHA256_REGEX = re.compile(r"^[0-9a-fA-F]{64}$")
ALLOWED_STYLES = {"Cinematic", "Gameplay", "Animated Art", "Minimal", "Dark", "Retro", "Music"}
ALLOWED_CODECS = {"h264", "hevc"}
MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB max safety cap


class ValidationError(Exception):
    pass


def validate_catalog_data(data: Dict[str, Any]) -> Tuple[int, int]:
    """
    Validates a catalog data dictionary against all domain rules.
    Returns (total_games, total_variants).
    Raises ValidationError if any check fails.
    """
    if not isinstance(data, dict):
        raise ValidationError("Root must be a JSON object")

    if data.get("schemaVersion") != 1:
        raise ValidationError(f"Unsupported schemaVersion: {data.get('schemaVersion')}, expected 1")

    if "updatedAt" not in data or not isinstance(data["updatedAt"], str):
        raise ValidationError("Missing or invalid 'updatedAt' field")

    games = data.get("games")
    if not isinstance(games, list):
        raise ValidationError("'games' must be an array")

    seen_title_ids = set()
    total_variants_count = 0

    for idx, game in enumerate(games):
        if not isinstance(game, dict):
            raise ValidationError(f"Game at index {idx} must be an object")

        title_id = game.get("titleId")
        if not title_id or not isinstance(title_id, str):
            raise ValidationError(f"Game {idx}: missing 'titleId'")

        # Enforce Title ID pattern
        if not TITLE_ID_REGEX.match(title_id):
            raise ValidationError(
                f"Game {idx}: invalid Title ID '{title_id}'. Must be 16 hex chars starting with 0100"
            )

        norm_title_id = title_id.upper()
        if norm_title_id in seen_title_ids:
            raise ValidationError(f"Duplicate Title ID detected: {title_id}")
        seen_title_ids.add(norm_title_id)

        title = game.get("title")
        if not title or not isinstance(title, str) or len(title.strip()) == 0:
            raise ValidationError(f"Game {title_id}: invalid or empty 'title'")

        variants = game.get("variants")
        if not isinstance(variants, list) or len(variants) == 0:
            raise ValidationError(f"Game {title_id}: 'variants' must be a non-empty array")

        seen_variant_ids = set()
        for v_idx, variant in enumerate(variants):
            if not isinstance(variant, dict):
                raise ValidationError(f"Game {title_id}, variant {v_idx} must be an object")

            v_id = variant.get("id")
            if not v_id or not isinstance(v_id, str) or not re.match(r"^[a-z0-9_-]{3,64}$", v_id):
                raise ValidationError(f"Game {title_id}, variant {v_idx}: invalid 'id' ({v_id})")

            if v_id in seen_variant_ids:
                raise ValidationError(f"Game {title_id}: duplicate variant id '{v_id}'")
            seen_variant_ids.add(v_id)

            style = variant.get("style")
            if style not in ALLOWED_STYLES:
                raise ValidationError(
                    f"Game {title_id}, variant '{v_id}': style '{style}' not in {sorted(ALLOWED_STYLES)}"
                )

            # Security checks for URLs
            url = variant.get("url")
            if not url or not isinstance(url, str) or not url.startswith("https://"):
                raise ValidationError(
                    f"Game {title_id}, variant '{v_id}': url must start with https://"
                )

            preview_url = variant.get("previewUrl")
            if not preview_url or not isinstance(preview_url, str) or not preview_url.startswith("https://"):
                raise ValidationError(
                    f"Game {title_id}, variant '{v_id}': previewUrl must start with https://"
                )

            # SHA256 integrity check format
            sha256 = variant.get("sha256")
            if not sha256 or not isinstance(sha256, str) or not SHA256_REGEX.match(sha256):
                raise ValidationError(
                    f"Game {title_id}, variant '{v_id}': invalid sha256 '{sha256}' (must be 64 hex chars)"
                )

            # File size limit check
            size_bytes = variant.get("sizeBytes")
            if not isinstance(size_bytes, int) or size_bytes < 1024 or size_bytes > MAX_FILE_SIZE_BYTES:
                raise ValidationError(
                    f"Game {title_id}, variant '{v_id}': sizeBytes {size_bytes} out of safe range (1KB - 100MB)"
                )

            # Duration check
            duration = variant.get("durationSec")
            if not isinstance(duration, (int, float)) or duration < 1.0 or duration > 300.0:
                raise ValidationError(
                    f"Game {title_id}, variant '{v_id}': durationSec {duration} must be between 1.0 and 300.0s"
                )

            # Codec check
            codec = variant.get("codec")
            if codec not in ALLOWED_CODECS:
                raise ValidationError(
                    f"Game {title_id}, variant '{v_id}': codec '{codec}' not in {sorted(ALLOWED_CODECS)}"
                )

            # Resolution checks
            width = variant.get("width")
            height = variant.get("height")
            if not isinstance(width, int) or width < 640 or width > 1920:
                raise ValidationError(f"Game {title_id}, variant '{v_id}': width {width} not in [640, 1920]")
            if not isinstance(height, int) or height < 360 or height > 1080:
                raise ValidationError(f"Game {title_id}, variant '{v_id}': height {height} not in [360, 1080]")

            # FPS check
            fps = variant.get("fps")
            if not isinstance(fps, (int, float)) or fps < 15.0 or fps > 60.0:
                raise ValidationError(f"Game {title_id}, variant '{v_id}': fps {fps} not in [15.0, 60.0]")

            total_variants_count += 1

    return len(games), total_variants_count


def validate_file(file_path: Path) -> bool:
    print(f"[*] Validating catalog file: {file_path}")
    if not file_path.exists():
        print(f"[-] Error: File not found: {file_path}", file=sys.stderr)
        return False

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"[-] JSON decode error: {e}", file=sys.stderr)
        return False

    try:
        games_count, variants_count = validate_catalog_data(data)
        print(f"[+] VALIDATION SUCCESS:")
        print(f"    - Schema Version: {data.get('schemaVersion')}")
        print(f"    - Total Games:    {games_count}")
        print(f"    - Total Variants: {variants_count}")
        print(f"    - Updated At:     {data.get('updatedAt')}")
        return True
    except ValidationError as e:
        print(f"[-] Validation failed: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("catalog/data/catalog.json")
    success = validate_file(target)
    sys.exit(0 if success else 1)
