"""Patches auto_video_harvester.py and tg_bot/bot.py with [skip render] [skip ci] and live GitHub catalog stats sync."""
from pathlib import Path

p_h = Path("scripts/auto_video_harvester.py")
t_h = p_h.read_text(encoding="utf-8")
old_c = 'f"feat(harvest): automated batch harvest {harvested_count} {self.mode} video themes ({self.codec.upper()})"'
new_c = 'f"feat(harvest): automated batch harvest {harvested_count} {self.mode} video themes ({self.codec.upper()}) [skip render] [skip ci]"'
if old_c in t_h:
    t_h = t_h.replace(old_c, new_c)
    p_h.write_text(t_h, encoding="utf-8")
    print("[+] Patched auto_video_harvester.py with [skip render] [skip ci]")

p_b = Path("tg_bot/bot.py")
t_b = p_b.read_text(encoding="utf-8")
old_m = '"message": commit_msg,'
new_m = '"message": commit_msg if "[skip render]" in commit_msg else f"{commit_msg} [skip render] [skip ci]",'
if old_m in t_b:
    t_b = t_b.replace(old_m, new_m)

old_stats = """def get_catalog_stats() -> dict:
    std_games = 0"""

new_stats = """_last_remote_sync = 0.0

def get_catalog_stats() -> dict:
    global _last_remote_sync
    if time.time() - _last_remote_sync > 60.0:
        _last_remote_sync = time.time()
        for rel_p in (CATALOG_PATH_STANDARD, CATALOG_PATH_AFTER_DARK):
            try:
                raw_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{str(rel_p).replace(chr(92), '/')}?t={int(time.time())}"
                req = urllib.request.Request(raw_url, headers={"User-Agent": "H3H-Bot-Sync/1.0"})
                with urllib.request.urlopen(req, timeout=8) as r:
                    content = r.read()
                    if len(content) > 1000:
                        (PROJECT_ROOT / rel_p).write_bytes(content)
            except Exception:
                pass
    std_games = 0"""

if old_stats in t_b and "_last_remote_sync" not in t_b:
    t_b = t_b.replace(old_stats, new_stats)

p_b.write_text(t_b, encoding="utf-8")
print("[+] Patched tg_bot/bot.py with [skip render] and live GitHub catalog stats sync")
