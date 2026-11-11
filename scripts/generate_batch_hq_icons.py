"""
Пакетный генератор видеоиконок 4IFIR стандарта Ultra-HQ 256x256 v2.

Ключевые улучшения качества v2:
- Разрешение: 256x256 (1:1 квадрат для меню Horizon OS)
- Умный выбор сцены (Smart Scene Picker): анализ 3 точек ролика (22%, 48%, 72%), защита от черных фейд-инов и пустых плашек
- Масштабирование и резкость: Lanczos (accurate_rnd + full_chroma_int) + CAS 0.45 (Contrast Adaptive Sharpen) + легкий микроконтраст
- Бесшовный цикл 5.0 сек (xfade 0.5 сек между хвостом и началом — без рывка при повторе)
- Кодек: H.264 High Profile @ Level 4.1, preset slow, честный CRF 15 (maxrate 2.8M, bufsize 5.6M), 30 FPS, без аудио
- Приоритет:
  1) Апгрейд старых мыльных иконок (< 240 КБ) при наличии HD-исходника
  2) Мгновенная генерация новых иконок из локального архива H:\\h3h_stage\\720p
  3) Докачка 720p исходников из облака для остальных игр
- По умолчанию работает в локальном режиме тестирования (БЕЗ git commit / git push в GitHub!).
"""

import os
import sys
import json
import time
import math
import shutil
import argparse
import subprocess
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "studio"))

from tg_bot.bot import get_gdrive_auth
from tg_bot.config import GDRIVE_ICONS_FOLDER_ID, GDRIVE_AFTER_DARK_FOLDER_ID, detect_local_proxy
from h3h_studio.core.google_drive import GoogleDriveClient
from h3h_studio.core.github_publisher import GitHubPublisher

STAGE_ROOT_DIR = Path(r"H:\h3h_stage")
STAGE_720P_DIR = Path(r"H:\h3h_stage\720p")
TMP_ICONS_DIR = PROJECT_ROOT / "tmp" / "batch_hq_icons"
TMP_ICONS_DIR.mkdir(parents=True, exist_ok=True)
CATALOG_PATH = PROJECT_ROOT / "catalog" / "data" / "catalog.json"
AFTER_DARK_CATALOG_PATH = PROJECT_ROOT / "catalog" / "data" / "catalog_after_dark.json"
ROMFS_CATALOG_PATH = PROJECT_ROOT / "downloader" / "romfs" / "catalog.json"

LOW_QUALITY_THRESHOLD_BYTES = 240_000


def probe_video_duration(src_video: Path) -> float:
    """Возвращает длительность исходного видео в секундах."""
    try:
        res = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(src_video),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if res.returncode == 0 and res.stdout.strip():
            val = float(res.stdout.strip())
            if math.isfinite(val) and val > 0.5:
                return val
    except Exception:
        pass
    return 10.0


def score_frame_at(src_video: Path, timestamp_sec: float) -> float:
    """Оценивает визуальную насыщенность и контраст кадра 48x48 RGB, штрафуя темные фейды и засветы."""
    try:
        res = subprocess.run(
            [
                "ffmpeg", "-v", "error", "-nostdin",
                "-ss", f"{max(0.0, timestamp_sec):.2f}",
                "-i", str(src_video),
                "-frames:v", "1",
                "-vf", "crop=min(iw\\,ih):min(iw\\,ih),scale=48:48:flags=fast_bilinear,format=rgb24",
                "-f", "rawvideo", "pipe:1",
            ],
            capture_output=True,
            timeout=8,
        )
        buf = res.stdout
        if len(buf) < 48 * 48 * 3:
            return 0.0

        lum_vals = []
        sat_sum = 0.0
        n = 48 * 48
        for i in range(0, n * 3, 3):
            r, g, b = buf[i], buf[i + 1], buf[i + 2]
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            lum_vals.append(lum)
            mx = max(r, g, b)
            mn = min(r, g, b)
            sat_sum += (mx - mn)

        mean_lum = sum(lum_vals) / n
        # Штраф за слишком темный экран (< 26) или белый засвет (> 232)
        if mean_lum < 18.0 or mean_lum > 240.0:
            lum_penalty = 0.25
        elif mean_lum < 34.0 or mean_lum > 220.0:
            lum_penalty = 0.65
        else:
            lum_penalty = 1.0

        variance = sum((x - mean_lum) ** 2 for x in lum_vals) / n
        std_contrast = math.sqrt(variance)
        mean_sat = sat_sum / n

        return (std_contrast * 1.4 + mean_sat * 0.65) * lum_penalty
    except Exception:
        return 0.0


def pick_best_scene_time(src_video: Path, clip_need_sec: float = 5.5) -> Tuple[float, float]:
    """Подбирает лучший таймкод старта и возвращает (best_start_sec, total_duration_sec)."""
    dur = probe_video_duration(src_video)
    max_start = max(0.0, dur - clip_need_sec - 0.15)
    if max_start <= 0.4:
        return 0.0, dur

    probe_fracs = [0.22, 0.48, 0.72]
    best_t = min(1.2, max_start)
    best_score = -1.0
    for frac in probe_fracs:
        cand_t = min(max_start, max(0.3, dur * frac))
        sc = score_frame_at(src_video, cand_t)
        if sc > best_score:
            best_score = sc
            best_t = cand_t
    return round(best_t, 2), dur


def find_source_video(title_id: str, game_variants: list, local_files_map: dict) -> Optional[Path]:
    tid_lower = title_id.lower()
    candidates = [
        f"{tid_lower}.mp4",
        f"{tid_lower}_expand.mp4",
        f"{tid_lower}_variant.mp4",
        f"{tid_lower}_1.mp4",
        f"{tid_lower}_2.mp4",
        f"{tid_lower}_cover.mp4",
    ]
    for c in candidates:
        if c in local_files_map:
            return local_files_map[c]

    for v in game_variants:
        vid = (v.get("id") or "").lower()
        if not vid or vid.startswith("icon-"):
            continue
        for ext in [".mp4", "_expand.mp4"]:
            v_cand = f"{vid}{ext}"
            if v_cand in local_files_map:
                return local_files_map[v_cand]
    return None


def download_full_video(url: str, dest_path: Path) -> bool:
    try:
        import requests
        with requests.get(url, stream=True, timeout=28) as r:
            if r.status_code == 200:
                with open(dest_path, "wb") as f_out:
                    for chunk in r.iter_content(chunk_size=512 * 1024):
                        if chunk:
                            f_out.write(chunk)
                return dest_path.exists() and dest_path.stat().st_size >= 100_000
    except Exception as e:
        print(f"    [!] Ошибка скачивания исходника: {e}")
    return False


def transcode_ultra_hq_icon(src_video: Path, out_mp4: Path, target_loop_sec: float = 5.0) -> Tuple[bool, float]:
    """Кодирует бесшовную 256x256 Ultra-HQ видеоиконку (Lanczos + CAS 0.45 + xfade + High@Slow CRF 15)."""
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    xfade_dur = 0.5
    raw_need = target_loop_sec + xfade_dur
    start_sec, total_dur = pick_best_scene_time(src_video, clip_need_sec=raw_need)

    base_chain = (
        "crop=min(iw\\,ih):min(iw\\,ih):(iw-ow)*0.5:(ih-oh)/2,"
        "scale=256:256:flags=lanczos+accurate_rnd+full_chroma_int,"
        "cas=0.45,"
        "eq=saturation=1.08:contrast=1.03,"
        "fps=30,setpts=PTS-STARTPTS"
    )

    use_seamless = total_dur >= (raw_need + 0.2)
    if use_seamless:
        offset_sec = round(target_loop_sec - xfade_dur, 2)
        filter_complex = (
            f"[0:v]{base_chain},split=2[main][pre];"
            f"[main]trim=start={xfade_dur}:end={raw_need},setpts=PTS-STARTPTS[body];"
            f"[pre]trim=start=0:end={xfade_dur},setpts=PTS-STARTPTS[head];"
            f"[body][head]xfade=transition=fade:duration={xfade_dur}:offset={offset_sec},format=yuv420p[outv]"
        )
        cmd = [
            "ffmpeg", "-y", "-nostdin",
            "-ss", f"{start_sec:.2f}",
            "-t", f"{raw_need:.2f}",
            "-i", str(src_video),
            "-filter_complex", filter_complex,
            "-map", "[outv]",
            "-c:v", "libx264",
            "-preset", "slow",
            "-profile:v", "high",
            "-level:v", "4.1",
            "-crf", "15",
            "-maxrate", "2800k",
            "-bufsize", "5600k",
            "-g", "30",
            "-keyint_min", "15",
            "-pix_fmt", "yuv420p",
            "-an",
            "-movflags", "+faststart",
            str(out_mp4),
        ]
        final_dur = target_loop_sec
    else:
        actual_dur = round(min(target_loop_sec, max(2.5, total_dur - 0.1)), 2)
        cmd = [
            "ffmpeg", "-y", "-nostdin",
            "-ss", f"{start_sec:.2f}",
            "-t", f"{actual_dur:.2f}",
            "-i", str(src_video),
            "-vf", f"{base_chain},format=yuv420p",
            "-c:v", "libx264",
            "-preset", "slow",
            "-profile:v", "high",
            "-level:v", "4.1",
            "-crf", "15",
            "-maxrate", "2800k",
            "-bufsize", "5600k",
            "-g", "30",
            "-keyint_min", "15",
            "-pix_fmt", "yuv420p",
            "-an",
            "-movflags", "+faststart",
            str(out_mp4),
        ]
        final_dur = actual_dur

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        err_tail = "\n".join(res.stderr.splitlines()[-6:])
        print(f"    [!] FFmpeg ошибка ({res.returncode}):\n{err_tail}")
        return False, 0.0

    ok = out_mp4.exists() and out_mp4.stat().st_size >= 60_000
    return ok, final_dur


def process_one_candidate(
    item: Tuple[int, int, Dict[str, Any], str, Optional[Path]],
    token: str,
    target_folder_id: str = GDRIVE_ICONS_FOLDER_ID,
) -> Optional[Dict[str, Any]]:
    idx, total, game, mode_tag, local_src = item
    tid = game["titleId"].upper()
    title = game.get("title", tid)
    temp_src = None
    src_file = local_src

    try:
        if not src_file:
            cover_vars = [
                v for v in game.get("variants", [])
                if not str(v.get("id", "")).startswith("icon-") and v.get("width", 1280) != 256
            ]
            if not cover_vars:
                return None
            var_url = cover_vars[0].get("url")
            if not var_url:
                return None
            temp_src = TMP_ICONS_DIR / f"{tid}_src.mp4"
            if not download_full_video(var_url, temp_src):
                return None
            src_file = temp_src

        out_icon_mp4 = TMP_ICONS_DIR / f"{tid}_ultrahq.mp4"
        ok, final_dur = transcode_ultra_hq_icon(src_file, out_icon_mp4, target_loop_sec=5.0)
        if not ok or not out_icon_mp4.exists():
            return None

        icon_size = out_icon_mp4.stat().st_size
        upload_res = GoogleDriveClient.upload_file(out_icon_mp4, target_folder_id, token)
        direct_url = upload_res.get("directUrl")
        if not direct_url:
            print(f"  [-] [{idx}/{total}] Пустой URL загрузки для {title}")
            return None

        print(
            f"  [OK] [{idx}/{total}] ({mode_tag}) {title} [{tid}] -> "
            f"{icon_size // 1024} KB Ultra-HQ ({final_dur:.1f}s) | {direct_url}"
        )
        return {
            "titleId": tid,
            "mode": mode_tag,
            "directUrl": direct_url,
            "iconSize": icon_size,
            "durationSec": final_dur,
        }
    except Exception as e:
        print(f"  [-] [{idx}/{total}] Сбой обработки {title} [{tid}]: {e}")
        return None
    finally:
        if temp_src and temp_src.exists():
            try:
                temp_src.unlink()
            except Exception:
                pass
        out_cand = TMP_ICONS_DIR / f"{tid}_ultrahq.mp4"
        if out_cand.exists():
            try:
                out_cand.unlink()
            except Exception:
                pass


def sync_local_catalog_outputs(cat_data: dict, target_cat_path: Path = CATALOG_PATH) -> None:
    """Сохраняет целевой каталог, собирает сжатые .min.json(.gz) и обновляет встроенные romfs обоих изданий."""
    cat_data["totalGames"] = len(cat_data["games"])
    cat_data["totalVariants"] = sum(len(g.get("variants", [])) for g in cat_data["games"])
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    cat_data["updatedAt"] = now_iso
    cat_data["lastUpdated"] = now_iso

    with open(target_cat_path, "w", encoding="utf-8") as f:
        json.dump(cat_data, f, indent=2, ensure_ascii=False)

    subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "build_min_catalog.py")],
        check=False,
    )


def run_batch(
    batch_size: int = 40,
    workers: int = 4,
    upgrade_lowq: bool = True,
    allow_remote_download: bool = False,
    push_github: bool = False,
    edition: str = "main",
) -> Tuple[int, int]:
    is_after_dark = edition.strip().lower() in ("after-dark", "after_dark", "afterdark", "ad")
    active_cat_path = AFTER_DARK_CATALOG_PATH if is_after_dark else CATALOG_PATH
    gdrive_folder = GDRIVE_AFTER_DARK_FOLDER_ID if is_after_dark else GDRIVE_ICONS_FOLDER_ID

    print("=" * 72)
    print(
        f"[*] H3H Ultra-HQ 256x256 v2 Icon Generator [{edition.upper()}] "
        f"(batch={batch_size}, workers={workers}, push_github={push_github})"
    )
    print("=" * 72)

    token, _ = get_gdrive_auth("after_dark" if is_after_dark else "standard")
    if not token:
        print("[-] Не удалось получить токен Google Drive")
        return 0, 0

    local_files_map: Dict[str, Path] = {}
    scan_root = STAGE_ROOT_DIR if STAGE_ROOT_DIR.exists() else STAGE_720P_DIR
    if scan_root.exists():
        for f in scan_root.rglob("*.mp4"):
            try:
                if f.stat().st_size >= 100_000:
                    local_files_map[f.name.lower()] = f
            except Exception:
                pass
    print(f"[*] Локальных 720p HD-исходников в {scan_root}: {len(local_files_map)}")

    cat_data = json.loads(active_cat_path.read_text(encoding="utf-8"))
    games = cat_data.get("games", [])
    games_by_tid = {g.get("titleId", "").upper(): g for g in games if g.get("titleId")}

    upgrade_queue: List[Tuple[Dict[str, Any], str, Optional[Path]]] = []
    new_local_queue: List[Tuple[Dict[str, Any], str, Optional[Path]]] = []
    new_remote_queue: List[Tuple[Dict[str, Any], str, Optional[Path]]] = []

    for g in games:
        tid = g.get("titleId", "").upper()
        if not tid or (tid == "0000000000000000" and not is_after_dark):
            continue
        variants = g.get("variants", [])
        if not variants:
            continue

        icon_vars = [v for v in variants if v.get("hasIcon") and v.get("iconUrl")]
        src_local = find_source_video(tid, variants, local_files_map)

        if icon_vars:
            if upgrade_lowq:
                max_ico_sz = max(
                    int(v.get("iconSizeBytes") or v.get("sizeBytes") or 0)
                    for v in icon_vars
                )
                already_v2 = any("Ultra-HQ v2" in str(v.get("notes", "")) for v in variants)
                if not already_v2 and 0 <= max_ico_sz < LOW_QUALITY_THRESHOLD_BYTES:
                    if src_local is not None:
                        upgrade_queue.append((g, "UPGRADE-HQ", src_local))
                    elif allow_remote_download:
                        upgrade_queue.append((g, "UPGRADE-CLOUD", None))
        else:
            if src_local is not None:
                new_local_queue.append((g, "NEW-LOCAL", src_local))
            elif allow_remote_download:
                new_remote_queue.append((g, "NEW-CLOUD", None))

    print(
        f"[*] Очередь кандидатов: "
        f"апгрейд старых мыльных = {len(upgrade_queue)}, "
        f"новые из локальных 720p = {len(new_local_queue)}, "
        f"облачные = {len(new_remote_queue)}"
    )

    # Формируем сбалансированную пачку: сначала половину на апгрейд хитов, половину на новые тайтлы!
    selected: List[Tuple[Dict[str, Any], str, Optional[Path]]] = []
    half_up = min(len(upgrade_queue), max(10, batch_size // 3))
    selected.extend(upgrade_queue[:half_up])
    rem = batch_size - len(selected)
    if rem > 0:
        selected.extend(new_local_queue[:rem])
    rem = batch_size - len(selected)
    if rem > 0 and len(upgrade_queue) > half_up:
        selected.extend(upgrade_queue[half_up : half_up + rem])
    rem = batch_size - len(selected)
    if rem > 0:
        selected.extend(new_remote_queue[:rem])

    if not selected:
        print("[+] Нет кандидатов для текущего режима!")
        return 0, 0

    work_items = [
        (i, len(selected), g, mode, src)
        for i, (g, mode, src) in enumerate(selected, 1)
    ]

    upgraded_cnt = 0
    added_cnt = 0

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futs = [pool.submit(process_one_candidate, item, token, gdrive_folder) for item in work_items]
        for fut in as_completed(futs):
            res = fut.result()
            if not res:
                continue
            tid = res["titleId"]
            g = games_by_tid.get(tid)
            if not g:
                continue

            direct_url = res["directUrl"]
            icon_size = res["iconSize"]
            dur_sec = res["durationSec"]
            title = g.get("title", tid)

            # Обновляем прикрепленную иконку у основного 16:9 варианта
            for v in g["variants"]:
                if not str(v.get("id", "")).startswith("icon-") and v.get("width", 1280) != 256:
                    v["hasIcon"] = True
                    v["iconUrl"] = direct_url
                    v["iconSizeBytes"] = icon_size
                    v["iconCodec"] = "h264"
                    v["iconWidth"] = 256
                    v["iconHeight"] = 256
                    break

            icon_slug = f"icon-{tid.lower()}"
            icon_payload = {
                "id": icon_slug,
                "name": f"4IFIR Ultra-HQ: {title}",
                "style": "4IFIR Dynamic Icon",
                "version": "2.0",
                "url": direct_url,
                "previewUrl": direct_url,
                "sizeBytes": icon_size,
                "sha256": "",
                "durationSec": dur_sec,
                "author": "@4IFIR / H3H",
                "codec": "h264",
                "width": 256,
                "height": 256,
                "fps": 30.0,
                "hasAudio": False,
                "hasIcon": True,
                "iconUrl": direct_url,
                "iconSizeBytes": icon_size,
                "iconCodec": "h264",
                "iconWidth": 256,
                "iconHeight": 256,
                "notes": "4IFIR 256x256 Ultra-HQ v2 (Lanczos + CAS 0.45 + Seamless xfade + High@Slow CRF 15)",
            }

            existing_icon_var = next(
                (v for v in g["variants"] if v.get("id") == icon_slug or v.get("width") == 256),
                None,
            )
            if existing_icon_var:
                existing_icon_var.update(icon_payload)
            else:
                g["variants"].append(icon_payload)

            if res["mode"].startswith("UPGRADE"):
                upgraded_cnt += 1
            else:
                added_cnt += 1

    total_done = upgraded_cnt + added_cnt
    if total_done > 0:
        sync_local_catalog_outputs(cat_data, active_cat_path)
        total_icons_now = sum(
            1 for g in cat_data["games"]
            if any(v.get("hasIcon") and v.get("iconUrl") for v in g.get("variants", []))
        )
        print(
            f"\n[+] Каталог [{edition.upper()}] синхронизирован: "
            f"+{added_cnt} новых, ~{upgraded_cnt} улучшено до Ultra-HQ v2! Всего игр с видеоиконками: {total_icons_now}."
        )

        if push_github:
            gh_token, _ = GitHubPublisher.get_stored_credentials()
            local_proxy = detect_local_proxy()
            repo_url = (
                f"https://x-access-token:{gh_token}@github.com/Holy3holy-dev/H3H-Backgrounds.git"
                if gh_token else "origin"
            )
            git_env = os.environ.copy()
            git_env["GIT_EDITOR"] = ":"
            git_env["GIT_TERMINAL_PROMPT"] = "0"
            if local_proxy:
                git_env["http_proxy"] = local_proxy
                git_env["https_proxy"] = local_proxy

            subprocess.run(["git", "pull", "--rebase", repo_url, "main"], env=git_env, check=False)
            subprocess.run(
                [
                    "git", "add",
                    "catalog/data/catalog.json",
                    "catalog/data/catalog.min.json",
                    "catalog/data/catalog.min.json.gz",
                ],
                check=False,
            )
            msg = (
                f"feat(icons): +{added_cnt} new & {upgraded_cnt} upgraded Ultra-HQ 256x256 video icons "
                f"(Lanczos+CAS+xfade CRF15) [skip render] [skip ci]"
            )
            subprocess.run(["git", "commit", "-m", msg], env=git_env, check=False)
            res_push = subprocess.run(
                ["git", "push", repo_url, "HEAD:refs/heads/main"],
                env=git_env,
                capture_output=True,
                text=True,
            )
            if res_push.returncode == 0:
                print(f"[+] Отправлено в GitHub main: {msg}")
            else:
                print(f"[-] Уведомление git push: {res_push.stderr}")
        else:
            print("[*] Локальный режим тестирования активен: в GitHub ничего НЕ отправлялось.")

    return added_cnt, upgraded_cnt


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch Ultra-HQ 256x256 Video Icon Generator v2")
    parser.add_argument("--batch", type=int, default=48, help="Количество иконок за один пакет")
    parser.add_argument("--workers", type=int, default=4, help="Число параллельных потоков кодирования")
    parser.add_argument("--edition", type=str, default="main", help="Целевой каталог: main или after-dark")
    parser.add_argument("--no-upgrade", action="store_true", help="Не обновлять старые мыльные иконки")
    parser.add_argument("--allow-remote", action="store_true", help="Скачивать исходники с облака при отсутствии локальных")
    parser.add_argument("--push-github", action="store_true", help="Публиковать изменения в GitHub (по умолчанию ВЫКЛ)")
    parser.add_argument("--continuous", action="store_true", help="Непрерывно генерировать пакетами")
    parser.add_argument("--interval", type=int, default=8, help="Пауза между пакетами в секундах")
    args = parser.parse_args()

    if args.continuous:
        while True:
            added, upgraded = run_batch(
                batch_size=args.batch,
                workers=args.workers,
                upgrade_lowq=not args.no_upgrade,
                allow_remote_download=args.allow_remote,
                push_github=args.push_github,
                edition=args.edition,
            )
            if added + upgraded == 0:
                print("[*] Все локальные кандидаты обработаны!")
                break
            time.sleep(args.interval)
    else:
        run_batch(
            batch_size=args.batch,
            workers=args.workers,
            upgrade_lowq=not args.no_upgrade,
            allow_remote_download=args.allow_remote,
            push_github=args.push_github,
            edition=args.edition,
        )


if __name__ == "__main__":
    main()
