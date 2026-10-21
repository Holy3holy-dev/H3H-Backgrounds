import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open('catalog/data/catalog.json', 'r', encoding='utf-8') as f:
    cat = json.load(f)
existing = {g['titleId'].upper() for g in cat.get('games', []) if g.get('titleId')}

# Accurate list of 40 flagship games
TARGETS_RAW = [
    # Mario Flagships
    ("Super Mario Bros. Wonder", "010015100B514000", "Super Mario Bros Wonder launch trailer 60fps", "*00:10-00:30"),
    ("Super Mario 3D World + Bowser's Fury", "010028600EBDA000", "Super Mario 3D World Bowsers Fury trailer 60fps", "*00:15-00:35"),
    ("Super Mario Maker 2", "01009B90006DC000", "Super Mario Maker 2 launch trailer 60fps", "*00:10-00:30"),
    ("Paper Mario: The Thousand-Year Door", "0100ECD018EBE000", "Paper Mario The Thousand Year Door Switch trailer 60fps", "*00:10-00:30"),
    ("Super Mario RPG", "0100BC0018138000", "Super Mario RPG Nintendo Switch trailer 60fps", "*00:10-00:30"),
    ("Super Mario Party Jamboree", "0100965017338000", "Super Mario Party Jamboree trailer 60fps", "*00:10-00:30"),
    ("Mario Party Superstars", "01006FE013472000", "Mario Party Superstars trailer 60fps", "*00:10-00:30"),
    ("Mario Strikers: Battle League", "010019401051C000", "Mario Strikers Battle League trailer 60fps", "*00:05-00:25"),
    ("Donkey Kong Country: Tropical Freeze", "0100C1F0051B6000", "Donkey Kong Country Tropical Freeze Switch trailer 60fps", "*00:10-00:30"),

    # Zelda
    ("The Legend of Zelda: Link's Awakening", "01006BB00C6F0000", "Zelda Links Awakening Switch trailer 60fps", "*00:05-00:25"),
    ("The Legend of Zelda: Skyward Sword HD", "01002DA013484000", "Zelda Skyward Sword HD trailer 60fps", "*00:10-00:30"),
    ("The Legend of Zelda: Echoes of Wisdom", "01008CF01BAAC000", "Zelda Echoes of Wisdom trailer 60fps", "*00:10-00:30"),

    # Pokemon
    ("Pokemon Scarlet", "0100A3D008C5C000", "Pokemon Scarlet trailer 60fps", "*00:10-00:30"),
    ("Pokemon Violet", "01008F6008C5E000", "Pokemon Violet trailer 60fps", "*00:10-00:30"),
    ("Pokemon Sword", "0100ABF008968000", "Pokemon Sword trailer 60fps", "*00:10-00:30"),
    ("Pokemon Shield", "01008DB008C2C000", "Pokemon Shield trailer 60fps", "*00:10-00:30"),
    ("Pokemon Let's Go Pikachu", "010003F003A34000", "Pokemon Lets Go Pikachu trailer 60fps", "*00:05-00:25"),

    # Nintendo Flagships
    ("Pikmin 4", "0100B7C00933A000", "Pikmin 4 launch trailer 60fps", "*00:10-00:30"),
    ("Kirby's Return to Dream Land Deluxe", "01006B601380E000", "Kirbys Return to Dream Land Deluxe trailer 60fps", "*00:10-00:30"),
    ("Fire Emblem: Three Houses", "010055D009F78000", "Fire Emblem Three Houses trailer 60fps", "*00:10-00:30"),
    ("Fire Emblem Engage", "0100A6301214E000", "Fire Emblem Engage launch trailer 60fps", "*00:10-00:30"),
    ("Bayonetta 3", "01004A4010FEA000", "Bayonetta 3 launch trailer 60fps", "*00:10-00:30"),
    ("Splatoon 3", "0100C2500FC20000", "Splatoon 3 launch trailer 60fps", "*00:10-00:30"),
    ("Luigi's Mansion 2 HD", "010048701995E000", "Luigis Mansion 2 HD trailer 60fps", "*00:05-00:25"),

    # JRPG & Big Adventures
    ("Prince of Persia: The Lost Crown", "0100210019428000", "Prince of Persia The Lost Crown launch trailer 60fps", "*00:10-00:30"),
    ("Octopath Traveler II", "0100A3501946E000", "Octopath Traveler II launch trailer 60fps", "*00:10-00:30"),
    ("Octopath Traveler", "010057D006492000", "Octopath Traveler launch trailer 60fps", "*00:10-00:30"),
    ("Triangle Strategy", "0100CC80140F8000", "Triangle Strategy launch trailer 60fps", "*00:10-00:30"),
    ("Bravely Default II", "01006DC010326000", "Bravely Default II launch trailer 60fps", "*00:10-00:30"),
    ("Live A Live", "0100CF801776C000", "Live A Live Switch trailer 60fps", "*00:10-00:30"),
    ("Shin Megami Tensei V", "010069C01AB82000", "Shin Megami Tensei V launch trailer 60fps", "*00:10-00:30"),
    ("Persona 5 Strikers", "0100801011C3E000", "Persona 5 Strikers launch trailer 60fps", "*00:10-00:30"),
    ("Crisis Core: Final Fantasy VII Reunion", "01004BC0166CC000", "Crisis Core Final Fantasy VII Reunion launch trailer 60fps", "*00:10-00:30"),
    ("Final Fantasy VII", "0100A5B00BDC6000", "Final Fantasy VII Switch launch trailer 60fps", "*00:10-00:30"),
    ("Final Fantasy XII The Zodiac Age", "0100EB100AB42000", "Final Fantasy XII The Zodiac Age Switch trailer 60fps", "*00:10-00:30"),
    ("Monster Hunter Rise: Sunbreak", "0100B04011742000", "Monster Hunter Rise Sunbreak launch trailer 60fps", "*00:10-00:30"),
    ("Tales of Vesperia: Definitive Edition", "01002C0008E52000", "Tales of Vesperia Definitive Edition trailer 60fps", "*00:10-00:30"),

    # Renowned Indies & Action
    ("Ori and the Blind Forest", "010061D00DB74000", "Ori and the Blind Forest Definitive Edition launch trailer 60fps", "*00:05-00:25"),
    ("Ori and the Will of the Wisps", "01008DD013200000", "Ori and the Will of the Wisps launch trailer 60fps", "*00:05-00:25"),
    ("The Binding of Isaac: Repentance", "010021C000B6A000", "The Binding of Isaac Repentance launch trailer 60fps", "*00:05-00:25"),
    ("Slay the Spire", "010026300BA4A000", "Slay the Spire launch trailer 60fps", "*00:05-00:25"),
    ("Chained Echoes", "0100C510166F0000", "Chained Echoes launch trailer 60fps", "*00:05-00:25"),
    ("Eastward", "010071B00F63A000", "Eastward launch trailer 60fps", "*00:05-00:25"),
    ("Rayman Legends: Definitive Edition", "01005FF002E2A000", "Rayman Legends Definitive Edition Switch trailer 60fps", "*00:10-00:30"),
    ("Mortal Kombat 11", "0100F2200C984000", "Mortal Kombat 11 launch trailer 60fps", "*00:10-00:30"),
    ("Little Nightmares II", "010097100EDD6000", "Little Nightmares II launch trailer 60fps", "*00:10-00:30"),
    ("LEGO Star Wars: The Skywalker Saga", "010042D00D900000", "LEGO Star Wars The Skywalker Saga launch trailer 60fps", "*00:10-00:30"),
    ("EA SPORTS FC 24", "0100BDB01A0E6000", "EA SPORTS FC 24 official trailer 60fps", "*00:10-00:30"),
    ("GRID Autosport", "0100DC800A602000", "GRID Autosport Nintendo Switch launch trailer 60fps", "*00:10-00:30"),
    ("Civilization VI", "01009B500C886000", "Sid Meiers Civilization VI Nintendo Switch trailer 60fps", "*00:10-00:30")
]

final_targets = []
seen = set()
for name, tid, q, tr in TARGETS_RAW:
    tid = tid.upper()
    if tid not in existing and tid not in seen:
        seen.add(tid)
        clean_name = name.replace(":", "").replace("'", "").replace(" ", "_")
        final_targets.append({
            "name": name,
            "titleId": tid,
            "filename": f"{tid}_{clean_name}.mp4",
            "query": q,
            "time_range": tr
        })

print(f"Total Unique Verified Targets for Batch 9: {len(final_targets)}")
with open("scripts/batch_9_targets.json", "w", encoding="utf-8") as f:
    json.dump(final_targets, f, ensure_ascii=False, indent=2)
print("Saved to scripts/batch_9_targets.json")
