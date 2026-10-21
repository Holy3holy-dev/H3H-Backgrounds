import json
from pathlib import Path
from datetime import datetime, timezone

cat_path = Path("catalog/data/catalog_after_dark.json")

base_data = {
    "schemaVersion": 1,
    "name": "H3H After Dark (18+) Official Catalog",
    "updatedAt": datetime.now(timezone.utc).isoformat(),
    "totalGames": 0,
    "totalVariants": 0,
    "games": [
        {
            "titleId": "0000000000000000",
            "title": "★ Коллекция After Dark (Свободный выбор)",
            "publisher": "H3H Studio",
            "variants": []
        }
    ]
}

cat_path.parent.mkdir(parents=True, exist_ok=True)
if not cat_path.exists():
    cat_path.write_text(json.dumps(base_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[+] Initialized {cat_path}")
else:
    print(f"[*] {cat_path} already exists")
