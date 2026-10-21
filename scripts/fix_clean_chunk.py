from pathlib import Path

p = Path("scripts/auto_video_harvester.py")
text = p.read_text(encoding="utf-8")

bad_chunk = '''    ("010093800B8C8000", "Stardew Valley", ["stardew valley sunset", "stardew valley farm"])
])
]),
    ("0100152000022000", "Mario Kart 8 Deluxe", ["mario kart 8", "mario kart"]),
    ("01007EF00011E000", "The Legend of Zelda: Breath of the Wild", ["breath of the wild", "zelda botw"]),
    ("0100F2C0115B6000", "The Legend of Zelda: Tears of the Kingdom", ["tears of the kingdom", "zelda totk"]),
    ("01006F8002326000", "Animal Crossing: New Horizons", ["animal crossing new horizons", "animal crossing"]),
    ("01000A10041EA000", "Super Smash Bros. Ultimate", ["super smash bros ultimate", "smash ultimate"]),
    ("0100A3900C3E2000", "Pokemon Sword / Shield", ["pokemon sword shield", "pokemon zacian"]),
    ("0100ABF008968000", "Pokemon Scarlet / Violet", ["pokemon scarlet violet", "koraidon miraidon"]),
    ("01002DA013484000", "Metroid Dread", ["metroid dread", "samus aran dread"]),
    ("01000320000CC000", "Splatoon 2 / 3", ["splatoon", "splatoon 3"]),
    ("0100E95004038000", "Xenoblade Chronicles 2", ["xenoblade chronicles 2 scenery", "xenoblade world"]),
    ("010074600E9F2000", "Xenoblade Chronicles 3", ["xenoblade chronicles 3 scenery", "xenoblade 3"]),
    ("01003BC0000A0000", "Kirby and the Forgotten Land", ["kirby forgotten land", "kirby"]),
    ("0100559011540000", "Monster Hunter Rise", ["monster hunter rise", "monster hunter kamura"]),

    # Top Acclaimed Multiplatform Switch Ports
    ("010036500ECF2000", "Hollow Knight", ["hollow knight", "hallownest", "hollow knight silksong"]),
    ("0100E8B00BDC6000", "The Witcher 3: Wild Hunt", ["witcher 3 scenery", "geralt of rivia kaer morhen", "witcher 3 novigrad"]),
    ("01005C000B2AE000", "NieR:Automata", ["nier automata city ruins", "nier automata amusement park"]),
    ("01004AB00A260000", "Dark Souls: Remastered", ["dark souls bonfire", "dark souls anor londo", "dark souls firelink"]),
    ("010091200CDA4000", "Persona 5 Royal", ["persona 5 shibuya", "persona 5 royal phantom thieves"]),
    ("010052300B254000", "Hades", ["hades game underworld", "zagreus hades"]),
    ("0100B9600AA90000", "Celeste", ["celeste mountain", "celeste game"]),
    ("01008C3005A66000", "Dead Cells", ["dead cells prisoner", "dead cells game"]),
    ("010076F0049A2000", "Bayonetta", ["bayonetta action", "bayonetta umbra"]),
    ("010079C009494000", "Cuphead", ["cuphead boss", "cuphead game"]),
    ("010086C00AF7C000", "Ori and the Will of the Wisps", ["ori and the will of the wisps", "ori blind forest"]),
    ("010093800B8C8000", "Stardew Valley", ["stardew valley sunset", "stardew valley farm"]),
    ("01000B900D8B0000", "Doom Eternal", ["doom eternal slayer", "doom eternal fortress"])
]'''

good_chunk = '''    ("010093800B8C8000", "Stardew Valley", ["stardew valley sunset", "stardew valley farm"])
]'''

assert bad_chunk in text, "bad_chunk not found"
text = text.replace(bad_chunk, good_chunk)

with open(p, "w", newline="\n", encoding="utf-8") as f:
    f.write(text)

print("[SUCCESS] Chunk cleaned!")
