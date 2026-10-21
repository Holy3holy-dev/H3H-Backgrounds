from pathlib import Path

harv_path = Path("scripts/auto_video_harvester.py")
content = harv_path.read_text(encoding="utf-8")

# Define comprehensive lists
mature_switch_games_code = '''# Nintendo Switch games with mature / adult / ecchi / waifu content
MATURE_SWITCH_GAMES = [
    # Top Action & Mature RPGs on Switch
    ("01005C000B2AE000", "NieR:Automata", ["nier automata 2b", "nier 2b", "nier a2", "2b ecchi"]),
    ("010076F0049A2000", "Bayonetta", ["bayonetta", "bayonetta umbra witch", "bayonetta sexy"]),
    ("010076F0049A4000", "Bayonetta 2", ["bayonetta 2", "bayonetta jeanne"]),
    ("01004A4010DAA000", "Bayonetta 3", ["bayonetta 3", "bayonetta ceres"]),
    ("0100E95004038000", "Xenoblade Chronicles 2", ["xenoblade pyra", "xenoblade mythra", "pyra mythra", "xenoblade nia"]),
    ("010074600E9F2000", "Xenoblade Chronicles 3", ["xenoblade 3 mio", "xenoblade eunie"]),
    ("010091200CDA4000", "Persona 5 Royal", ["persona 5 ann", "persona 5 makoto", "persona 5 kasumi", "persona 5 takemi"]),
    ("0100908018CD6000", "Shin Megami Tensei V", ["shin megami tensei v", "smt v nahobino"]),
    ("010052300C3DC000", "Catherine: Full Body", ["catherine full body", "catherine game", "catherine rin"]),
    ("0100E8B00BDC6000", "The Witcher 3: Wild Hunt", ["witcher 3 yennefer", "witcher 3 triss", "witcher 3 ciri"]),

    # Dedicated Ecchi & Waifu Switch Releases
    ("010099400D28E000", "Senran Kagura Peach Ball", ["senran kagura", "senran kagura asuka", "senran kagura yumi"]),
    ("0100914008272000", "Senran Kagura Reflexions", ["senran kagura reflexions", "senran kagura homura"]),
    ("010034200B5B0000", "Dead or Alive Xtreme 3 Scarlet", ["dead or alive marie rose", "dead or alive honoka", "dead or alive xtreme"]),
    ("01003AE007204000", "Gal*Gun 2", ["gal gun 2", "gal gun"]),
    ("01002360155A6000", "Gal*Gun Double Peace", ["gal gun double peace"]),
    ("0100A1900F3BA000", "Azur Lane: Crosswave", ["azur lane prinz eugen", "azur lane taihou", "azur lane akagi", "azur lane bikini"]),
    ("0100A8900A4A0000", "Fate/EXTELLA LINK", ["fate nero claudius", "fate tamamo", "fate scathach"]),
    ("01008D9017646000", "Seven Pirates H", ["seven pirates h"]),
    ("0100EBF010190000", "Moero Crystal H", ["moero crystal h"]),
    ("01005A7013EA0000", "Doki Doki Literature Club Plus!", ["doki doki monika", "ddlc yuri", "ddlc sayori"]),
    ("0100A6301646E000", "Needy Streamer Overload", ["needy streamer overload", "kangel", "ame chan"]),
    ("0100A5B00BDC6000", "Final Fantasy VII", ["tifa lockhart", "aerith gainsborough", "tifa bikini"]),
    ("0100F2C0115B6000", "The Legend of Zelda: Tears of the Kingdom", ["zelda purah", "zelda totk bikini", "purah totk"]),
    ("01007EF00011E000", "The Legend of Zelda: Breath of the Wild", ["princess zelda botw", "zelda gerudo"])
]'''

# Expand SFW games to include official Switch games AND iconic Homebrew Ports
homebrew_and_switch_sfw = '''# Known popular Switch games & famous Homebrew ports for SFW Main catalog
POPULAR_SWITCH_SFW_GAMES = [
    # Top Nintendo Exclusives
    ("0100000000010000", "Super Mario Odyssey", ["super mario odyssey", "mario odyssey"]),
    ("0100152000022000", "Mario Kart 8 Deluxe", ["mario kart 8", "mario kart"]),
    ("01007EF00011E000", "The Legend of Zelda: Breath of the Wild", ["breath of the wild", "zelda botw"]),
    ("0100F2C0115B6000", "The Legend of Zelda: Tears of the Kingdom", ["tears of the kingdom", "zelda totk"]),
    ("01006F8002326000", "Animal Crossing: New Horizons", ["animal crossing new horizons", "animal crossing"]),
    ("01000A10041EA000", "Super Smash Bros. Ultimate", ["super smash bros ultimate", "smash ultimate"]),
    ("01002DA013484000", "Metroid Dread", ["metroid dread", "samus aran dread"]),
    ("01003BC0000A0000", "Kirby and the Forgotten Land", ["kirby forgotten land", "kirby"]),
    ("0100559011540000", "Monster Hunter Rise", ["monster hunter rise", "monster hunter kamura"]),

    # Famous Nintendo Switch Homebrew Ports & Legendary PC/Console Classics
    ("0100A6901170A000", "Need for Speed: Hot Pursuit Remastered", ["need for speed", "need for speed hot pursuit", "nfs police"]),
    ("0100B9600D498000", "Need for Speed: Underground", ["need for speed underground", "nfs underground r34", "nfs underground"]),
    ("01004C800C3DC000", "Need for Speed: Most Wanted", ["need for speed most wanted", "nfs most wanted bmw m3", "nfs most wanted"]),
    ("0100658013AE8000", "Grand Theft Auto III - Definitive", ["grand theft auto iii", "gta 3", "claude gta"]),
    ("0100659013AEA000", "Grand Theft Auto: Vice City - Definitive", ["grand theft auto vice city", "gta vice city", "tommy vercetti"]),
    ("010065A013AEC000", "Grand Theft Auto: San Andreas - Definitive", ["grand theft auto san andreas", "gta san andreas", "cj san andreas"]),
    ("0100ABD01785C000", "Portal Companion Collection", ["portal 2", "portal aperture", "glados portal"]),
    ("01004A7010C52000", "Super Mario 64 (Port)", ["super mario 64", "mario 64 castle", "mario 64"]),
    ("0100C810142A6000", "Quake Remastered", ["quake 1", "quake remastered", "quake id"]),
    ("01007E3019808000", "Quake II Remastered", ["quake 2", "quake ii remastered"]),
    ("0100B9F00BD34000", "DOOM (Classic Port)", ["doom classic", "doom 1993", "doom marine"]),
    ("0100B9F00BD36000", "DOOM II (Classic Port)", ["doom 2", "doom ii classic"]),
    ("01000B900D8B0000", "DOOM Eternal", ["doom eternal slayer", "doom eternal fortress"]),
    ("01007E6002A54000", "Sonic Mania", ["sonic mania", "sonic green hill", "sonic the hedgehog"]),
    ("0100994017EE6000", "Sonic Frontiers", ["sonic frontiers", "sonic starfall"]),
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
    ("010093800B8C8000", "Stardew Valley", ["stardew valley sunset", "stardew valley farm"])
]'''

# Target replacing POPULAR_SWITCH_SFW_GAMES
import re
pattern = r'# Known popular Switch games for SFW Main catalog search queries on MoeWalls\s+POPULAR_SWITCH_SFW_GAMES = \[.*?\]'
m = re.search(pattern, content, re.DOTALL)
assert m, "POPULAR_SWITCH_SFW_GAMES pattern not found"

content = content[:m.start()] + mature_switch_games_code + "\n\n" + homebrew_and_switch_sfw + content[m.end():]

# Now update harvest_from_moewalls to use MATURE_SWITCH_GAMES when in after_dark mode
target_m = """        if self.mode == "main":
            for tid, gname, qlist in POPULAR_SWITCH_SFW_GAMES:
                for q in qlist:
                    query_queue.append((tid, gname, q))
        else:
            for q in AFTER_DARK_QUERIES:
                query_queue.append(("0000000000000000", "★ Коллекция After Dark (Свободный выбор)", q))"""

repl_m = """        if self.mode == "main":
            for tid, gname, qlist in POPULAR_SWITCH_SFW_GAMES:
                for q in qlist:
                    query_queue.append((tid, gname, q))
        else:
            # First query mature Switch games with exact Title IDs
            for tid, gname, qlist in MATURE_SWITCH_GAMES:
                for q in qlist:
                    query_queue.append((tid, gname, q))
            # Also append general After Dark waifu / anime collection queries
            for q in AFTER_DARK_QUERIES:
                query_queue.append(("0000000000000000", "★ Коллекция After Dark (Свободный выбор)", q))"""

assert target_m in content
content = content.replace(target_m, repl_m, 1)

with open(harv_path, "w", newline="\n", encoding="utf-8") as f:
    f.write(content)

print("[SUCCESS] auto_video_harvester.py updated with mature Switch games and homebrew ports!")
