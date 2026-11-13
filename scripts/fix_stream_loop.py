with open("scripts/generate_batch_hq_icons.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace('"-stream_loop", "-1",\n        ', '')
text = text.replace('"-stream_loop", "-1",\r\n        ', '')

with open("scripts/generate_batch_hq_icons.py", "w", encoding="utf-8") as f:
    f.write(text)

print("[+] Successfully removed -stream_loop from scripts/generate_batch_hq_icons.py!")
