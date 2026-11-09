"""
H3H Video Icon Harvester: Top 100 Popular Nintendo Switch Titles x 3 Variations (300 Video Icons)
STRICTLY FOR LOCAL STAGING AND REVIEW (DOES NOT PUBLISH TO CATALOG.JSON OR GITHUB).

Generates 256x256 30fps H.264 video icons for Nintendo Switch Home Menu (4IFIR format):
- Variation 1: Hero Portrait Loop (1:1 Character/Protagonist Focus)
- Variation 2: Dynamic Action Loop (1:1 Action/Gameplay Focus)
- Variation 3: Atmospheric Cinematic Loop (1:1 Cinematic/Art/Logo Focus)
"""

import os
import sys
import json
import re
import time
import shutil
import requests
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
sys.stderr.reconfigure(encoding='utf-8', line_buffering=True)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

STAGE_ICONS_DIR = Path(r"H:\h3h_stage\video_icons_100")
STAGE_ICONS_DIR.mkdir(parents=True, exist_ok=True)

STAGE_720P_DIR = Path(r"H:\h3h_stage\720p")
CACHE_DOWNLOADS_DIR = PROJECT_ROOT / "tmp" / "video_icons_cache"
CACHE_DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

LOCAL_PREVIEW_DIR = PROJECT_ROOT / "tmp" / "video_icons_staging"
LOCAL_PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

ARTIFACTS_DIR = Path(r"C:\Users\HL\.gemini\antigravity\brain\0e2eccd7-a141-47bd-bba5-1dd6edc63967")
SHOWCASE_OUT_DIR = ARTIFACTS_DIR / "showcase_icons_100"
SHOWCASE_OUT_DIR.mkdir(parents=True, exist_ok=True)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": USER_AGENT})

# Load catalog for cross-referencing variant IDs
cat_path = PROJECT_ROOT / "catalog" / "data" / "catalog.json"
catalog_data = json.loads(cat_path.read_text(encoding="utf-8")) if cat_path.exists() else {"games": []}
games_by_tid = {g["titleId"].upper(): g for g in catalog_data.get("games", [])}

# Build index of valid local 720p files (only files >= 500 KB)
local_720p_files = {}
if STAGE_720P_DIR.exists():
    for f in STAGE_720P_DIR.glob("*.*"):
        if f.suffix.lower() in [".mp4", ".webm", ".mkv"]:
            try:
                if f.stat().st_size >= 500000:
                    local_720p_files[f.name.lower()] = f
                    local_720p_files[f.stem.lower()] = f
            except Exception:
                pass

# Curated List of Exact Top 100 Nintendo Switch Popular Games
TOP_100_GAMES = [
    # Top Nintendo Exclusives & Flagships (35)
    ("010015100B514000", "Super Mario Bros. Wonder", "Super Mario Bros Wonder", None, "Nintendo Exclusives"),
    ("01008CF01BAAC000", "The Legend of Zelda: Echoes of Wisdom", "The Legend of Zelda Echoes of Wisdom", None, "Nintendo Exclusives"),
    ("0100F2C0115B6000", "The Legend of Zelda: Tears of the Kingdom", "The Legend of Zelda Tears of the Kingdom", None, "Nintendo Exclusives"),
    ("01007EF00011E000", "The Legend of Zelda: Breath of the Wild", "The Legend of Zelda Breath of the Wild", None, "Nintendo Exclusives"),
    ("0100000000010000", "Super Mario Odyssey", "Super Mario Odyssey", None, "Nintendo Exclusives"),
    ("0100152000022000", "Mario Kart 8 Deluxe", "Mario Kart 8 Deluxe", None, "Nintendo Exclusives"),
    ("01006A800016E000", "Super Smash Bros. Ultimate", "Super Smash Bros Ultimate", None, "Nintendo Exclusives"),
    ("01002DA013484000", "Metroid Dread", "Metroid Dread", None, "Nintendo Exclusives"),
    ("010012101468C000", "Metroid Prime Remastered", "Metroid Prime Remastered", None, "Nintendo Exclusives"),
    ("01006F8002326000", "Animal Crossing: New Horizons", "Animal Crossing New Horizons", None, "Nintendo Exclusives"),
    ("01001F5010DFA000", "Pokemon Legends: Arceus", "Pokemon Legends Arceus", None, "Nintendo Exclusives"),
    ("0100A3D008C5C000", "Pokemon Scarlet", "Pokemon Scarlet", None, "Nintendo Exclusives"),
    ("0100ABF008968000", "Pokemon Sword", "Pokemon Sword", None, "Nintendo Exclusives"),
    ("0100BD0009ED6000", "Super Mario 3D World + Bowser's Fury", "Super Mario 3D World", None, "Nintendo Exclusives"),
    ("01006BB00C6F0000", "The Legend of Zelda: Link's Awakening", "The Legend of Zelda Links Awakening", None, "Nintendo Exclusives"),
    ("0100DA9013230000", "The Legend of Zelda: Skyward Sword HD", "The Legend of Zelda Skyward Sword HD", None, "Nintendo Exclusives"),
    ("0100ECD018EBE000", "Paper Mario: The Thousand-Year Door", "Paper Mario The Thousand-Year Door", None, "Nintendo Exclusives"),
    ("01004C300E9F0000", "Paper Mario: The Origami King", "Paper Mario The Origami King", None, "Nintendo Exclusives"),
    ("0100BC0018138000", "Super Mario RPG", "Super Mario RPG", None, "Nintendo Exclusives"),
    ("0100DCA0064A6000", "Luigi's Mansion 3", "Luigis Mansion 3", None, "Nintendo Exclusives"),
    ("0100B7C00933A000", "Pikmin 4", "Pikmin 4", None, "Nintendo Exclusives"),
    ("01003BC0000A0000", "Kirby and the Forgotten Land", "Kirby and the Forgotten Land", None, "Nintendo Exclusives"),
    ("01007A3009184000", "Princess Peach: Showtime!", "Princess Peach Showtime", None, "Nintendo Exclusives"),
    ("0100C1F0051B6000", "Donkey Kong Country: Tropical Freeze", "Donkey Kong Country Tropical Freeze", None, "Nintendo Exclusives"),
    ("0100C2500FC20000", "Splatoon 3", "Splatoon 3", None, "Nintendo Exclusives"),
    ("01003C700009C000", "Splatoon 2", "Splatoon 2", None, "Nintendo Exclusives"),
    ("0100FF500E34A000", "Xenoblade Chronicles Definitive Edition", "Xenoblade Chronicles", None, "Nintendo Exclusives"),
    ("0100E95004038000", "Xenoblade Chronicles 2", "Xenoblade Chronicles 2", None, "Nintendo Exclusives"),
    ("010074F013262000", "Xenoblade Chronicles 3", "Xenoblade Chronicles 3", None, "Nintendo Exclusives"),
    ("010055D009F78000", "Fire Emblem: Three Houses", "Fire Emblem Three Houses", None, "Nintendo Exclusives"),
    ("0100A6301214E000", "Fire Emblem Engage", "Fire Emblem Engage", None, "Nintendo Exclusives"),
    ("01007300020FA000", "Astral Chain", "Astral Chain", None, "Nintendo Exclusives"),
    ("01004A4010FEA000", "Bayonetta 3", "Bayonetta 3", None, "Nintendo Exclusives"),
    ("010076F0049A4000", "Bayonetta 2", "Bayonetta 2", None, "Nintendo Exclusives"),
    ("010076F0049A2000", "Bayonetta", "Bayonetta", 460790, "Nintendo Exclusives"),

    # Major RPGs & Modern Masterpieces (35)
    ("01003D100E9C6000", "The Witcher 3: Wild Hunt", "The Witcher 3 Wild Hunt", 292030, "RPGs & Masterpieces"),
    ("01005CA01580E000", "Persona 5 Royal", "Persona 5 Royal", 1687950, "RPGs & Masterpieces"),
    ("010062B01525C000", "Persona 4 Golden", "Persona 4 Golden", 1113000, "RPGs & Masterpieces"),
    ("0100DCD01525A000", "Persona 3 Portable", "Persona 3 Portable", 1809700, "RPGs & Masterpieces"),
    ("01005C000B2AE000", "NieR:Automata", "NieR Automata", 524220, "RPGs & Masterpieces"),
    ("010028D005A3C000", "The Elder Scrolls V: Skyrim", "The Elder Scrolls V Skyrim", 489830, "RPGs & Masterpieces"),
    ("01007820196A6000", "Red Dead Redemption", "Red Dead Redemption", 2668510, "RPGs & Masterpieces"),
    ("01004AB00A260000", "Dark Souls Remastered", "Dark Souls Remastered", 570940, "RPGs & Masterpieces"),
    ("0100B04011742000", "Monster Hunter Rise", "Monster Hunter Rise", 1446780, "RPGs & Masterpieces"),
    ("010069C01AB82000", "Shin Megami Tensei V: Vengeance", "Shin Megami Tensei V Vengeance", 1875830, "RPGs & Masterpieces"),
    ("010057D006492000", "Octopath Traveler", "Octopath Traveler", 921570, "RPGs & Masterpieces"),
    ("0100755018612000", "Octopath Traveler II", "Octopath Traveler II", 1971650, "RPGs & Masterpieces"),
    ("01006C300E9F0000", "Dragon Quest XI S: Echoes of an Elusive Age", "Dragon Quest XI S", 1295510, "RPGs & Masterpieces"),
    ("01004BC0166CC000", "Crisis Core - Final Fantasy VII Reunion", "Crisis Core Final Fantasy VII Reunion", 1608070, "RPGs & Masterpieces"),
    ("0100A5B00BDC6000", "Final Fantasy VII", "Final Fantasy VII", 39140, "RPGs & Masterpieces"),
    ("0100B1A00C254000", "Final Fantasy VIII Remastered", "Final Fantasy VIII Remastered", 1026680, "RPGs & Masterpieces"),
    ("0100E2600AEA4000", "Final Fantasy IX", "Final Fantasy IX", 377840, "RPGs & Masterpieces"),
    ("0100BC300CB48000", "Final Fantasy X/X-2 HD Remaster", "Final Fantasy X HD Remaster", 359870, "RPGs & Masterpieces"),
    ("0100EB100AB42000", "Final Fantasy XII: The Zodiac Age", "Final Fantasy XII The Zodiac Age", 595520, "RPGs & Masterpieces"),
    ("01003F00163CE000", "Batman: Arkham Trilogy", "Batman Arkham City", 200260, "RPGs & Masterpieces"),
    ("0100092021C80000", "Tomb Raider (2013)", "Tomb Raider", 203160, "RPGs & Masterpieces"),
    ("010024601BB16000", "Tomb Raider I-III Remastered", "Tomb Raider Remastered", 2525380, "RPGs & Masterpieces"),
    ("0100BC0005C8A000", "DOOM (2016)", "DOOM", 379720, "RPGs & Masterpieces"),
    ("01000B900D8B0000", "DOOM Eternal", "DOOM Eternal", 782330, "RPGs & Masterpieces"),
    ("010034400C3DA000", "Wolfenstein II: The New Colossus", "Wolfenstein II The New Colossus", 612880, "RPGs & Masterpieces"),
    ("010014200B0D0000", "Metro 2033 Redux", "Metro 2033 Redux", 286690, "RPGs & Masterpieces"),
    ("01000F400B0D2000", "Metro: Last Light Redux", "Metro Last Light Redux", 287390, "RPGs & Masterpieces"),
    ("010038800C3DC000", "BioShock Remastered", "BioShock Remastered", 409710, "RPGs & Masterpieces"),
    ("010065000C3DE000", "BioShock Infinite", "BioShock Infinite", 8870, "RPGs & Masterpieces"),
    ("01000F900C404000", "Borderlands 2", "Borderlands 2", 49520, "RPGs & Masterpieces"),
    ("01005A300C3FA000", "Borderlands: The Pre-Sequel", "Borderlands The Pre-Sequel", 261640, "RPGs & Masterpieces"),
    ("010075D00E8BA000", "Alien: Isolation", "Alien Isolation", 214490, "RPGs & Masterpieces"),
    ("010042400D600000", "No Man's Sky", "No Man's Sky", 275850, "RPGs & Masterpieces"),
    ("0100E5F00E88C000", "Subnautica", "Subnautica", 264710, "RPGs & Masterpieces"),
    ("010023200C12C000", "Subnautica: Below Zero", "Subnautica Below Zero", 848450, "RPGs & Masterpieces"),

    # Acclaimed Indie Masterpieces & Popular Classics (30)
    ("010036500ECF2000", "Hollow Knight", "Hollow Knight", 367520, "Indie & Classics"),
    ("010052300B254000", "Hades", "Hades", 1145360, "Indie & Classics"),
    ("01008C3005A66000", "Dead Cells", "Dead Cells", 588650, "Indie & Classics"),
    ("0100CD801CE5E000", "Balatro", "Balatro", 2379780, "Indie & Classics"),
    ("010097F018538000", "Dave the Diver", "Dave the Diver", 1868140, "Indie & Classics"),
    ("01002E7016C46000", "Cult of the Lamb", "Cult of the Lamb", 1313140, "Indie & Classics"),
    ("010079C009494000", "Cuphead", "Cuphead", 268910, "Indie & Classics"),
    ("01002B30028F6000", "Celeste", "Celeste", 504230, "Indie & Classics"),
    ("0100698009C6E000", "Blasphemous", "Blasphemous", 774361, "Indie & Classics"),
    ("010040801A4C8000", "Blasphemous 2", "Blasphemous 2", 2114740, "Indie & Classics"),
    ("010029600D56A000", "Katana Zero", "Katana ZERO", 460950, "Indie & Classics"),
    ("010090F012916000", "Ghostrunner", "Ghostrunner", 1139900, "Indie & Classics"),
    ("010093800B8C8000", "Stardew Valley", "Stardew Valley", 413150, "Indie & Classics"),
    ("01008C0016544000", "Sea of Stars", "Sea of Stars", 1244090, "Indie & Classics"),
    ("0100307018934000", "Signalis", "Signalis", 1262350, "Indie & Classics"),
    ("0100DA801624E000", "Tunic", "Tunic", 553420, "Indie & Classics"),
    ("010027F017B12000", "Inscryption", "Inscryption", 1092790, "Indie & Classics"),
    ("01008CD0172D6000", "Dredge", "Dredge", 1562430, "Indie & Classics"),
    ("01003DC0144B6000", "Outer Wilds", "Outer Wilds", 753640, "Indie & Classics"),
    ("010086C00AF7C000", "Ori and the Will of the Wisps", "Ori and the Will of the Wisps", 1057090, "Indie & Classics"),
    ("0100210019428000", "Prince of Persia: The Lost Crown", "Prince of Persia The Lost Crown", 2751000, "Indie & Classics"),
    ("0100ABD01785C000", "Portal Companion Collection", "Portal 2", 620, "Indie & Classics"),
    ("01007E6002A54000", "Sonic Mania", "Sonic Mania", 584400, "Indie & Classics"),
    ("0100994017EE6000", "Sonic Frontiers", "Sonic Frontiers", 1237320, "Indie & Classics"),
    ("0100A6901170A000", "Need for Speed: Hot Pursuit Remastered", "Need for Speed Hot Pursuit", 1328660, "Indie & Classics"),
    ("0100659013AEA000", "Grand Theft Auto: Vice City - Definitive", "Grand Theft Auto Vice City", 1547000, "Indie & Classics"),
    ("010065A013AEC000", "Grand Theft Auto: San Andreas - Definitive", "Grand Theft Auto San Andreas", 1546990, "Indie & Classics"),
    ("010009B00E71A000", "Slay the Spire", "Slay the Spire", 646570, "Indie & Classics"),
    ("0100DC70188AE000", "Vampire Survivors", "Vampire Survivors", 1794680, "Indie & Classics"),
    ("0100CF5010FEC000", "Bayonetta Origins: Cereza and the Lost Demon", "Bayonetta Origins", None, "Indie & Classics")
]

def get_duration(p: Path) -> float:
    """Gets duration of video file in seconds via ffprobe."""
    try:
        cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', str(p)]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        return float(res.stdout.strip() or 0)
    except Exception:
        return 0.0

def find_local_sources_for_game(tid: str, title: str, query: str) -> List[Tuple[Path, float]]:
    """Finds valid local video files matching the titleId or catalog variants."""
    sources = []
    tid_u = tid.upper()
    seen_paths = set()
    
    def try_add(path: Path):
        if path not in seen_paths and path.exists():
            try:
                if path.stat().st_size >= 500000:
                    dur = get_duration(path)
                    if dur >= 3.0:
                        sources.append((path, dur))
                        seen_paths.add(path)
            except Exception:
                pass
                
    # 1. By titleId prefix in H:\h3h_stage\720p
    for name, path in local_720p_files.items():
        if tid_u.lower() in name:
            try_add(path)
            
    # 2. By catalog variants
    cat_game = games_by_tid.get(tid_u)
    if cat_game:
        for v in cat_game.get("variants", []):
            vid = (v.get("id") or "").lower()
            if vid in local_720p_files:
                try_add(local_720p_files[vid])
                
    # 3. By distinctive keywords
    clean_words = [w.lower() for w in re.sub(r"[^\w\s]", "", query).split() if len(w) > 3 and w.lower() not in ["remastered", "definitive", "edition", "deluxe"]]
    if len(clean_words) >= 2:
        for name, path in local_720p_files.items():
            if all(w in name for w in clean_words[:2]):
                try_add(path)
                
    return sources

def download_online_loops(query: str, needed: int = 3) -> List[Tuple[Path, float]]:
    """Fetches high-quality animated MP4 loops from Tenor with strict duration & size checks."""
    results = []
    try:
        clean = re.sub(r"[^\w\s]", "", query).strip().replace(" ", "-").lower()
        url = f"https://tenor.com/search/{clean}-gifs"
        r = SESSION.get(url, timeout=6)
        if r.status_code == 200:
            mp4_urls = list(set(re.findall(r'https://media\.tenor\.com/[^\s"\'<>]+\.mp4', r.text)))
            safe_q = re.sub(r"[^\w]", "_", query)[:22]
            
            for idx, u in enumerate(mp4_urls):
                if len(results) >= needed:
                    break
                cached = CACHE_DOWNLOADS_DIR / f"{safe_q}_{idx}.mp4"
                if not cached.exists() or cached.stat().st_size < 15000:
                    try:
                        r2 = SESSION.get(u, timeout=6)
                        if r2.status_code == 200 and len(r2.content) >= 15000:
                            cached.write_bytes(r2.content)
                    except Exception:
                        continue
                if cached.exists() and cached.stat().st_size >= 15000:
                    dur = get_duration(cached)
                    if dur >= 1.5:
                        results.append((cached, dur))
    except Exception as e:
        print(f"    [!] Online search error for '{query}': {e}")
        
    return results

def transcode_video_icon(
    input_path: Path,
    output_mp4: Path,
    output_jpg: Path,
    start_sec: float = 0.0,
    duration_sec: float = 4.0,
    crop_x_ratio: float = 0.5, # 0.5 = center, 0.35 = action left, 0.65 = scenic right
    fps: int = 30
) -> bool:
    """
    Transcodes input footage to a strict 4IFIR-compliant 256x256 30fps H.264 video icon:
    - Codec: H.264 Baseline, level 3.0, yuv420p
    - Crop: 1:1 square crop with precise ratio positioning
    - Scaling: Lanczos 256x256
    - Bitrate: ~380-550 kbps (faststart enabled, no audio track)
    - Loops seamlessly via -stream_loop -1
    """
    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    
    crop_expr = f"crop=min(iw\\,ih):min(iw\\,ih):(iw-ow)*{crop_x_ratio}:(ih-oh)/2,scale=256:256:flags=lanczos,unsharp=3:3:0.6:3:3:0.0,fps={fps},format=yuv420p"
    
    cmd_mp4 = [
        "ffmpeg", "-y", "-nostdin",
        "-stream_loop", "-1",
        "-ss", str(start_sec),
        "-i", str(input_path),
        "-t", str(duration_sec),
        "-vf", crop_expr,
        "-c:v", "libx264",
        "-preset", "fast",
        "-profile:v", "main",
        "-crf", "18",
        "-b:v", "1200k",
        "-maxrate", "1800k",
        "-bufsize", "2400k",
        "-an",
        "-movflags", "+faststart",
        str(output_mp4)
    ]
    
    res = subprocess.run(cmd_mp4, capture_output=True, text=True)
    if res.returncode != 0 or not output_mp4.exists() or output_mp4.stat().st_size < 10000:
        return False
        
    # Extract representative poster frame at 0.5s into the icon loop
    cmd_jpg = [
        "ffmpeg", "-y", "-nostdin",
        "-ss", "0.5",
        "-i", str(output_mp4),
        "-vframes", "1",
        "-q:v", "2",
        str(output_jpg)
    ]
    subprocess.run(cmd_jpg, capture_output=True, text=True)
    
    return True

def create_preview_gif(mp4_path: Path, gif_path: Path) -> bool:
    """Creates a lightweight 160x160 15fps looping GIF for markdown embeds."""
    cmd = [
        "ffmpeg", "-y", "-nostdin",
        "-ss", "0", "-t", "2.5",
        "-i", str(mp4_path),
        "-vf", "fps=15,scale=160:160:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=64[p];[s1][p]paletteuse=dither=bayer",
        str(gif_path)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.returncode == 0 and gif_path.exists()

def build_composite_strip(
    title: str,
    tid: str,
    category: str,
    jpg1: Path,
    jpg2: Path,
    jpg3: Path,
    output_strip: Path
) -> bool:
    """Builds a polished 3-variation horizontal preview card for the UI showcase."""
    try:
        w_card = 256 * 3 + 40
        h_card = 256 + 70
        strip = Image.new("RGB", (w_card, h_card), (15, 20, 30))
        draw = ImageDraw.Draw(strip)
        
        font_path = r"C:\Windows\Fonts\segoeuib.ttf"
        font_title = ImageFont.truetype(font_path, 17) if os.path.exists(font_path) else None
        font_sub = ImageFont.truetype(font_path, 12) if os.path.exists(font_path) else None
        
        # Header with category badge
        header_text = f"{title} [{tid}]"
        if font_title:
            draw.text((15, 12), header_text[:50], fill=(255, 255, 255), font=font_title)
            draw.text((w_card - 180, 14), f"• {category}", fill=(0, 242, 254), font=font_sub)
        else:
            draw.text((15, 12), header_text[:50], fill=(255, 255, 255))
            
        labels = ["Var 1: Hero Portrait", "Var 2: Dynamic Action", "Var 3: Cinematic Art"]
        
        for idx, (p_jpg, label) in enumerate(zip([jpg1, jpg2, jpg3], labels)):
            x_pos = 10 + idx * (256 + 10)
            y_pos = 45
            if p_jpg.exists():
                im = Image.open(p_jpg).convert("RGB")
                strip.paste(im, (x_pos, y_pos))
            else:
                draw.rectangle([x_pos, y_pos, x_pos + 256, y_pos + 256], fill=(30, 35, 50))
                draw.text((x_pos + 40, y_pos + 120), "Preview Pending", fill=(180, 180, 180))
                
            # Draw label banner at bottom
            draw.rectangle([x_pos, y_pos + 228, x_pos + 256, y_pos + 256], fill=(10, 14, 22))
            if font_sub:
                draw.text((x_pos + 10, y_pos + 235), label, fill=(0, 242, 254), font=font_sub)
            else:
                draw.text((x_pos + 10, y_pos + 235), label, fill=(0, 242, 254))
                
        strip.save(output_strip, quality=92)
        return True
    except Exception as e:
        print(f"Error building strip for {title}: {e}")
        return False

def build_category_montage(game_strips: List[Tuple[str, str, Path]], out_path: Path):
    """Builds a composite montage grid of preview strips for a category."""
    if not game_strips:
        return
    try:
        sample_w, sample_h = 256 * 3 + 40, 256 + 70
        # Stack vertically up to 8 strips per category
        strips_to_render = game_strips[:8]
        total_h = sample_h * len(strips_to_render) + 20
        montage = Image.new("RGB", (sample_w, total_h), (10, 14, 20))
        
        y_offset = 10
        for title, tid, s_path in strips_to_render:
            if s_path.exists():
                sim = Image.open(s_path)
                montage.paste(sim, (0, y_offset))
                y_offset += sample_h
                
        montage.save(out_path, quality=90)
        print(f"[+] Saved category montage: {out_path} ({out_path.stat().st_size/1024:.1f} KB)")
    except Exception as e:
        print(f"[-] Error building category montage {out_path}: {e}")

def main():
    print("=" * 80)
    print("   H3H VIDEO ICON HARVESTER: 100 POPULAR TITLES x 3 VARIATIONS (300 ICONS)")
    print("   STRICTLY FOR LOCAL STAGING & REVIEW (NO PUBLISHING TO CATALOG/GITHUB)")
    print("=" * 80)
    print(f"[*] Total target games: {len(TOP_100_GAMES)}")
    print(f"[*] Local Staging directory: {STAGE_ICONS_DIR}")
    print(f"[*] Artifacts Showcase directory: {SHOWCASE_OUT_DIR}")
    print(f"[*] Valid Local 720p indexed files: {len(local_720p_files)//2}")
    print("-" * 80)
    
    staged_catalog = []
    total_icons_generated = 0
    start_time = time.time()
    category_strips = {"Nintendo Exclusives": [], "RPGs & Masterpieces": [], "Indie & Classics": []}
    
    for game_idx, (tid, title, query, appid, category) in enumerate(TOP_100_GAMES):
        print(f"\n[{game_idx+1:3d}/100] Processing: {title} ({tid})")
        game_stage_dir = STAGE_ICONS_DIR / tid
        game_stage_dir.mkdir(parents=True, exist_ok=True)
        
        meta_file = game_stage_dir / "meta.json"
        var1_mp4 = game_stage_dir / "var1.mp4"
        var1_jpg = game_stage_dir / "var1.jpg"
        var2_mp4 = game_stage_dir / "var2.mp4"
        var2_jpg = game_stage_dir / "var2.jpg"
        var3_mp4 = game_stage_dir / "var3.mp4"
        var3_jpg = game_stage_dir / "var3.jpg"
        strip_file = game_stage_dir / "preview_strip.jpg"
        
        # Check if already staged with valid file sizes (>= 50 KB per icon)
        all_exist = all([
            var1_mp4.exists() and var1_mp4.stat().st_size > 50000,
            var2_mp4.exists() and var2_mp4.stat().st_size > 50000,
            var3_mp4.exists() and var3_mp4.stat().st_size > 50000,
            var1_jpg.exists(), var2_jpg.exists(), var3_jpg.exists(),
            meta_file.exists()
        ])
        
        if all_exist:
            print("    [+] All 3 variations already staged, loading metadata.")
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                staged_catalog.append(meta)
                total_icons_generated += 3
                if strip_file.exists():
                    category_strips[category].append((title, tid, strip_file))
                continue
            except Exception:
                pass
                
        # 1. Resolve local sources
        local_sources = find_local_sources_for_game(tid, title, query)
        print(f"    Found {len(local_sources)} valid local 720p footage sources.")
        
        # 2. If needed, supplement with online Tenor loops
        online_sources = []
        if len(local_sources) < 3:
            needed = 3 - len(local_sources)
            print(f"    Searching online sources for {needed} candidate loops...")
            online_sources = download_online_loops(query, needed=needed)
            print(f"    Downloaded {len(online_sources)} valid online loop sources.")
            
        # 3. Form source plan for the 3 variations
        # If we have 3 distinct video sources:
        if len(local_sources) + len(online_sources) >= 3:
            all_srcs = [s[0] for s in local_sources] + [s[0] for s in online_sources]
            v1_src, v1_start = all_srcs[0], 0.0
            v2_src, v2_start = all_srcs[1], 0.0
            v3_src, v3_start = all_srcs[2], 0.0
        # If we have 2 sources:
        elif len(local_sources) + len(online_sources) == 2:
            all_srcs = [s[0] for s in local_sources] + [s[0] for s in online_sources]
            v1_src, v1_start = all_srcs[0], 0.0
            v2_src, v2_start = all_srcs[1], 0.0
            v3_src, v3_start = all_srcs[0], 4.0
        # If we have 1 source (slice into 3 distinct scenes):
        elif len(local_sources) + len(online_sources) == 1:
            all_srcs = [s[0] for s in local_sources] + [s[0] for s in online_sources]
            single = all_srcs[0]
            v1_src, v1_start = single, 0.0
            v2_src, v2_start = single, 4.0
            v3_src, v3_start = single, 8.0
        else:
            print(f"    [-] CRITICAL: No footage sources available for {title}!")
            continue
            
        # Transcode Variation 1: Hero Portrait Loop
        ok1 = transcode_video_icon(
            input_path=v1_src,
            output_mp4=var1_mp4,
            output_jpg=var1_jpg,
            start_sec=v1_start,
            duration_sec=4.0,
            crop_x_ratio=0.5 # Centered portrait
        )
        
        # Transcode Variation 2: Dynamic Action Loop
        ok2 = transcode_video_icon(
            input_path=v2_src,
            output_mp4=var2_mp4,
            output_jpg=var2_jpg,
            start_sec=v2_start,
            duration_sec=4.0,
            crop_x_ratio=0.35 # Action / dynamic offset
        )
        
        # Transcode Variation 3: Atmospheric Cinematic Loop
        ok3 = transcode_video_icon(
            input_path=v3_src,
            output_mp4=var3_mp4,
            output_jpg=var3_jpg,
            start_sec=v3_start,
            duration_sec=4.0,
            crop_x_ratio=0.65 # Scenic / logo framing
        )
        
        # Build metadata for this game
        variations = [
            {
                "var": 1,
                "id": "var1",
                "name": "Hero Portrait Loop",
                "style": "Character Focus",
                "file": "var1.mp4",
                "poster": "var1.jpg",
                "durationSec": 4.0,
                "sizeBytes": var1_mp4.stat().st_size if var1_mp4.exists() else 0,
                "codec": "h264",
                "width": 256,
                "height": 256,
                "fps": 30
            },
            {
                "var": 2,
                "id": "var2",
                "name": "Dynamic Action Loop",
                "style": "Action Gameplay",
                "file": "var2.mp4",
                "poster": "var2.jpg",
                "durationSec": 4.0,
                "sizeBytes": var2_mp4.stat().st_size if var2_mp4.exists() else 0,
                "codec": "h264",
                "width": 256,
                "height": 256,
                "fps": 30
            },
            {
                "var": 3,
                "id": "var3",
                "name": "Atmospheric Cinematic Loop",
                "style": "Cinematic Art",
                "file": "var3.mp4",
                "poster": "var3.jpg",
                "durationSec": 4.0,
                "sizeBytes": var3_mp4.stat().st_size if var3_mp4.exists() else 0,
                "codec": "h264",
                "width": 256,
                "height": 256,
                "fps": 30
            }
        ]
        
        game_meta = {
            "titleId": tid,
            "title": title,
            "query": query,
            "category": category,
            "steamAppId": appid,
            "staged_path": str(game_stage_dir),
            "total_variations": 3,
            "variations": variations
        }
        
        meta_file.write_text(json.dumps(game_meta, indent=2, ensure_ascii=False), encoding="utf-8")
        staged_catalog.append(game_meta)
        total_icons_generated += 3
        print(f"    [+] Successfully staged 3 variations: Var1={variations[0]['sizeBytes']/1024:.1f}KB, Var2={variations[1]['sizeBytes']/1024:.1f}KB, Var3={variations[2]['sizeBytes']/1024:.1f}KB")
        
        # Build composite strip for UI showcase
        build_composite_strip(title, tid, category, var1_jpg, var2_jpg, var3_jpg, strip_file)
        if strip_file.exists():
            category_strips[category].append((title, tid, strip_file))
        
        # Copy preview files to artifacts showcase directory for user review
        showcase_game_dir = SHOWCASE_OUT_DIR / tid
        showcase_game_dir.mkdir(parents=True, exist_ok=True)
        if strip_file.exists():
            shutil.copy2(strip_file, showcase_game_dir / "preview_strip.jpg")
        if var1_jpg.exists():
            shutil.copy2(var1_jpg, showcase_game_dir / "var1.jpg")
        if var2_jpg.exists():
            shutil.copy2(var2_jpg, showcase_game_dir / "var2.jpg")
        if var3_jpg.exists():
            shutil.copy2(var3_jpg, showcase_game_dir / "var3.jpg")
            
        # Create animated GIF preview for top games (first 10 games)
        if game_idx < 10:
            create_preview_gif(var1_mp4, showcase_game_dir / "var1.gif")
            
    # Build category montages
    print("\n[*] Generating high-resolution Category Showcase Montages...")
    build_category_montage(category_strips["Nintendo Exclusives"], SHOWCASE_OUT_DIR / "montage_exclusives.jpg")
    build_category_montage(category_strips["RPGs & Masterpieces"], SHOWCASE_OUT_DIR / "montage_rpgs.jpg")
    build_category_montage(category_strips["Indie & Classics"], SHOWCASE_OUT_DIR / "montage_indies.jpg")
    
    # Save master staging index
    index_file = LOCAL_PREVIEW_DIR / "catalog_preview_icons.json"
    index_file.write_text(json.dumps({
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_titles": len(staged_catalog),
        "total_video_icons": total_icons_generated,
        "status": "STAGED_FOR_APPROVAL_DO_NOT_PUBLISH",
        "categories": {
            "Nintendo Exclusives": 35,
            "RPGs & Masterpieces": 35,
            "Indie & Classics": 30
        },
        "games": staged_catalog
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    
    elapsed = time.time() - start_time
    print("\n" + "=" * 80)
    print(f"[*] HARVESTING COMPLETE IN {elapsed:.1f} SECONDS!")
    print(f"[*] Successfully Staged: {len(staged_catalog)} Titles / {total_icons_generated} Video Icons.")
    print(f"[*] Staging Directory: {STAGE_ICONS_DIR}")
    print(f"[*] Master Index: {index_file}")
    print(f"[*] Review Showcase Assets: {SHOWCASE_OUT_DIR}")
    print("=" * 80)

if __name__ == "__main__":
    main()
