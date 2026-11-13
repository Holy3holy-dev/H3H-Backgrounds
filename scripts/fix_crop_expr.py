with open("scripts/generate_batch_hq_icons.py", "r", encoding="utf-8") as f:
    text = f.read()

bad_crop = 'crop=min(iw\\,ih):min(iw\\,ih):(iw-ow)*0.5:(ih-oh)/2,scale=256:256:flags=lanczos,unsharp=3:3:0.6:3:3:0.0,fps=30,format=yuv420p'
good_crop = 'crop=ih:ih:(iw-ih)/2:0,scale=256:256:flags=lanczos,unsharp=3:3:0.6:3:3:0.0,fps=30,format=yuv420p'

text = text.replace(bad_crop, good_crop)

with open("scripts/generate_batch_hq_icons.py", "w", encoding="utf-8") as f:
    f.write(text)

print("[+] Successfully fixed crop expression in scripts/generate_batch_hq_icons.py!")
