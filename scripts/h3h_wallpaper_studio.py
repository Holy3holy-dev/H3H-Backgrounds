"""
H3H Wallpaper Engine Studio & Pipeline.
Local visual dashboard and automated converter for Wallpaper Engine wallpapers.
Operates on drive H: for high performance and zero C: drive space consumption.
"""

import os
import sys
import re
import json
import uuid
import shutil
import subprocess
import threading
import mimetypes
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

# Path configuration
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "studio"))

from scripts.title_id_resolver import TitleIdResolver
from h3h_studio.core.google_drive import GoogleDriveHelper, GoogleDriveClient
from h3h_studio.core.github_publisher import GitHubPublisher
from tg_bot.config import (
    GDRIVE_FOLDER_ID,
    GDRIVE_AFTER_DARK_FOLDER_ID,
    GDRIVE_REFRESH_TOKEN,
    GITHUB_TOKEN,
    GITHUB_REPO,
    GITHUB_BRANCH,
    CATALOG_PATH_STANDARD,
    CATALOG_PATH_AFTER_DARK
)

STAGE_DIR = Path(r"H:\h3h_stage")
STAGE_RAW = STAGE_DIR / "raw"
STAGE_720P = STAGE_DIR / "720p"
STAGE_THUMBS = STAGE_DIR / "thumbs"
STAGE_WEB = STAGE_DIR / "web"

for p in [STAGE_DIR, STAGE_RAW, STAGE_720P, STAGE_THUMBS, STAGE_WEB]:
    p.mkdir(parents=True, exist_ok=True)

WE_WORKSHOP_PATH = Path(r"E:\SteamLibrary\steamapps\workshop\content\431960")
WE_EXE_PATH = Path(r"E:\SteamLibrary\steamapps\common\wallpaper_engine\launcher.exe")

resolver = TitleIdResolver(str(PROJECT_ROOT / CATALOG_PATH_STANDARD))

# Track active operations
active_tasks: Dict[str, Dict[str, Any]] = {}

def launch_wallpaper_engine() -> bool:
    """Launches Wallpaper Engine if not already running."""
    try:
        if WE_EXE_PATH.exists():
            subprocess.Popen([str(WE_EXE_PATH)])
            return True
        subprocess.Popen(["cmd", "/c", "start", "steam://rungameid/431960"])
        return True
    except Exception as e:
        print(f"[-] Error launching Wallpaper Engine: {e}")
        return False

def scan_wallpaper_engine_items() -> List[Dict[str, Any]]:
    """Scans Workshop directory for video wallpapers, metadata, and catalog status."""
    if not WE_WORKSHOP_PATH.exists():
        return []

    # Load existing catalogs to check if already published
    cat_std = json.loads((PROJECT_ROOT / CATALOG_PATH_STANDARD).read_text(encoding="utf-8")) if (PROJECT_ROOT / CATALOG_PATH_STANDARD).exists() else {}
    cat_ad = json.loads((PROJECT_ROOT / CATALOG_PATH_AFTER_DARK).read_text(encoding="utf-8")) if (PROJECT_ROOT / CATALOG_PATH_AFTER_DARK).exists() else {}

    std_variants = {v.get("name", "").lower(): v for g in cat_std.get("games", []) for v in g.get("variants", [])}
    ad_variants = {v.get("name", "").lower(): v for g in cat_ad.get("games", []) for v in g.get("variants", [])}

    results = []
    valid_vid_exts = {".mp4", ".webm"}

    for d in WE_WORKSHOP_PATH.iterdir():
        if not d.is_dir():
            continue
        p_json = d / "project.json"
        if not p_json.exists():
            continue

        try:
            info = json.loads(p_json.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            continue

        title = info.get("title", d.name)
        rating = info.get("contentrating", "Everyone")
        tags = info.get("tags", [])
        desc = info.get("description", "")

        vid_files = [f for f in d.iterdir() if f.is_file() and f.suffix.lower() in valid_vid_exts]
        if not vid_files:
            continue

        vid = vid_files[0]
        vid_size_mb = round(vid.stat().st_size / (1024 * 1024), 1)

        preview_file = None
        for cand in ["preview.jpg", "preview.gif", "preview.png"]:
            if (d / cand).exists():
                preview_file = str(d / cand)
                break

        # Auto-match game
        game_match = resolver.resolve(title)
        suggested_cat = "standard"
        if rating in ["Questionable", "Mature"] or any(t.lower() in ["anime", "girls", "mature", "ecchi"] for t in tags):
            suggested_cat = "after_dark"

        is_published = False
        published_cat = None
        if title.lower() in std_variants:
            is_published = True
            published_cat = "standard"
        elif title.lower() in ad_variants:
            is_published = True
            published_cat = "after_dark"

        results.append({
            "id": d.name,
            "title": title,
            "rating": rating,
            "tags": tags,
            "description": desc[:200] if desc else "",
            "video_path": str(vid),
            "video_filename": vid.name,
            "video_size_mb": vid_size_mb,
            "preview_path": preview_file,
            "game_match": {
                "title_id": game_match[0] if game_match else None,
                "game_name": game_match[1] if game_match else None
            } if game_match else None,
            "suggested_category": suggested_cat,
            "is_published": is_published,
            "published_category": published_cat
        })

    # Sort: unbaked/unpublished first, then by title
    results.sort(key=lambda x: (x["is_published"], x["title"].lower()))
    return results

def convert_and_publish_item(
    item_id: str,
    category: str,
    title_id: str,
    game_name: str,
    variant_name: str,
    author: str = "Wallpaper Engine",
    duration_sec: int = 25
) -> Dict[str, Any]:
    """Converts wallpaper to 720p on H: drive, uploads to GDrive, and updates catalog."""
    item_dir = WE_WORKSHOP_PATH / item_id
    if not item_dir.exists():
        raise FileNotFoundError(f"Item folder not found: {item_dir}")

    vid_files = [f for f in item_dir.iterdir() if f.is_file() and f.suffix.lower() in {".mp4", ".webm"}]
    if not vid_files:
        raise FileNotFoundError(f"No video found in {item_dir}")

    src_vid = vid_files[0]
    out_mp4 = STAGE_720P / f"{title_id}_{uuid.uuid4().hex[:6]}.mp4"
    out_thumb = STAGE_THUMBS / f"{title_id}_{uuid.uuid4().hex[:6]}.jpg"

    # Step 1: Transcode via FFmpeg on H: drive
    cmd_ffmpeg = [
        "ffmpeg", "-y",
        "-i", str(src_vid),
        "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:black",
        "-c:v", "libx264",
        "-profile:v", "high",
        "-level", "4.1",
        "-pix_fmt", "yuv420p",
        "-r", "30",
        "-b:v", "2500k",
        "-maxrate", "3000k",
        "-bufsize", "5000k",
        "-an",
        "-movflags", "+faststart",
        "-t", str(duration_sec),
        str(out_mp4)
    ]
    subprocess.run(cmd_ffmpeg, capture_output=True, check=True)

    # Step 2: Extract Thumbnail
    cmd_thumb = [
        "ffmpeg", "-y",
        "-ss", "2",
        "-i", str(out_mp4),
        "-vframes", "1",
        "-vf", "scale=640:360",
        "-f", "image2",
        str(out_thumb)
    ]
    subprocess.run(cmd_thumb, capture_output=True)

    # Step 3: Google Drive Upload
    gdrive_cfg = GoogleDriveHelper.get_stored_config()
    refresh_tok = os.getenv("GDRIVE_REFRESH_TOKEN") or GDRIVE_REFRESH_TOKEN or gdrive_cfg.get("refresh_token")
    access_tok = GoogleDriveHelper.refresh_access_token(refresh_tok) or gdrive_cfg.get("token")

    if category == "after_dark":
        folder_id = (
            os.getenv("GDRIVE_AFTER_DARK_FOLDER_ID")
            or GDRIVE_AFTER_DARK_FOLDER_ID
            or gdrive_cfg.get("after_dark_folder_id")
            or "1SXWjp12pKxPPT6YRMZ7tle8cgZdrKkHk"
        )
        target_catalog_rel = CATALOG_PATH_AFTER_DARK
    else:
        folder_id = (
            os.getenv("GDRIVE_FOLDER_ID")
            or GDRIVE_FOLDER_ID
            or gdrive_cfg.get("project_folder_id")
            or gdrive_cfg.get("folder_id")
            or "1hI1klJ6t2ymVoBwGA6IzY79QMjp5dTJC"
        )
        target_catalog_rel = CATALOG_PATH_STANDARD

    upload_res = GoogleDriveClient.upload_file(
        file_path=out_mp4,
        folder_id=folder_id,
        token=access_tok
    )

    direct_url = upload_res.get("directUrl")
    preview_url = upload_res.get("previewUrl")
    file_size = upload_res.get("size", out_mp4.stat().st_size)

    # Step 4: Register in catalog
    target_catalog_path = PROJECT_ROOT / target_catalog_rel
    cat_data = json.loads(target_catalog_path.read_text(encoding="utf-8"))
    games_list = cat_data.get("games", [])

    game_entry = None
    for g in games_list:
        if g.get("titleId", "").upper() == title_id.upper():
            game_entry = g
            break

    if not game_entry:
        game_entry = {
            "titleId": title_id.upper(),
            "title": game_name,
            "publisher": "Wallpaper Engine Community",
            "variants": []
        }
        games_list.append(game_entry)

    var_id = f"var-{uuid.uuid4().hex[:8]}"
    new_var = {
        "id": var_id,
        "name": variant_name,
        "style": "Wallpaper Engine Animated" if category == "standard" else "After Dark (18+)",
        "version": "1.0",
        "url": direct_url,
        "previewUrl": preview_url,
        "sizeBytes": file_size,
        "sha256": "",
        "durationSec": float(duration_sec),
        "author": author,
        "codec": "h264",
        "width": 1280,
        "height": 720,
        "fps": 30.0,
        "hasAudio": False,
        "notes": f"Imported from Wallpaper Engine ({item_id})"
    }
    game_entry["variants"].append(new_var)

    cat_data["totalGames"] = len(games_list)
    cat_data["totalVariants"] = sum(len(g.get("variants", [])) for g in games_list)
    cat_data["lastUpdated"] = datetime.now(timezone.utc).isoformat()
    target_catalog_path.write_text(json.dumps(cat_data, indent=2, ensure_ascii=False), encoding="utf-8")

    # Step 5: Git commit & push
    gh_token, _ = GitHubPublisher.get_stored_credentials()
    if not gh_token:
        gh_token = os.getenv("GITHUB_TOKEN") or GITHUB_TOKEN
    if gh_token:
        repo_name = GITHUB_REPO or GitHubPublisher.get_repo_name()
        repo_url = f"https://x-access-token:{gh_token}@github.com/{repo_name}.git"
        commit_msg = f"feat(catalog): import '{variant_name}' ({title_id}) from Wallpaper Engine ({category})"
        subprocess.run(["git", "-C", str(PROJECT_ROOT), "add", str(target_catalog_rel)], check=True)
        subprocess.run(["git", "-C", str(PROJECT_ROOT), "commit", "-m", commit_msg], check=True)
        subprocess.run(["git", "-C", str(PROJECT_ROOT), "push", repo_url, GITHUB_BRANCH], check=True)

    return {
        "success": True,
        "variantId": var_id,
        "directUrl": direct_url,
        "previewUrl": preview_url,
        "catalog": str(target_catalog_rel)
    }

# --- HTTP Request Handler ---

HTML_DASHBOARD = """<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <title>H3H Wallpaper Engine Studio (Drive H:)</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg-dark: #07090E;
      --card-bg: rgba(15, 23, 42, 0.75);
      --card-border: rgba(255, 255, 255, 0.08);
      --cyan: #00F0FF;
      --magenta: #FF2E93;
      --purple: #A855F7;
      --text: #F1F5F9;
      --muted: #94A3B8;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg-dark);
      color: var(--text);
      font-family: 'Inter', sans-serif;
      min-height: 100vh;
      padding: 24px;
      background-image: 
        radial-gradient(ellipse at 15% 10%, rgba(0, 240, 255, 0.08) 0%, transparent 50%),
        radial-gradient(ellipse at 85% 20%, rgba(255, 46, 147, 0.09) 0%, transparent 50%);
    }
    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 24px;
      padding-bottom: 20px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 16px;
    }
    .badge-h {
      background: linear-gradient(135deg, var(--cyan), var(--magenta));
      color: #000;
      font-weight: 800;
      font-size: 13px;
      padding: 6px 12px;
      border-radius: 8px;
      letter-spacing: 0.5px;
    }
    h1 {
      font-size: 24px;
      font-weight: 800;
      letter-spacing: -0.5px;
    }
    .btn {
      background: rgba(255, 255, 255, 0.06);
      border: 1px solid rgba(255, 255, 255, 0.15);
      color: #fff;
      padding: 10px 18px;
      border-radius: 8px;
      font-weight: 600;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      transition: all 0.2s;
    }
    .btn:hover {
      background: rgba(255, 255, 255, 0.12);
      transform: translateY(-1px);
    }
    .btn-we {
      background: linear-gradient(135deg, #1E3A8A, #3B82F6);
      border: none;
      box-shadow: 0 4px 15px rgba(59, 130, 246, 0.3);
    }
    .btn-we:hover {
      box-shadow: 0 6px 20px rgba(59, 130, 246, 0.5);
    }
    .filter-bar {
      display: flex;
      gap: 10px;
      margin-bottom: 24px;
      flex-wrap: wrap;
    }
    .filter-btn {
      background: rgba(255, 255, 255, 0.04);
      border: 1px solid rgba(255, 255, 255, 0.08);
      color: var(--muted);
      padding: 8px 16px;
      border-radius: 6px;
      font-size: 13px;
      cursor: pointer;
      transition: all 0.15s;
    }
    .filter-btn.active, .filter-btn:hover {
      background: rgba(255, 255, 255, 0.1);
      color: #fff;
      border-color: rgba(255, 255, 255, 0.2);
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 20px;
    }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      backdrop-filter: blur(16px);
      transition: transform 0.2s, border-color 0.2s;
    }
    .card:hover {
      transform: translateY(-3px);
      border-color: rgba(255, 255, 255, 0.2);
    }
    .card-thumb-wrap {
      width: 100%;
      height: 180px;
      background: #000;
      position: relative;
      overflow: hidden;
    }
    .card-thumb {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }
    .card-video {
      position: absolute;
      top: 0; left: 0;
      width: 100%; height: 100%;
      object-fit: cover;
      display: none;
    }
    .card-thumb-wrap:hover .card-video {
      display: block;
    }
    .rating-badge {
      position: absolute;
      top: 10px; right: 10px;
      padding: 4px 8px;
      border-radius: 6px;
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
    }
    .rating-mature { background: rgba(255, 46, 147, 0.85); color: #fff; }
    .rating-everyone { background: rgba(16, 185, 129, 0.85); color: #fff; }
    .status-badge {
      position: absolute;
      top: 10px; left: 10px;
      padding: 4px 8px;
      border-radius: 6px;
      font-size: 11px;
      font-weight: 700;
      background: rgba(0, 240, 255, 0.85);
      color: #000;
    }
    .card-body {
      padding: 16px;
      display: flex;
      flex-direction: column;
      flex: 1;
      gap: 10px;
    }
    .card-title {
      font-size: 15px;
      font-weight: 700;
      line-height: 1.3;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .card-meta {
      font-size: 12px;
      color: var(--muted);
      display: flex;
      justify-content: space-between;
    }
    .match-box {
      background: rgba(0, 0, 0, 0.35);
      padding: 8px 12px;
      border-radius: 8px;
      border: 1px dashed rgba(255, 255, 255, 0.1);
      font-size: 12px;
    }
    .match-label {
      color: var(--cyan);
      font-weight: 600;
      margin-bottom: 2px;
    }
    .match-ad {
      color: var(--magenta);
    }
    .card-actions {
      margin-top: auto;
      display: flex;
      gap: 8px;
      padding-top: 10px;
    }
    .btn-action {
      flex: 1;
      font-size: 12px;
      padding: 8px 10px;
      border-radius: 6px;
      border: none;
      font-weight: 700;
      cursor: pointer;
      text-align: center;
      transition: all 0.15s;
    }
    .btn-std {
      background: rgba(0, 240, 255, 0.15);
      color: var(--cyan);
      border: 1px solid rgba(0, 240, 255, 0.3);
    }
    .btn-std:hover {
      background: var(--cyan);
      color: #000;
    }
    .btn-ad {
      background: rgba(255, 46, 147, 0.15);
      color: var(--magenta);
      border: 1px solid rgba(255, 46, 147, 0.3);
    }
    .btn-ad:hover {
      background: var(--magenta);
      color: #fff;
    }
    .toast {
      position: fixed;
      bottom: 24px; right: 24px;
      background: #1E293B;
      color: #fff;
      padding: 14px 22px;
      border-radius: 8px;
      border: 1px solid var(--cyan);
      box-shadow: 0 10px 25px rgba(0, 0, 0, 0.5);
      display: none;
      z-index: 1000;
      font-size: 14px;
    }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <span class="badge-h">DRIVE H: STAGE</span>
      <div>
        <h1>H3H Wallpaper Engine Studio</h1>
        <p style="color: var(--muted); font-size: 13px;">Интерактивный центр публикации видеофонов в Switch-каталоги</p>
      </div>
    </div>
    <div style="display: flex; gap: 10px;">
      <button class="btn btn-we" onclick="launchWE()">🚀 Запустить Wallpaper Engine</button>
      <button class="btn" onclick="fetchWallpapers()">🔄 Обновить список</button>
    </div>
  </header>

  <div class="filter-bar">
    <button class="filter-btn active" onclick="setFilter('all', this)">Все обои (<span id="cnt-all">0</span>)</button>
    <button class="filter-btn" onclick="setFilter('unpub', this)">✨ Неопубликованные (<span id="cnt-unpub">0</span>)</button>
    <button class="filter-btn" onclick="setFilter('games', this)">🎮 Игры Switch (<span id="cnt-games">0</span>)</button>
    <button class="filter-btn" onclick="setFilter('after_dark', this)">🌸 After Dark 18+ (<span id="cnt-ad">0</span>)</button>
    <button class="filter-btn" onclick="setFilter('pub', this)">✅ Опубликованные (<span id="cnt-pub">0</span>)</button>
  </div>

  <div class="grid" id="grid"></div>

  <div class="toast" id="toast"></div>

  <script>
    let allItems = [];
    let currentFilter = 'all';

    function showToast(msg, isError=false) {
      const t = document.getElementById('toast');
      t.style.display = 'block';
      t.style.borderColor = isError ? '#EF4444' : '#00F0FF';
      t.innerText = msg;
      setTimeout(() => { t.style.display = 'none'; }, 4000);
    }

    async function launchWE() {
      showToast('Запускаю Wallpaper Engine...');
      try {
        const res = await fetch('/api/launch_we', { method: 'POST' });
        const data = await res.json();
        if (data.success) {
          showToast('Wallpaper Engine успешно запущен!');
        }
      } catch (e) {
        showToast('Ошибка запуска: ' + e, true);
      }
    }

    async function fetchWallpapers() {
      try {
        const res = await fetch('/api/wallpapers');
        allItems = await res.json();
        updateCounts();
        renderGrid();
      } catch (e) {
        showToast('Ошибка загрузки списка: ' + e, true);
      }
    }

    function updateCounts() {
      document.getElementById('cnt-all').innerText = allItems.length;
      document.getElementById('cnt-unpub').innerText = allItems.filter(x => !x.is_published).length;
      document.getElementById('cnt-games').innerText = allItems.filter(x => x.game_match).length;
      document.getElementById('cnt-ad').innerText = allItems.filter(x => x.suggested_category === 'after_dark').length;
      document.getElementById('cnt-pub').innerText = allItems.filter(x => x.is_published).length;
    }

    function setFilter(filter, btn) {
      currentFilter = filter;
      document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      renderGrid();
    }

    function renderGrid() {
      const grid = document.getElementById('grid');
      grid.innerHTML = '';

      let filtered = allItems;
      if (currentFilter === 'unpub') filtered = allItems.filter(x => !x.is_published);
      if (currentFilter === 'games') filtered = allItems.filter(x => x.game_match);
      if (currentFilter === 'after_dark') filtered = allItems.filter(x => x.suggested_category === 'after_dark');
      if (currentFilter === 'pub') filtered = allItems.filter(x => x.is_published);

      filtered.forEach(item => {
        const card = document.createElement('div');
        card.className = 'card';

        const thumbSrc = item.preview_path ? `/preview/${item.id}` : '';
        const videoSrc = `/video/${item.id}`;

        const isMature = item.rating === 'Mature' || item.rating === 'Questionable';
        const ratingClass = isMature ? 'rating-mature' : 'rating-everyone';

        let matchHtml = '';
        if (item.game_match) {
          matchHtml = `
            <div class="match-box">
              <div class="match-label">🎮 Определена игра:</div>
              <div><b>${item.game_match.game_name}</b></div>
              <div style="font-family: monospace; color: #94A3B8; font-size: 11px;">ID: ${item.game_match.title_id}</div>
            </div>
          `;
        } else if (item.suggested_category === 'after_dark') {
          matchHtml = `
            <div class="match-box">
              <div class="match-label match-ad">🌸 After Dark (Свободный выбор):</div>
              <div>Любая игра на Switch</div>
              <div style="font-family: monospace; color: #94A3B8; font-size: 11px;">ID: 0000000000000000</div>
            </div>
          `;
        } else {
          matchHtml = `
            <div class="match-box">
              <div class="match-label">✨ Свободный арт:</div>
              <div>Универсальный видеофон</div>
              <div style="font-family: monospace; color: #94A3B8; font-size: 11px;">ID: 0000000000000000</div>
            </div>
          `;
        }

        let statusBadge = '';
        if (item.is_published) {
          statusBadge = `<div class="status-badge">✅ В каталоге (${item.published_category})</div>`;
        }

        card.innerHTML = `
          <div class="card-thumb-wrap">
            ${statusBadge}
            <div class="rating-badge ${ratingClass}">${item.rating}</div>
            ${thumbSrc ? `<img class="card-thumb" src="${thumbSrc}" loading="lazy">` : ''}
            <video class="card-video" src="${videoSrc}" loop muted onmouseover="this.play()" onmouseout="this.pause()"></video>
          </div>
          <div class="card-body">
            <div class="card-title" title="${item.title}">${item.title}</div>
            <div class="card-meta">
              <span>📁 ${item.video_filename}</span>
              <span>💾 ${item.video_size_mb} MB</span>
            </div>
            ${matchHtml}
            <div class="card-actions">
              <button class="btn-action btn-std" onclick="publishItem('${item.id}', 'standard')">🎮 В Обычный</button>
              <button class="btn-action btn-ad" onclick="publishItem('${item.id}', 'after_dark')">🌸 В After Dark</button>
            </div>
          </div>
        `;
        grid.appendChild(card);
      });
    }

    async function publishItem(itemId, category) {
      const item = allItems.find(x => x.id === itemId);
      if (!item) return;

      const titleId = (item.game_match && category === 'standard') ? item.game_match.title_id : '0000000000000000';
      const gameName = (item.game_match && category === 'standard') ? item.game_match.game_name : '★ Коллекция After Dark (Свободный выбор)';
      const variantName = item.title;

      showToast(`⏳ Конвертация 720p на диске H: и отправка в Google Drive (${category})...`);

      try {
        const res = await fetch('/api/publish', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            workshop_id: itemId,
            category: category,
            title_id: titleId,
            game_name: gameName,
            variant_name: variantName
          })
        });
        const data = await res.json();
        if (data.success) {
          showToast(`🎉 Успешно опубликовано: «${variantName}»! Каталог на GitHub обновлён.`);
          fetchWallpapers();
        } else {
          showToast('Ошибка публикации: ' + data.error, true);
        }
      } catch (e) {
        showToast('Сбой запроса: ' + e, true);
      }
    }

    // Auto-fetch on load
    fetchWallpapers();
  </script>
</body>
</html>
"""

class StudioHTTPHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ["/", "/index.html"]:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_DASHBOARD.encode("utf-8"))
            return

        if path == "/api/wallpapers":
            items = scan_wallpaper_engine_items()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(items, ensure_ascii=False).encode("utf-8"))
            return

        if path.startswith("/preview/"):
            workshop_id = path.split("/")[2]
            item_dir = WE_WORKSHOP_PATH / workshop_id
            preview_file = None
            for cand in ["preview.jpg", "preview.gif", "preview.png"]:
                if (item_dir / cand).exists():
                    preview_file = item_dir / cand
                    break
            if preview_file and preview_file.exists():
                mime, _ = mimetypes.guess_type(str(preview_file))
                self.send_response(200)
                self.send_header("Content-Type", mime or "image/jpeg")
                self.end_headers()
                self.wfile.write(preview_file.read_bytes())
                return
            self.send_error(404, "Preview not found")
            return

        if path.startswith("/video/"):
            workshop_id = path.split("/")[2]
            item_dir = WE_WORKSHOP_PATH / workshop_id
            vid_files = [f for f in item_dir.iterdir() if f.is_file() and f.suffix.lower() in {".mp4", ".webm"}] if item_dir.exists() else []
            if vid_files:
                vid = vid_files[0]
                mime, _ = mimetypes.guess_type(str(vid))
                self.send_response(200)
                self.send_header("Content-Type", mime or "video/mp4")
                self.send_header("Content-Length", str(vid.stat().st_size))
                self.end_headers()
                with open(vid, "rb") as vf:
                    shutil.copyfileobj(vf, self.wfile)
                return
            self.send_error(404, "Video not found")
            return

        self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/launch_we":
            success = launch_wallpaper_engine()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": success}).encode("utf-8"))
            return

        if path == "/api/publish":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body.decode("utf-8"))
                res = convert_and_publish_item(
                    item_id=data["workshop_id"],
                    category=data.get("category", "standard"),
                    title_id=data.get("title_id", "0000000000000000"),
                    game_name=data.get("game_name", "Community Theme"),
                    variant_name=data.get("variant_name", "Theme")
                )
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}, ensure_ascii=False).encode("utf-8"))
            return

        self.send_error(404, "Not Found")

    def log_message(self, format, *args):
        pass

def run_server(port: int = 8090):
    server = HTTPServer(("127.0.0.1", port), StudioHTTPHandler)
    print(f"[*] H3H Wallpaper Engine Studio running on http://localhost:{port}")
    print(f"[*] Staging directory: {STAGE_DIR}")
    server.serve_forever()

if __name__ == "__main__":
    run_server()
