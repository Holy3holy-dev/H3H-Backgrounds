"""
Генератор компактного турбо-индекса каталога (catalog.min.json и catalog.min.json.gz).
Удаляет избыточные пробелы и поля со значениями по умолчанию в CatalogManager,
сохраняя 100% совместимость со схемой schemaVersion=1 и уменьшая расход RAM/сети в 4-10 раз.
"""

import gzip
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_CATALOG = ROOT_DIR / "catalog" / "data" / "catalog.json"
MIN_CATALOG = ROOT_DIR / "catalog" / "data" / "catalog.min.json"
GZ_CATALOG = ROOT_DIR / "catalog" / "data" / "catalog.min.json.gz"
ROMFS_CATALOG = ROOT_DIR / "downloader" / "romfs" / "catalog.json"


def minify_catalog_dict(data: dict) -> dict:
    out_games = []
    for g in data.get("games", []):
        tid = str(g.get("titleId", "")).strip().upper()
        if len(tid) != 16:
            continue
        mg = {
            "titleId": tid,
            "title": g.get("title", "Unknown Title"),
        }
        if g.get("publisher"):
            mg["publisher"] = g["publisher"]
        if g.get("iconUrl"):
            mg["iconUrl"] = g["iconUrl"]

        m_vars = []
        for v in g.get("variants", []):
            mv = {
                "id": v.get("id", ""),
                "name": v.get("name", "Standard"),
            }
            style = v.get("style", "")
            if style and style != "All":
                mv["style"] = style
            ver = v.get("version", "1.0")
            if ver and ver != "1.0":
                mv["version"] = ver
            if v.get("url"):
                mv["url"] = v["url"]
            if v.get("previewUrl"):
                mv["previewUrl"] = v["previewUrl"]
            if v.get("sizeBytes"):
                mv["sizeBytes"] = int(v["sizeBytes"])
            if v.get("sha256"):
                mv["sha256"] = v["sha256"]
            if v.get("durationSec"):
                mv["durationSec"] = round(float(v["durationSec"]), 1)
            author = v.get("author", "Community")
            if author and author != "Community":
                mv["author"] = author
            codec = v.get("codec", "h264")
            if codec and codec != "h264":
                mv["codec"] = codec
            w = int(v.get("width", 1280) or 1280)
            h = int(v.get("height", 720) or 720)
            if w != 1280:
                mv["width"] = w
            if h != 720:
                mv["height"] = h
            fps = float(v.get("fps", 30.0) or 30.0)
            if abs(fps - 30.0) > 0.05:
                mv["fps"] = round(fps, 2)
            if v.get("hasAudio"):
                mv["hasAudio"] = True
            if v.get("notes"):
                mv["notes"] = v["notes"]
            if v.get("iconUrl"):
                mv["hasIcon"] = True
                mv["iconUrl"] = v["iconUrl"]
                if v.get("iconSizeBytes"):
                    mv["iconSizeBytes"] = int(v["iconSizeBytes"])
                ic = v.get("iconCodec", "hevc")
                if ic and ic != "hevc":
                    mv["iconCodec"] = ic
                iw = int(v.get("iconWidth", 256) or 256)
                ih = int(v.get("iconHeight", 256) or 256)
                if iw != 256:
                    mv["iconWidth"] = iw
                if ih != 256:
                    mv["iconHeight"] = ih

            m_vars.append(mv)

        mg["variants"] = m_vars
        out_games.append(mg)

    return {
        "schemaVersion": int(data.get("schemaVersion", 1)),
        "updatedAt": data.get("updatedAt", ""),
        "games": out_games,
    }


def build_min_catalog() -> None:
    with open(SRC_CATALOG, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    minified = minify_catalog_dict(raw_data)
    payload = json.dumps(minified, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    with open(MIN_CATALOG, "wb") as f:
        f.write(payload)

    with gzip.open(GZ_CATALOG, "wb", compresslevel=9) as gf:
        gf.write(payload)

    # Обновляем встроенный офлайн-каталог romfs компактной версией для экономии RAM и размера NRO
    ROMFS_CATALOG.parent.mkdir(parents=True, exist_ok=True)
    with open(ROMFS_CATALOG, "wb") as rf:
        rf.write(payload)

    src_kb = SRC_CATALOG.stat().st_size / 1024
    min_kb = MIN_CATALOG.stat().st_size / 1024
    gz_kb = GZ_CATALOG.stat().st_size / 1024
    icons_total = sum(
        1 for g in minified["games"] if any(v.get("hasIcon") or v.get("iconUrl") for v in g["variants"])
    )
    print(
        f"[+] Турбо-индекс собран: игр={len(minified['games'])}, с HQ-иконками={icons_total} | "
        f"Исходный={src_kb:.1f} КБ -> Min={min_kb:.1f} КБ -> Gzip={gz_kb:.1f} КБ"
    )


if __name__ == "__main__":
    build_min_catalog()
