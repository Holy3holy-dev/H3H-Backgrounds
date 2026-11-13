with open("scripts/expand_new_switch_titles.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
inserted = False
for line in lines:
    if "if tid not in games_map:" in line and not inserted:
        block = """        if icon_url:
            new_variant["hasIcon"] = True
            new_variant["iconUrl"] = icon_url
            new_variant["iconSizeBytes"] = icon_size
            new_variant["iconCodec"] = "h264"
            new_variant["iconWidth"] = 256
            new_variant["iconHeight"] = 256

"""
        new_lines.append(block)
        inserted = True
    new_lines.append(line)

with open("scripts/expand_new_switch_titles.py", "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print(f"Inserted: {inserted}")
