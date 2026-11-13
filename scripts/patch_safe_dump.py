with open("scripts/generate_batch_hq_icons.py", "r", encoding="utf-8") as f:
    text = f.read()

old_write = 'CATALOG_PATH.write_text(json.dumps(cat_data, indent=2, ensure_ascii=False), encoding="utf-8")'
new_write = 'with open(CATALOG_PATH, "w", encoding="utf-8") as f:\n            json.dump(cat_data, f, indent=2, ensure_ascii=False)'

text = text.replace(old_write, new_write)

with open("scripts/generate_batch_hq_icons.py", "w", encoding="utf-8") as f:
    f.write(text)

print("[+] Successfully replaced write_text with safe streamed json.dump!")
