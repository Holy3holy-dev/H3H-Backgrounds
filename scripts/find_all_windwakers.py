import json
import glob

print("--- Searching for Wind Waker across all DBs ---")

for path in ["studio/h3h_studio/data/switch_titles_db.json", "catalog/data/catalog.json", "downloader/romfs/catalog.json"]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                items = data.get("games", data)
            else:
                items = data
            if isinstance(items, dict):
                for k, v in items.items():
                    name = str(v.get("name", v.get("title", ""))) if isinstance(v, dict) else str(v)
                    if "wind waker" in name.lower() or "windwaker" in name.lower() or "zelda" in name.lower():
                        if "wind" in name.lower():
                            print(f"[{path}] Key: {k} -> {name}")
            elif isinstance(items, list):
                for item in items:
                    tid = item.get("titleId", item.get("title_id", item.get("id", "")))
                    name = item.get("title", item.get("name", ""))
                    if "wind waker" in name.lower() or "windwaker" in name.lower():
                        print(f"[{path}] TID: {tid} -> {name}")
    except Exception as e:
        print(f"Err {path}: {e}")
