with open('scripts/auto_harvest_pipeline.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = '''    while True:
        batch_run_count += 1
        print(f"\\n--- Starting Batch #{batch_run_count} (Target: {batch_size} new backgrounds) ---")
        harvested_this_batch = 0'''

replacement = '''    while True:
        batch_run_count += 1
        # Safely reload latest catalog from disk before every batch
        if CATALOG_PATH.exists():
            try:
                with open(CATALOG_PATH, "r", encoding="utf-8") as f:
                    cat_data = json.load(f)
                catalog_games = {g["titleId"].upper(): g for g in cat_data.get("games", [])}
            except Exception:
                pass
        print(f"\\n--- Starting Batch #{batch_run_count} (Target: {batch_size} new backgrounds) ---")
        harvested_this_batch = 0'''

content_norm = content.replace('\r\n', '\n')
target_norm = target.replace('\r\n', '\n')
replacement_norm = replacement.replace('\r\n', '\n')

if target_norm in content_norm:
    new_content = content_norm.replace(target_norm, replacement_norm)
    with open('scripts/auto_harvest_pipeline.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print('SUCCESS: Added batch catalog reload!')
else:
    print('Target not matched.')
