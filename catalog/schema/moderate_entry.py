#!/usr/bin/env python3
"""
Moderation Ingestion CLI for H3H Backgrounds Catalog.
Safely inspects submissions via FFprobe, checks 4IFIR compliance, computes SHA-256,
and atomically updates catalog.json.
"""

import argparse
import datetime
import json
import re
import sys
import tempfile
import urllib.request
from pathlib import Path

# Add studio to path to reuse VideoAnalyzer and Encoder
ROOT_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT_DIR / "studio"))

from h3h_studio.core.analyzer import VideoAnalyzer
from h3h_studio.core.encoder import Encoder
from validate_catalog import validate_catalog_data, ValidationError, TITLE_ID_REGEX


def moderate_and_ingest(
    catalog_path: Path,
    title_id: str,
    game_title: str,
    variant_name: str,
    variant_id: str,
    style: str,
    video_url_or_path: str,
    author: str,
    publisher: str = "",
    notes: str = ""
) -> bool:
    print(f"[*] Starting moderation for '{game_title}' ({title_id})")

    # 1. Title ID validation
    norm_title_id = title_id.strip().upper()
    if not TITLE_ID_REGEX.match(norm_title_id):
        print(f"[-] Error: Invalid Title ID format: {norm_title_id}", file=sys.stderr)
        return False

    # 2. Acquire video file (local or download)
    temp_dir = tempfile.TemporaryDirectory()
    temp_path = Path(temp_dir.name) / f"{norm_title_id}.mp4"

    try:
        if video_url_or_path.startswith("https://") or video_url_or_path.startswith("http://"):
            print(f"[*] Downloading remote asset: {video_url_or_path}")
            urllib.request.urlretrieve(video_url_or_path, temp_path)
            public_url = video_url_or_path
        else:
            local_src = Path(video_url_or_path)
            if not local_src.exists():
                print(f"[-] Error: Local file not found: {local_src}", file=sys.stderr)
                return False
            import shutil
            shutil.copy2(local_src, temp_path)
            public_url = f"https://github.com/h3h-backgrounds/assets/releases/download/v1.0.0/{norm_title_id}.mp4"

        # 3. Analyze with VideoAnalyzer
        print("[*] Inspecting video with FFprobe...")
        analysis = VideoAnalyzer.analyze_file(temp_path)

        print(f"    - Codec:        {analysis.codec.upper()}")
        print(f"    - Profile:      {analysis.profile} L{analysis.level}")
        print(f"    - Resolution:   {analysis.width}x{analysis.height}")
        print(f"    - Pixel Format: {analysis.pixel_format}")
        print(f"    - FPS:          {analysis.fps}")
        print(f"    - Faststart:    {analysis.is_faststart}")
        print(f"    - Duration:     {analysis.duration_sec:.1f}s")

        if not analysis.is_compliant:
            print(f"[-] Moderation REJECTED: Video does not meet 4IFIR specifications:", file=sys.stderr)
            for issue in analysis.issues:
                print(f"    • {issue}", file=sys.stderr)
            return False

        # 4. Compute Checksum and Size
        size_bytes = temp_path.stat().st_size
        sha256 = Encoder.calculate_file_sha256(temp_path)
        print(f"[+] SHA-256: {sha256}")
        print(f"[+] Size:    {size_bytes} bytes")

        # 5. Load and update catalog
        with open(catalog_path, "r", encoding="utf-8") as f:
            catalog_data = json.load(f)

        new_variant = {
            "id": variant_id or variant_name.lower().replace(" ", "-").replace("'", ""),
            "name": variant_name,
            "style": style,
            "version": "1.0",
            "url": public_url,
            "previewUrl": public_url.replace(".mp4", ".webp"),
            "sizeBytes": size_bytes,
            "sha256": sha256,
            "durationSec": round(analysis.duration_sec, 1),
            "author": author,
            "codec": analysis.codec,
            "width": analysis.width,
            "height": analysis.height,
            "fps": analysis.fps,
            "hasAudio": analysis.has_audio,
            "notes": notes or "Approved by H3H Moderation"
        }

        # Check if game already exists
        game_entry = None
        for g in catalog_data.get("games", []):
            if g.get("titleId") == norm_title_id:
                game_entry = g
                break

        if game_entry:
            # Replace variant with same id or append
            replaced = False
            for idx, v in enumerate(game_entry["variants"]):
                if v.get("id") == new_variant["id"]:
                    game_entry["variants"][idx] = new_variant
                    replaced = True
                    break
            if not replaced:
                game_entry["variants"].append(new_variant)
            print(f"[+] Updated existing game entry: {norm_title_id}")
        else:
            new_game = {
                "titleId": norm_title_id,
                "title": game_title,
                "publisher": publisher or "Nintendo Switch",
                "variants": [new_variant]
            }
            catalog_data["games"].append(new_game)
            print(f"[+] Added new game entry: {norm_title_id}")

        # Update totals & timestamp
        total_variants = sum(len(g.get("variants", [])) for g in catalog_data["games"])
        catalog_data["totalGames"] = len(catalog_data["games"])
        catalog_data["totalVariants"] = total_variants
        catalog_data["updatedAt"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # 6. Validate updated catalog data
        validate_catalog_data(catalog_data)

        # 7. Write atomically
        with open(catalog_path, "w", encoding="utf-8") as f:
            json.dump(catalog_data, f, indent=2, ensure_ascii=False)

        print(f"[+] SUCCESS: Catalog updated and validated. Total games: {len(catalog_data['games'])}, Total variants: {total_variants}")
        return True

    except ValidationError as ve:
        print(f"[-] Catalog schema validation failed: {ve}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"[-] Unexpected error during moderation: {e}", file=sys.stderr)
        return False
    finally:
        temp_dir.cleanup()


def main():
    parser = argparse.ArgumentParser(description="H3H Catalog Moderation Ingestion Tool")
    parser.add_argument("--catalog", default="catalog/data/catalog.json", help="Path to catalog.json")
    parser.add_argument("--title-id", required=True, help="16-hex Title ID")
    parser.add_argument("--game-title", required=True, help="Display Game Title")
    parser.add_argument("--variant-name", required=True, help="Variant Name")
    parser.add_argument("--variant-id", default="", help="Variant Slug ID")
    parser.add_argument("--style", default="Cinematic", help="Cover Style category")
    parser.add_argument("--video", required=True, help="Path or URL to MP4 video")
    parser.add_argument("--author", required=True, help="Author/Contributor name")
    parser.add_argument("--publisher", default="", help="Game Publisher")
    parser.add_argument("--notes", default="", help="Approval Notes")

    args = parser.parse_args()
    success = moderate_and_ingest(
        catalog_path=Path(args.catalog),
        title_id=args.title_id,
        game_title=args.game_title,
        variant_name=args.variant_name,
        variant_id=args.variant_id,
        style=args.style,
        video_url_or_path=args.video,
        author=args.author,
        publisher=args.publisher,
        notes=args.notes
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
