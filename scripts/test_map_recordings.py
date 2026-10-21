import os, glob, json

folder = r"C:\Users\HL\Downloads\Telegram Desktop\recordings\recordings\covers"
files = glob.glob(os.path.join(folder, "*.mp4"))

with open("downloader/romfs/catalog.json", "r", encoding="utf-8") as f:
    cat = json.load(f)

cat_games = {g["titleId"].upper(): g for g in cat.get("games", [])}

custom_names = {
    "0100A0800E9C4000": "The Witcher 3: Wild Hunt - Complete Edition (RU)",
    "0100EA80032EA000": "New Super Mario Bros. U Deluxe",
    "010019A01E2F2000": "Metroid Prime 4: Beyond",
    "01004D300C5AE000": "Kirby and the Forgotten Land",
    "0100A5C00D162000": "Cuphead + The Delicious Last Course",
    "0100B8E016F76000": "NieR: Automata The End of YoRHa Edition",
    "0100B9C0148D0000": "Slime Rancher: Plortable Edition",
    "0100F7E00C70E000": "Hogwarts Legacy",
}

print(f"Total files: {len(files)}")
for p in sorted(files):
    fname = os.path.basename(p)
    tid = os.path.splitext(fname)[0].upper()
    g = cat_games.get(tid)
    name = g["title"] if g else custom_names.get(tid, "UNKNOWN")
    in_cat = "YES" if g else "NEW TO ADD"
    print(f"[{in_cat:<10}] {tid}: {name}")
