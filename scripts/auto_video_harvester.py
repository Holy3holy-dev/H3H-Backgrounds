"""
H3H Automated Video Background Harvester Pipeline.
Streamlined, continuous harvesting ("на поток") for both:
1. Main Branch: High-quality, atmospheric, SFW gaming video backgrounds for Nintendo Switch.
   Sources: SteamGridDB (animated heroes/grids for Switch games) + MoeWalls (cinematic Switch exclusives).
2. After Dark Branch: Mature, ecchi, 18+, anime/waifu video backgrounds for Nintendo Switch games and collection.
   Sources: MoeWalls (Switch games with adult/ecchi filters + waifus).

Features:
- Dual-source harvesting (SteamGridDB + MoeWalls)
- Switch Title prioritization for BOTH Main and After Dark catalogs
- Strict After Dark validation (only genuine adult, ecchi, sensual, waifu, swimsuit content)
- Codec selection: AVC (H.264) or HEVC (H.265 with NVDEC hvc1 tag)
- Continuous streaming loop mode (--continuous) with configurable intervals and batch sizes
- Automatic Google Drive token refresh (runs indefinitely without auth expiry)
- Atomic progress logging and duplicate prevention
- Automated GitHub catalog sync with --force push to after-dark branch
"""

import os
import sys
import json
import time
import re
import argparse
import hashlib
import subprocess
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
sys.stderr.reconfigure(encoding='utf-8', line_buffering=True)

# Path configuration
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "studio"))

from scripts.title_id_resolver import TitleIdResolver
from h3h_studio.core.steamgriddb import SteamGridDBClient
from h3h_studio.core.google_drive import GoogleDriveHelper, GoogleDriveClient
from h3h_studio.core.github_publisher import GitHubPublisher
from tg_bot.config import (
    GDRIVE_FOLDER_ID,
    GDRIVE_AFTER_DARK_FOLDER_ID,
    CATALOG_PATH_STANDARD,
    CATALOG_PATH_AFTER_DARK
)

STAGE_DIR = Path(r"H:\h3h_stage")
RAW_DIR = STAGE_DIR / "raw"
P720_DIR = STAGE_DIR / "720p"
THUMB_DIR = STAGE_DIR / "thumbs"

for d in [STAGE_DIR, RAW_DIR, P720_DIR, THUMB_DIR]:
    d.mkdir(parents=True, exist_ok=True)

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

# Priority games queue for SteamGridDB harvesting (high yield of animated heroes & motion grids)
PRIORITY_STEAMGRID_GAMES = [
    ("01007820196A6000", "Red Dead Redemption", "Red Dead Redemption"),
    ("0100ABD01785C000", "Portal Companion Collection", "Portal"),
    ("01000B900D8B0000", "DOOM Eternal", "DOOM Eternal"),
    ("0100BC0005C8A000", "DOOM (2016)", "DOOM"),
    ("010034400C3DA000", "Wolfenstein II: The New Colossus", "Wolfenstein II: The New Colossus"),
    ("010014200B0D0000", "Metro 2033 Redux", "Metro 2033"),
    ("01000F400B0D2000", "Metro: Last Light Redux", "Metro: Last Light"),
    ("01008C3005A66000", "Dead Cells", "Dead Cells"),
    ("01004AB00A260000", "Dark Souls Remastered", "Dark Souls"),
    ("010029600D56A000", "Katana Zero", "Katana ZERO"),
    ("010079C009494000", "Cuphead", "Cuphead"),
    ("01002B30028F6000", "Celeste", "Celeste"),
    ("010052300B254000", "Hades", "Hades"),
    ("010036500ECF2000", "Hollow Knight", "Hollow Knight"),
    ("0100CD801CE5E000", "Balatro", "Balatro"),
    ("010097F018538000", "Dave the Diver", "Dave the Diver"),
    ("01002E7016C46000", "Cult of the Lamb", "Cult of the Lamb"),
    ("010027F017B12000", "Inscryption", "Inscryption"),
    ("0100DA801624E000", "Tunic", "Tunic"),
    ("0100307018934000", "Signalis", "Signalis"),
    ("01008C0016544000", "Sea of Stars", "Sea of Stars"),
    ("010093800B8C8000", "Stardew Valley", "Stardew Valley"),
    ("01003D100E9C6000", "The Witcher 3: Wild Hunt", "The Witcher 3: Wild Hunt"),
    ("01005CA01580E000", "Persona 5 Royal", "Persona 5 Royal"),
    ("01005C000B2AE000", "NieR:Automata", "NieR:Automata"),
    ("01000A10041EA000", "The Elder Scrolls V: Skyrim", "The Elder Scrolls V: Skyrim"),
    ("0100559011540000", "Monster Hunter Rise", "Monster Hunter Rise"),
    ("010040801A4C8000", "Blasphemous 2", "Blasphemous 2"),
    ("010006700C7E2000", "Blasphemous", "Blasphemous"),
    ("010038800C3DC000", "BioShock Remastered", "BioShock Remastered"),
    ("010065000C3DE000", "BioShock Infinite", "BioShock Infinite"),
    ("01000F900C404000", "Borderlands 2", "Borderlands 2"),
    ("01005A300C3FA000", "Borderlands: The Pre-Sequel", "Borderlands: The Pre-Sequel"),
    ("010076F0049A2000", "Bayonetta", "Bayonetta"),
    ("01003BC0000A0000", "Kirby and the Forgotten Land", "Kirby and the Forgotten Land"),
    ("01002DA013484000", "Metroid Dread", "Metroid Dread"),
    ("010086C00AF7C000", "Ori and the Will of the Wisps", "Ori and the Will of the Wisps")
]

# Dedicated Nintendo Switch games for After Dark (with specific character and mature queries)
MATURE_SWITCH_GAMES = [
    # Top Action & Mature RPGs on Switch
    ("01005C000B2AE000", "NieR:Automata", ["2b", "nier 2b", "nier a2", "2b ecchi", "2b swimsuit", "2b white"]),
    ("0100A5B00BDC6000", "Final Fantasy VII", ["tifa", "tifa lockhart", "aerith", "tifa bikini", "aerith beach"]),
    ("0100E95004038000", "Xenoblade Chronicles 2", ["pyra", "mythra", "xenoblade pyra", "xenoblade mythra"]),
    ("010074600E9F2000", "Xenoblade Chronicles 3", ["xenoblade 3 mio", "xenoblade eunie", "xenoblade 3"]),
    ("0100F2C0115B6000", "The Legend of Zelda: Tears of the Kingdom", ["zelda", "purah", "zelda tears of the kingdom"]),
    ("01007EF00011E000", "The Legend of Zelda: Breath of the Wild", ["princess zelda", "zelda gerudo", "zelda breath of the wild"]),
    ("010076F0049A2000", "Bayonetta", ["bayonetta", "cereza bayonetta", "bayonetta umbra"]),
    ("010076F0049A4000", "Bayonetta 2", ["bayonetta 2", "bayonetta jeanne"]),
    ("01004A4010DAA000", "Bayonetta 3", ["bayonetta 3", "bayonetta ceres"]),
    ("010052300C3DC000", "Catherine: Full Body", ["catherine full body", "catherine rin", "catherine"]),
    ("01005A7013EA0000", "Doki Doki Literature Club Plus!", ["monika", "doki doki monika", "ddlc monika"]),
    ("0100A6301646E000", "Needy Streamer Overload", ["kangel", "needy streamer overload", "ame chan"]),
    ("01002DA013484000", "Metroid Dread", ["samus", "samus aran", "zero suit samus"]),
    ("0100000000010000", "Super Mario Odyssey", ["bowsette", "boosette", "princess peach", "rosalina"]),
    ("0100E8B00BDC6000", "The Witcher 3: Wild Hunt", ["witcher yennefer", "witcher triss", "witcher ciri"]),
    ("010091200CDA4000", "Persona 5 Royal", ["persona 5 ann", "persona 5 makoto", "persona 5 kasumi", "persona 5 takemi"]),
    ("010034B016912000", "Persona 4 Golden", ["persona 4 rise", "persona 4 chie", "persona 4 yukiko"]),
    ("0100808016910000", "Persona 3 Portable", ["persona 3 mitsuru", "persona 3 yukari", "persona 3 aigis"]),
    ("010034200B5B0000", "Dead or Alive Xtreme 3 Scarlet", ["dead or alive", "marie rose", "honoka dead or alive"]),
    ("010099400D28E000", "Senran Kagura Peach Ball", ["senran kagura", "senran", "senran kagura asuka"]),
    ("0100914008272000", "Senran Kagura Reflexions", ["senran kagura reflexions", "senran kagura homura"]),
    ("0100A1900F3BA000", "Azur Lane: Crosswave", ["azur lane", "prinz eugen", "taihou", "shinano azur lane", "atago azur lane"]),
    ("0100A8900A4A0000", "Fate/EXTELLA LINK", ["fate nero", "fate scathach", "fate saber", "fate tamamo"]),
    ("0100B7000B36E000", "Dragon Ball FighterZ", ["android 18", "android 21"]),
    ("0100435942450000", "Cyberpunk 2077", ["lucy cyberpunk", "rebecca cyberpunk", "lucy edgerunners"]),
    ("010055D009AA8000", "Fire Emblem: Three Houses", ["fire emblem edelgard", "fire emblem byleth", "fire emblem hilda"]),
    ("010052300B254000", "Hades", ["aphrodite hades", "nyx hades", "megaera hades"]),
    ("01003AE007204000", "Gal*Gun 2", ["gal gun", "gal gun 2"]),
    ("01008D9017646000", "Seven Pirates H", ["seven pirates h", "seven pirates"]),
    ("0100EBF010190000", "Moero Crystal H", ["moero crystal h", "moero crystal"]),

    # Switch Visual Novels, Galge & Anime Fighting Titles
    ("010045000E418000", "Nekopara (Vol. 1-4)", ["nekopara", "chocola", "vanilla nekopara", "chocola nekopara"]),
    ("010063F014170000", "Danganronpa Decadence", ["danganronpa", "chiaki nanami", "junko enoshima", "kyoko kirigiri"]),
    ("0100A3F00C536000", "Kill la Kill - IF", ["kill la kill", "ryuko", "ryuuko matoi", "satsuki kiryuin"]),
    ("0100BE400CA2E000", "Steins;Gate Divergence Assorted", ["steins gate", "kurisu makise", "kurisu steins gate"]),
    ("0100A3A00CC7E000", "Clannad", ["clannad", "nagisa clannad", "ushio clannad"]),
    ("010092300D49E000", "Atelier Ryza / Sophie", ["atelier ryza", "atelier sophie", "ryza atelier", "atelier"]),
    ("01001E30126A0000", "Melty Blood: Type Lumina", ["melty blood", "arcueid", "neco arc", "tsukihime"]),
    ("0100EE800C93E000", "BlazBlue Cross Tag Battle", ["blazblue", "blazblue noel", "blazblue rachel"]),
    ("0100AB401F136000", "Guilty Gear -Strive-", ["guilty gear", "bridget guilty gear", "baiken guilty gear"]),
    ("010046B00DE62000", "Skullgirls 2nd Encore", ["skullgirls", "filia skullgirls", "valentine skullgirls"]),
    ("010023301E41C000", "Fate/Stay Night Remastered", ["fate stay night", "saber fate", "rin tohsaka", "fate saber alter"]),
    ("01004ED016E10000", "Neptunia x Senran Kagura Ninja Wars", ["hyperdimension neptunia", "purple heart neptunia", "noire neptunia"]),
    ("0100FBD01884C000", "Akiba's Trip: Hellbound & Debriefed", ["akibas trip", "akiba trip", "akiba"]),
    ("01002BD00CB86000", "Panty Party", ["panty party"]),
    ("010027F00AD6C000", "SNK Heroines: Tag Team Frenzy", ["snk heroines", "mai shiranui", "kula diamond"]),
    ("01003B300E4AA000", "The Grisaia Trilogy", ["grisaia", "grisaia phantom trigger", "fruit of grisaia"]),
    ("01003DE00C95E000", "Mary Skelter 2", ["mary skelter", "mary skelter 2"]),
    ("01004EB0119AC000", "Moero Chronicle Hyper", ["moero chronicle", "monster girl ecchi"]),
    ("0100BF500207C000", "Bloodstained: Ritual of the Night", ["bloodstained", "bloodstained miriam"]),
    ("01005700031AE000", "Disgaea Complete", ["disgaea", "disgaea etna", "disgaea flonne"]),
    ("0100990011866000", "Aokana: Four Rhythms Across the Blue", ["aokana", "asuka kurashina"]),
    ("010016101100A000", "The House in Fata Morgana", ["house in fata morgana", "fata morgana"]),
    ("0100F7E01343E000", "Corpse Party Blood Covered", ["corpse party", "ayumi shinozaki"]),

    # New Mature, Ecchi & Visual Novel Additions for Nintendo Switch
    ("0100C8801594E000", "Gal*Gun Double Peace", ["gal gun double peace", "gal gun"]),
    ("010090F012644000", "Gal*Gun Returns", ["gal gun returns", "gal gun ecchi"]),
    ("010093800B9CE000", "Omega Labyrinth Life", ["omega labyrinth life", "omega labyrinth"]),
    ("01002EA0112A6000", "Waifu Uncovered", ["waifu uncovered"]),
    ("01002270146AE000", "Waifu Discovered 2: Medieval Fantasy", ["waifu discovered"]),
    ("01008DE00C4FA000", "Super Neptunia RPG", ["super neptunia rpg", "neptunia"]),
    ("0100B9F01B63E000", "Neptunia Sisters VS Sisters", ["neptunia sisters", "neptunia nepgear"]),
    ("0100DCE00FE24000", "Megadimension Neptunia VII", ["megadimension neptunia", "neptune anime"]),
    ("010009B00E71A000", "Atelier Ryza: Ever Darkness & the Secret Hideout", ["atelier ryza", "ryza reisalin", "ryza thighs"]),
    ("010052901243A000", "Atelier Ryza 2: Lost Legends & the Secret Fairy", ["atelier ryza 2", "ryza swimsuit"]),
    ("0100F48017B80000", "Atelier Ryza 3: Alchemist of the End", ["atelier ryza 3"]),
    ("010051B014524000", "Atelier Sophie 2: The Alchemist of the Mysterious Dream", ["atelier sophie 2", "sophie neuenmuller"]),
    ("0100D5D010EB4000", "Mary Skelter Finale", ["mary skelter finale"]),
    ("01000B0011C9C000", "Death end re;Quest", ["death end request", "death end re quest"]),
    ("0100E2C0157E8000", "Death end re;Quest 2", ["death end re quest 2"]),
    ("01002F401C950000", "Tsukihime -A piece of blue glass moon-", ["tsukihime", "arcueid brunestud", "ciel tsukihime"]),
    ("0100344018A1A000", "Witch on the Holy Night", ["witch on the holy night", "aoko aozaki", "alice kuonji"]),
    ("0100847012D78000", "Saya no Uta", ["saya no uta", "song of saya"]),
    ("0100B9600E262000", "The Fruit of Grisaia: Remastered", ["fruit of grisaia", "yumiko sakaki", "michiru matsushima"]),
    ("01001A800FCFE000", "Grisaia: Phantom Trigger 01 to 05", ["grisaia phantom trigger", "rena grisaia"]),
    ("010058C00A63C000", "Higurashi When They Cry Hou", ["higurashi", "rena ryugu", "mion sonozaki"]),
    ("010025D00E71C000", "Umineko When They Cry Saku", ["umineko", "beatrice umineko"]),
    ("010065200DEB2000", "Gun Gun Pixies", ["gun gun pixies"]),
    ("0100486009E48000", "Bullet Girls Phantasia", ["bullet girls phantasia", "bullet girls"]),
    ("0100BD601309E000", "Crawlco Block Knockers", ["crawlco block knockers"]),
    ("0100C1A014E4C000", "Pretty Girls Mahjong Solitaire", ["pretty girls mahjong", "pretty girls"]),
    ("010020B01A3DE000", "Akiba's Trip: Undead & Undressed", ["akibas trip undead", "shizuku akiba"]),
    ("01001F000CB7E000", "Date A Live: Rio Reincarnation", ["date a live", "kurumi tokisaki", "tohka yatogami"]),
    ("010027701815A000", "Date A Live: Ren Dystopia", ["date a live ren dystopia", "kurumi date a live"]),
    ("0100C9E00CA3E000", "Sword Art Online: Fatal Bullet Complete Edition", ["sword art online", "fatal bullet", "sinon sao", "asuna sao"]),
    ("0100D1A007038000", "Sword Art Online: Hollow Realization Deluxe Edition", ["sao hollow realization", "asuna swimsuit"]),

    # Dedicated Adult / Anime Waifu Franchises
    ("0100EC0000000001", "Genshin Impact (Waifus)", ["genshin impact", "raiden shogun", "yae miko", "ganyu", "hu tao", "furina", "arlecchino", "shenhe", "yelan", "clorinde"]),
    ("0100EC0000000002", "Blue Archive (Swimsuit & Bunny)", ["blue archive", "blue archive swimsuit", "blue archive bunny", "akane bunny", "makoto swimsuit"]),
    ("0100EC0000000003", "Chainsaw Man (Makima & Power)", ["chainsaw man makima", "makima bikini", "power chainsaw man", "reze"]),
    ("0100EC0000000004", "GODDESS OF VICTORY: NIKKE", ["nikke", "nikke bikini", "goddess of victory nikke", "cinderella nikke", "dorothy nikke"]),
    ("0100EC0000000005", "Honkai: Star Rail (Waifus)", ["honkai star rail waifu", "kafka honkai", "firefly honkai", "acheron honkai", "black swan honkai", "sparkle honkai"]),
    ("0100EC0000000006", "Darling in the Franxx (Zero Two)", ["zero two", "zero two bunny", "darling in the franxx"]),
    ("0100EC0000000007", "Stellar Blade (Eve)", ["stellar blade eve", "eve stellar blade", "eve nano suit"]),
    ("0100EC0000000008", "Rascal Does Not Dream (Mai Sakurajima)", ["bunny girl senpai", "mai sakurajima"]),
    ("0100EC0000000009", "SPY x FAMILY (Yor Forger)", ["yor forger", "yor forger assassin", "yor swimsuit"]),
    ("0100EC000000000A", "Zenless Zone Zero", ["zenless zone zero", "ellen joe", "nicole demara", "zhu yuan"]),
    ("0100EC000000000B", "My Dress-Up Darling (Marin Kitagawa)", ["marin kitagawa", "marin bikini", "my dress-up darling"]),
    ("0100EC000000000C", "Overlord (Albedo & Shalltear)", ["overlord albedo", "albedo water", "shalltear bloodfallen"]),
    ("0100EC000000000D", "Re:Zero (Rem & Emilia)", ["rem re:zero", "rem fallen maid", "emilia re:zero", "echidna re:zero"]),
    ("0100EC000000000E", "KonoSuba (Megumin & Aqua)", ["konosuba megumin", "megumin", "aqua konosuba", "darkness konosuba"]),
    ("0100EC000000000F", "Hololive VTubers (Marine, Gura, Calli)", ["hololive", "houshou marine", "gawr gura", "mori calliope", "usada pekora"]),
    ("0100EC0000000010", "High School DxD (Rias & Akeno)", ["high school dxd", "rias gremory", "akeno himejima"]),
    ("0100EC0000000011", "To Love-Ru Darkness", ["to love ru", "to love-ru", "golden darkness", "lala satalin", "momo to love ru"])
]

# General mature / ecchi / waifu / genre queries for After Dark collection
AFTER_DARK_GENERAL_QUERIES = [
    # High-yielding Direct Tags on MoeWalls
    "tag:bikini", "tag:swimsuit", "tag:beach", "tag:bunny", "tag:maid",
    "tag:hot", "tag:legs", "tag:dress", "tag:gothic", "tag:elf", "tag:demon",
    "tag:vampire", "tag:overlord", "tag:konosuba", "tag:hololive", "tag:summer",
    "tag:school-uniform", "tag:blue-archive", "tag:genshin-impact", "tag:honkai-star-rail", "tag:cyberpunk",

    # Explicit / Ecchi Themes & Visual Filters
    "ecchi", "bikini", "swimsuit", "beach anime", "lingerie waifu", "cleavage",
    "bunny girl", "maid waifu", "monster girl", "catgirl", "succubus",
    "undressing", "erotic anime", "wet anime", "bath anime girl",
    "morrigan darkstalkers", "mai shiranui", "chun li", "cammy", "juri han"
]

# Known popular Switch games & famous Homebrew ports for SFW Main catalog
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
    ("0100BD0009ED6000", "Super Mario 3D World + Bowser's Fury", ["bowsers fury", "mario 3d world"]),
    ("0100ABF008968000", "Luigi's Mansion 3", ["luigis mansion 3", "luigi mansion"]),
    ("010055D009AA8000", "Fire Emblem: Three Houses", ["fire emblem three houses", "fire emblem edelgard"]),
    ("0100E95004038000", "Xenoblade Chronicles 2", ["xenoblade chronicles 2", "xenoblade pyra"]),
    ("010074600E9F2000", "Xenoblade Chronicles 3", ["xenoblade chronicles 3", "xenoblade 3"]),
    ("01008C3005A66000", "Dead Cells", ["dead cells prisoner", "dead cells game"]),
    ("010052300B254000", "Hades", ["hades game underworld", "zagreus hades"]),
    ("0100CD801CE5E000", "Balatro", ["balatro game", "balatro cards"]),
    ("010036500ECF2000", "Hollow Knight", ["hollow knight", "hallownest", "hollow knight silksong"]),

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
    ("0100E8B00BDC6000", "The Witcher 3: Wild Hunt", ["witcher 3 scenery", "geralt of rivia kaer morhen", "witcher 3 novigrad"]),
    ("01005C000B2AE000", "NieR:Automata", ["nier automata city ruins", "nier automata amusement park"]),
    ("01004AB00A260000", "Dark Souls: Remastered", ["dark souls bonfire", "dark souls anor londo", "dark souls firelink"]),
    ("010091200CDA4000", "Persona 5 Royal", ["persona 5 shibuya", "persona 5 royal phantom thieves"]),
    ("0100B9600AA90000", "Celeste", ["celeste mountain", "celeste game"]),
    ("010076F0049A2000", "Bayonetta", ["bayonetta action", "bayonetta umbra"]),
    ("010079C009494000", "Cuphead", ["cuphead boss", "cuphead game"]),
    ("010086C00AF7C000", "Ori and the Will of the Wisps", ["ori and the will of the wisps", "ori blind forest"]),
    ("010093800B8C8000", "Stardew Valley", ["stardew valley sunset", "stardew valley farm"])
]

NSFW_KEYWORDS = [
    "bikini", "swimsuit", "bunny", "ecchi", "nsfw", "18+", "erotic", "nude",
    "naked", "cleavage", "lingerie", "boobs", "ass", "thighs", "waifu", "hentai",
    "sensual", "undressing"
]

def clean_switch_title(raw_title: str) -> str:
    """Clean Switch release filenames to canonical game names."""
    t = re.sub(r'\[.*?\]', '', raw_title)
    t = re.sub(r'\(.*?\)', '', t)
    t = re.sub(r'(\+.*$)', '', t)
    t = re.sub(r'v\d+(\.\d+)*', '', t, flags=re.IGNORECASE)
    t = re.sub(r'[:\-–_]+', ' ', t)
    return ' '.join(t.split())


class AutoVideoHarvester:
    def __init__(self, mode: str = "main", codec: str = "h264", source: str = "all"):
        self.mode = mode.lower()  # "main" or "after_dark"
        if self.mode == "after-dark":
            self.mode = "after_dark"
        self.codec = codec.lower()  # "h264" or "hevc"
        self.source = source.lower()  # "all", "steamgriddb", "moewalls"
        
        self.resolver = TitleIdResolver()
        self.sgdb_client = SteamGridDBClient()
        
        self.log_file = PROJECT_ROOT / "catalog" / "data" / f"video_harvest_log_{self.mode}.json"
        self.log_data = self._load_log()
        
        self.catalog_path = PROJECT_ROOT / (CATALOG_PATH_AFTER_DARK if self.mode == "after_dark" else CATALOG_PATH_STANDARD)
        self.branch = "after-dark" if self.mode == "after_dark" else "main"
        self.folder_id = GDRIVE_AFTER_DARK_FOLDER_ID if self.mode == "after_dark" else GDRIVE_FOLDER_ID

    def _load_log(self) -> Dict[str, Any]:
        if self.log_file.exists():
            try:
                data = json.loads(self.log_file.read_text(encoding="utf-8"))
                data.setdefault("harvested_urls", {})
                data.setdefault("total_harvested", len(data["harvested_urls"]))
                data.setdefault("page_cursors", {})
                data.setdefault("query_cursor", 0)
                return data
            except Exception:
                pass
        return {
            "harvested_urls": {},
            "total_harvested": 0,
            "last_updated": "",
            "page_cursors": {},
            "query_cursor": 0
        }

    def _save_log(self):
        self.log_data["last_updated"] = datetime.now(timezone.utc).isoformat()
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.log_file.write_text(json.dumps(self.log_data, indent=2, ensure_ascii=False), encoding="utf-8")

    def is_url_harvested(self, url: str) -> bool:
        return url in self.log_data["harvested_urls"]

    def mark_harvested(self, url: str, info: Dict[str, Any]):
        self.log_data["harvested_urls"][url] = info
        self.log_data["total_harvested"] = len(self.log_data["harvested_urls"])
        self._save_log()

    def get_gdrive_token(self) -> Optional[str]:
        gdrive_cfg = GoogleDriveHelper.get_stored_config()
        refresh_tok = gdrive_cfg.get("refresh_token")
        if refresh_tok:
            refreshed = GoogleDriveHelper.refresh_access_token(refresh_tok)
            if refreshed:
                gdrive_cfg["token"] = refreshed
                GoogleDriveHelper.save_stored_config(gdrive_cfg)
                return refreshed
        # Fallback to direct access token if valid
        tok = gdrive_cfg.get("token")
        if tok:
            test = GoogleDriveClient.test_connection(tok)
            if test.get("ok"):
                return tok
        return None

    @staticmethod
    def is_nsfw_text(text: str) -> bool:
        t_low = text.lower()
        return any(kw in t_low for kw in NSFW_KEYWORDS)

    @staticmethod
    def is_suitable_for_after_dark(title: str, query: str) -> bool:
        """Strict validation: ensure wallpaper is genuine adult / ecchi / sensual / waifu / genre content."""
        t_low = title.lower()
        q_low = query.lower()

        # Reject obvious non-ecchi male shonen fighting or generic male wallpapers
        bad_males = [
            "sasuke", "naruto", "goku", "vegeta", "luffy", "zoro", "male", "boy",
            "chidori", "rasengan", "okabe", "rintarou", "deku", "all might",
            "tanjiro", "zenitsu", "inosuke", "gojo satoru", "sukuna", "eren"
        ]
        if any(bad in t_low for bad in bad_males):
            return False

        # Explicit sensual / ecchi / adult / anime genre keywords
        ecchi_keywords = [
            "bikini", "swimsuit", "bunny", "ecchi", "nsfw", "18+", "erotic", "nude",
            "naked", "cleavage", "lingerie", "boobs", "ass", "thighs", "waifu", "hentai",
            "sensual", "undressing", "sexy", "maid", "beach", "summer", "bath", "shower",
            "bed", "sleeping", "wet", "dress", "legs", "relaxing", "night", "flower",
            "girl", "neko", "catgirl", "yandere", "tsundere", "goth", "gothic",
            "cyberpunk girl", "schoolgirl", "vampire", "succubus", "witch", "princess", "bride"
        ]
        if any(k in t_low for k in ecchi_keywords):
            return True

        # Established iconic waifus & game heroines
        waifu_characters = [
            "2b", "a2", "tifa", "aerith", "pyra", "mythra", "purah", "bowsette", "boosette",
            "bayonetta", "catherine", "kangel", "monika", "prinz eugen", "taihou", "shinano",
            "atago", "marie rose", "honoka", "asuka", "yumi", "android 18", "lucy", "rebecca",
            "nikke", "stellar blade", "eve", "makima", "zero two", "marin kitagawa", "yor forger",
            "raiden", "yae miko", "ganyu", "hu tao", "furina", "kafka", "firefly", "acheron",
            "samus", "edelgard", "byleth", "aphrodite",
            # Visual Novel, Galge & Anime Heroines
            "chocola", "vanilla", "kurisu", "makise", "ryuko", "ryuuko", "satsuki",
            "chiaki", "nanami", "kyoko", "kirigiri", "junko", "enoshima", "mikan", "ibuki",
            "nagisa", "ushio", "sophie", "ryza", "saber", "arcueid", "arlecchino",
            "bridget", "baiken", "filia", "valentine", "miriam", "etna", "flonne",
            "shiranui", "kula", "shigure", "maple", "cinnamon", "azuki", "coconut"
        ]
        if any(w in t_low or w in q_low for w in waifu_characters):
            return True

        # Tag searches for After Dark are curated and trusted
        if q_low.startswith("tag:"):
            return True

        # If query is a targeted mature Switch game and wallpaper has no male flags, accept
        for _, gname, qlist in MATURE_SWITCH_GAMES:
            if any(q == q_low for q in qlist):
                return True

        return False

    def classify_after_dark_title(self, title: str, url: str) -> Tuple[str, str]:
        """Classifies an After Dark wallpaper into a specific game or dedicated franchise entry."""
        combined = (title + " " + url).lower()

        # 1. Dedicated Franchises
        if any(k in combined for k in ["genshin", "raiden", "yae miko", "ganyu", "hu tao", "furina", "arlecchino", "mona", "shenhe", "yelan", "clorinde"]):
            return ("0100EC0000000001", "Genshin Impact (Waifus)")
        if any(k in combined for k in ["blue archive", "ushio noa", "hanuma makoto", "iroha sunset", "akane bunny", "chiaki", "satsuki swimsuit", "toki blue"]):
            return ("0100EC0000000002", "Blue Archive (Swimsuit & Bunny)")
        if any(k in combined for k in ["chainsaw man", "makima", "power blood", "reze"]):
            return ("0100EC0000000003", "Chainsaw Man (Makima & Power)")
        if any(k in combined for k in ["nikke", "cinderella bikini", "anis nikke", "dorothy nikke", "elegg", "rapi nikke", "sugar nikke", "viper nikke"]):
            return ("0100EC0000000004", "GODDESS OF VICTORY: NIKKE")
        if any(k in combined for k in ["honkai", "star rail", "kafka", "firefly", "acheron", "black swan", "himeko", "silver wolf", "tingyun", "sparkle", "march 7th"]):
            return ("0100EC0000000005", "Honkai: Star Rail (Waifus)")
        if any(k in combined for k in ["zero two", "darling in the franxx", "ichigo darling"]):
            return ("0100EC0000000006", "Darling in the Franxx (Zero Two)")
        if any(k in combined for k in ["stellar blade", "eve nano", "eve stellar"]):
            return ("0100EC0000000007", "Stellar Blade (Eve)")
        if any(k in combined for k in ["bunny girl senpai", "mai sakurajima"]):
            return ("0100EC0000000008", "Rascal Does Not Dream (Mai Sakurajima)")
        if any(k in combined for k in ["yor forger", "yor spy", "spy x family"]):
            return ("0100EC0000000009", "SPY x FAMILY (Yor Forger)")
        if any(k in combined for k in ["zenless", "zzz", "ellen joe", "nicole demara", "zhu yuan"]):
            return ("0100EC000000000A", "Zenless Zone Zero")
        if any(k in combined for k in ["marin kitagawa", "my dress-up darling", "marin cosplay"]):
            return ("0100EC000000000B", "My Dress-Up Darling (Marin Kitagawa)")
        if any(k in combined for k in ["overlord", "albedo", "shalltear"]):
            return ("0100EC000000000C", "Overlord (Albedo & Shalltear)")
        if any(k in combined for k in ["re:zero", "re zero", "rem fallen", "rem re:zero", "emilia re:zero"]):
            return ("0100EC000000000D", "Re:Zero (Rem & Emilia)")
        if any(k in combined for k in ["konosuba", "megumin", "aqua konosuba", "darkness konosuba"]):
            return ("0100EC000000000E", "KonoSuba (Megumin & Aqua)")
        if any(k in combined for k in ["hololive", "houshou marine", "gawr gura", "calliope", "pekora"]):
            return ("0100EC000000000F", "Hololive VTubers (Marine, Gura, Calli)")
        if any(k in combined for k in ["high school dxd", "dxd", "rias gremory", "akeno himejima"]):
            return ("0100EC0000000010", "High School DxD (Rias & Akeno)")
        if any(k in combined for k in ["to love ru", "to love-ru", "lala satalin", "golden darkness", "momo to love"]):
            return ("0100EC0000000011", "To Love-Ru Darkness")

        # 2. Key Switch Titles
        if any(k in combined for k in ["nier", "2b", "a2"]):
            return ("01005C000B2AE000", "NieR:Automata The End of YoRHa Edition")
        if any(k in combined for k in ["tifa", "aerith", "final fantasy"]):
            return ("0100A5B00BDC6000", "Final Fantasy VII")
        if any(k in combined for k in ["azur lane", "prinz eugen", "taihou", "atago", "shinano"]):
            return ("0100A1900F3BA000", "Azur Lane: Crosswave")
        if any(k in combined for k in ["cyberpunk", "lucy", "rebecca"]):
            return ("0100435942450000", "Cyberpunk 2077")
        if any(k in combined for k in ["fate", "saber", "scathach", "rin tohsaka"]):
            return ("010023301E41C000", "Fate/Stay Night Remastered")
        if any(k in combined for k in ["senran kagura", "senran"]):
            return ("010099400D28E000", "Senran Kagura Peach Ball")
        if any(k in combined for k in ["dead or alive", "marie rose", "honoka"]):
            return ("010034200B5B0000", "Dead or Alive Xtreme 3 Scarlet")
        if any(k in combined for k in ["atelier ryza", "ryza"]):
            return ("010009B00E71A000", "Atelier Ryza: Ever Darkness & the Secret Hideout")
        if any(k in combined for k in ["date a live", "kurumi"]):
            return ("01001F000CB7E000", "Date A Live: Rio Reincarnation")
        if any(k in combined for k in ["sword art online", "sao", "asuna", "sinon"]):
            return ("0100C9E00CA3E000", "Sword Art Online: Fatal Bullet Complete Edition")
        if any(k in combined for k in ["witcher", "yennefer", "triss", "ciri"]):
            return ("0100E8B00BDC6000", "The Witcher 3: Wild Hunt - Complete Edition")

        return ("0000000000000000", "★ Коллекция After Dark: Ecchi & Waifus")

    def search_moewalls_articles(self, query: str, limit: int = 5, page: int = 1) -> List[Dict[str, str]]:
        if query.startswith("tag:"):
            tag_name = query.split(":", 1)[1].strip()
            url = f"https://moewalls.com/tag/{tag_name}/page/{page}/" if page > 1 else f"https://moewalls.com/tag/{tag_name}/"
        elif page > 1:
            url = f"https://moewalls.com/page/{page}/?s={urllib.parse.quote(query)}"
        else:
            url = f"https://moewalls.com/?s={urllib.parse.quote(query)}"
        req = urllib.request.Request(url, headers=HEADERS)
        results = []
        try:
            html = urllib.request.urlopen(req, timeout=12).read().decode('utf-8', errors='ignore')
            articles = re.findall(r'<article[^>]*>.*?<a href="([^"]+)"[^>]*rel="bookmark">(.*?)</a>', html, re.DOTALL)
            if not articles:
                articles = re.findall(r'<article[^>]*>.*?<a href="([^"]+)"[^>]*title="([^"]+)"', html, re.DOTALL)
            for page_url, raw_title in articles:
                clean_title = re.sub('<[^<]+?>', '', raw_title).strip()
                if self.mode == "main" and self.is_nsfw_text(clean_title):
                    continue
                if self.mode == "after_dark" and not self.is_suitable_for_after_dark(clean_title, query):
                    continue
                results.append({"title": clean_title, "page_url": page_url})
                if len(results) >= limit:
                    break
        except Exception as e:
            if "404" not in str(e):
                print(f"[!] Moewalls search error for '{query}' (p.{page}): {e}")
        return results

    def extract_direct_video_url(self, page_url: str) -> Optional[str]:
        req = urllib.request.Request(page_url, headers=HEADERS)
        try:
            html = urllib.request.urlopen(req, timeout=12).read().decode('utf-8', errors='ignore')
            vids = re.findall(r'<source[^>]*src="([^"]+\.(?:webm|mp4))"', html)
            if not vids:
                vids = re.findall(r'href="([^"]+\.(?:webm|mp4))"', html)
            if vids:
                v_url = vids[0]
                if v_url.startswith("/"):
                    v_url = "https://moewalls.com" + v_url
                return v_url
        except Exception as e:
            print(f"[!] Video extraction error for {page_url}: {e}")
        return None

    def check_audio_stream(self, raw_path: Path) -> bool:
        try:
            cmd = [
                "ffprobe", "-v", "error",
                "-select_streams", "a:0",
                "-show_entries", "stream=codec_name",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(raw_path)
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            return bool(res.stdout.strip())
        except Exception:
            return False

    def transcode_video(self, raw_path: Path, out_mp4: Path, out_thumb: Path) -> tuple:
        out_mp4.parent.mkdir(parents=True, exist_ok=True)
        out_thumb.parent.mkdir(parents=True, exist_ok=True)
        is_hevc = (self.codec == "hevc")
        has_audio = self.check_audio_stream(raw_path)

        cmd = [
            "ffmpeg", "-y", "-nostdin",
            "-t", "30",
            "-i", str(raw_path),
            "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=black",
            "-threads", "4",
            "-r", "30",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart"
        ]
        if has_audio:
            cmd.extend(["-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2"])
        else:
            cmd.append("-an")
        if is_hevc:
            cmd.extend([
                "-c:v", "libx265",
                "-preset", "ultrafast",
                "-tag:v", "hvc1",
                "-b:v", "1800k", "-maxrate", "2400k", "-bufsize", "4000k"
            ])
        else:
            cmd.extend([
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-tune", "fastdecode",
                "-profile:v", "high", "-level", "4.1",
                "-b:v", "2500k", "-maxrate", "3000k", "-bufsize", "5000k"
            ])
        cmd.append(str(out_mp4))

        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=45)
        except Exception as e:
            print(f"[!] FFmpeg transcode error: {e}")
            return False, False

        # Thumbnail
        cmd_thumb = [
            "ffmpeg", "-y", "-nostdin",
            "-ss", "00:00:01",
            "-i", str(out_mp4),
            "-vframes", "1",
            "-vf", "scale=640:360:force_original_aspect_ratio=decrease,pad=640:360:(ow-iw)/2:(oh-ih)/2:color=black",
            str(out_thumb)
        ]
        try:
            subprocess.run(cmd_thumb, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        except Exception:
            pass

        return True, has_audio

    def process_and_upload_asset(
        self,
        asset_url: str,
        title_id: str,
        game_title: str,
        var_name: str,
        author: str,
        style: str,
        catalog: Dict[str, Any],
        games_map: Dict[str, Any],
        gdrive_token: str
    ) -> bool:
        """Download raw asset, transcode to 720p 30fps Switch format, upload to Drive, and register in catalog."""
        var_id = "v_" + hashlib.md5(asset_url.encode()).hexdigest()[:8]
        ext = ".webm" if ".webm" in asset_url else (".webp" if ".webp" in asset_url else ".mp4")
        raw_file = RAW_DIR / f"{var_id}{ext}"
        out_mp4 = P720_DIR / f"{var_id}.mp4"
        out_thumb = THUMB_DIR / f"{var_id}.jpg"

        try:
            if not raw_file.exists() or raw_file.stat().st_size == 0:
                print(f"  -> Downloading stream ({ext})...")
                req = urllib.request.Request(asset_url, headers=HEADERS)
                with urllib.request.urlopen(req, timeout=30) as resp, open(raw_file, 'wb') as vf:
                    vf.write(resp.read())

            if not raw_file.exists() or raw_file.stat().st_size < 1000:
                print("  [!] Downloaded file is invalid or too small.")
                return False

            print(f"  -> Transcoding to 720p 30fps {self.codec.upper()} (with audio auto-detection)...")
            ok, has_audio = self.transcode_video(raw_file, out_mp4, out_thumb)
            if not ok or not out_mp4.exists() or out_mp4.stat().st_size == 0:
                return False

            print(f"  -> Uploading to Google Drive...")
            up_res = GoogleDriveClient.upload_file(out_mp4, self.folder_id, gdrive_token)
            fid = up_res.get("id")
            if not fid:
                print("  [!] Failed to upload to Google Drive.")
                return False

            GoogleDriveClient.make_public(fid, gdrive_token)
            direct_url = GoogleDriveHelper.to_direct_download_url(fid)
            preview_url = GoogleDriveHelper.to_preview_url(fid)

            size_bytes = out_mp4.stat().st_size
            h_sha = hashlib.sha256(out_mp4.read_bytes()).hexdigest().upper()

            variant_entry = {
                "id": var_id,
                "name": var_name or "Atmospheric Theme",
                "style": style,
                "version": "1.0",
                "url": direct_url,
                "previewUrl": preview_url,
                "sizeBytes": size_bytes,
                "sha256": h_sha,
                "durationSec": 30.0,
                "author": author,
                "codec": self.codec,
                "width": 1280,
                "height": 720,
                "fps": 30.0,
                "hasAudio": has_audio,
                "notes": f"Switch 720p 30fps {self.codec.upper()} | {var_name}" + (" | ЗВУК" if has_audio else "")
            }

            tid_upper = title_id.upper()
            if tid_upper not in games_map:
                g_entry = {
                    "titleId": tid_upper,
                    "title": game_title,
                    "publisher": "Nintendo Switch" if tid_upper != "0000000000000000" else "H3H Studio",
                    "iconUrl": f"https://raw.githubusercontent.com/Langegen/switch-game-collection/main/covers/{tid_upper}.jpg" if tid_upper != "0000000000000000" else "",
                    "variants": []
                }
                catalog["games"].append(g_entry)
                games_map[tid_upper] = g_entry

            games_map[tid_upper]["variants"].append(variant_entry)

            self.mark_harvested(asset_url, {
                "title": var_name,
                "titleId": tid_upper,
                "gameName": game_title,
                "varId": var_id,
                "driveId": fid,
                "mode": self.mode,
                "codec": self.codec,
                "author": author
            })
            return True

        except Exception as ex:
            print(f"  [!] Processing error: {ex}")
            return False

    def harvest_from_steamgriddb(self, limit: int, catalog: Dict[str, Any], games_map: Dict[str, Any], gdrive_token: str) -> int:
        """Harvest animated heroes and motion art from SteamGridDB across Switch library."""
        harvested = 0
        targets: List[Tuple[str, str, str]] = list(PRIORITY_STEAMGRID_GAMES)

        db_path = PROJECT_ROOT / "studio" / "h3h_studio" / "data" / "switch_titles_db.json"
        if db_path.exists():
            try:
                switch_db = json.loads(db_path.read_text(encoding="utf-8"))
                existing_tids = {t[0] for t in targets}
                for entry in switch_db:
                    tid = entry.get("titleId", "").upper()
                    raw_title = entry.get("title", "")
                    if len(tid) == 16 and tid not in existing_tids:
                        c_title = clean_switch_title(raw_title)
                        if len(c_title) >= 3:
                            targets.append((tid, raw_title, c_title))
            except Exception as e:
                print(f"[!] Warning reading switch_titles_db: {e}")

        targets.sort(key=lambda t: len(games_map.get(t[0].upper(), {}).get("variants", [])))

        for tid, full_game_name, search_query in targets:
            if harvested >= limit:
                break

            current_vars = len(games_map.get(tid.upper(), {}).get("variants", []))
            if current_vars >= 4:
                continue

            print(f"\n🔍 [SteamGridDB] Searching for '{search_query}' (ID: {tid})...")
            try:
                sg_results = self.sgdb_client.search_game(search_query)
            except Exception as e:
                print(f"  [!] SteamGridDB search failed: {e}")
                continue

            if not sg_results:
                continue

            matched_game = None
            q_low = search_query.lower()
            for cand in sg_results:
                cand_name = cand.get("name", "").lower()
                if q_low in cand_name or cand_name in q_low:
                    matched_game = cand
                    break

            if not matched_game:
                matched_game = sg_results[0]

            sg_id = matched_game["id"]
            sg_name = matched_game["name"]

            candidates = []
            try:
                heroes = self.sgdb_client.get_animated_heroes(sg_id)
                for h in heroes:
                    if self.mode == "main" and h.get("nsfw"):
                        continue
                    u = h.get("url") or h.get("thumb")
                    if u and not self.is_url_harvested(u):
                        author = h.get("author", {}).get("name", "SteamGridDB Community")
                        candidates.append((u, f"{sg_name} Hero", author, "Community Hero"))
            except Exception as e:
                print(f"  [!] Hero fetch error: {e}")

            if not candidates:
                try:
                    grids = self.sgdb_client.get_animated_grids(sg_id)
                    for gr in grids:
                        if self.mode == "main" and gr.get("nsfw"):
                            continue
                        u = gr.get("url") or gr.get("thumb")
                        if u and not self.is_url_harvested(u):
                            author = gr.get("author", {}).get("name", "SteamGridDB Community")
                            candidates.append((u, f"{sg_name} Motion Cover", author, "Motion Grid"))
                except Exception as e:
                    print(f"  [!] Grid fetch error: {e}")

            for asset_url, var_name, author, style in candidates:
                if harvested >= limit:
                    break
                print(f"\n[*] Harvesting SteamGridDB asset for '{sg_name}': {asset_url}")
                ok = self.process_and_upload_asset(
                    asset_url=asset_url,
                    title_id=tid,
                    game_title=full_game_name,
                    var_name=var_name,
                    author=author,
                    style=style,
                    catalog=catalog,
                    games_map=games_map,
                    gdrive_token=gdrive_token
                )
                if ok:
                    harvested += 1
                    print(f"  [+] Success! ({harvested}/{limit}) Added {var_name} to {full_game_name}")

        return harvested

    def harvest_from_moewalls(self, limit: int, catalog: Dict[str, Any], games_map: Dict[str, Any], gdrive_token: str) -> int:
        """Harvest cinematic live video wallpapers from MoeWalls with targeted Switch titles & continuous pagination."""
        query_queue: List[Tuple[str, str, str]] = []  # (titleId, gameName, query)

        if self.mode == "main":
            # Curated SFW gaming targets
            for tid, gname, qlist in POPULAR_SWITCH_SFW_GAMES:
                for q in qlist:
                    query_queue.append((tid, gname, q))
            # Games in catalog missing variants
            for g in catalog.get("games", []):
                tid = g.get("titleId", "").upper()
                if tid not in ("0000000000000000", "0000000000000001") and len(g.get("variants", [])) < 3:
                    c_title = clean_switch_title(g.get("title", ""))
                    if 4 <= len(c_title) <= 28 and not self.is_nsfw_text(c_title):
                        query_queue.append((tid, c_title, c_title))
        else:
            # 1. Prioritize Switch games with mature / waifu / adult filters
            for tid, gname, qlist in MATURE_SWITCH_GAMES:
                for q in qlist:
                    query_queue.append((tid, gname, q))
            # 2. General waifus and adult collections
            for q in AFTER_DARK_GENERAL_QUERIES:
                query_queue.append(("0000000000000000", "★ Коллекция After Dark (Свободный выбор)", q))

        if not query_queue:
            return 0

        harvested = 0
        q_cursor = self.log_data.get("query_cursor", 0) % len(query_queue)
        page_cursors = self.log_data.get("page_cursors", {})

        queries_to_try = 30
        for i in range(queries_to_try):
            if harvested >= limit:
                break
            idx = (q_cursor + i) % len(query_queue)
            tid, default_game_name, q = query_queue[idx]
            current_p = page_cursors.get(q, 1)

            print(f"\n🔍 [MoeWalls] Searching: '{q}' (Target: {default_game_name}, Page: {current_p})...")
            articles = self.search_moewalls_articles(q, limit=4, page=current_p)
            found_any = False

            for art in articles:
                if harvested >= limit:
                    break
                page_url = art["page_url"]
                if self.is_url_harvested(page_url):
                    continue

                vid_url = self.extract_direct_video_url(page_url)
                if not vid_url or self.is_url_harvested(vid_url):
                    self.mark_harvested(page_url, {"page": True, "skipped": True})
                    continue

                raw_title = art["title"].replace("Live Wallpaper", "").strip(" -–")
                clean_name = re.sub(r'\(.*?\)', '', raw_title).strip()
                if len(clean_name) > 40:
                    clean_name = clean_name[:40].strip()

                final_tid = tid
                final_name = default_game_name
                if self.mode == "after_dark" and tid == "0000000000000000":
                    c_tid, c_name = self.classify_after_dark_title(clean_name, vid_url)
                    final_tid = c_tid
                    final_name = c_name

                print(f"\n[*] Harvesting MoeWalls video: '{clean_name}' (Target: {final_name} [{final_tid}])")
                ok = self.process_and_upload_asset(
                    asset_url=vid_url,
                    title_id=final_tid,
                    game_title=final_name,
                    var_name=clean_name or "Atmospheric Theme",
                    author="MoeWalls / Community",
                    style="Ecchi / Mature" if self.mode == "after_dark" else "Cinematic",
                    catalog=catalog,
                    games_map=games_map,
                    gdrive_token=gdrive_token
                )
                if ok:
                    self.mark_harvested(page_url, {"page": True, "vid": vid_url})
                    harvested += 1
                    found_any = True
                    print(f"  [+] Success! ({harvested}/{limit}) Added {clean_name} to {default_game_name}")

            # Advance page for this query if current page had no new items
            if not articles or not found_any:
                page_cursors[q] = current_p + 1 if current_p < 15 else 1

        self.log_data["query_cursor"] = (q_cursor + queries_to_try) % len(query_queue)
        self.log_data["page_cursors"] = page_cursors
        self._save_log()

        return harvested

    def harvest_stream(self, limit: int = 10) -> int:
        print(f"\n==================================================")
        print(f"[*] Starting Video Harvester (Mode: {self.mode.upper()}, Source: {self.source.upper()}, Codec: {self.codec.upper()})")
        print(f"[*] Target Catalog: {self.catalog_path}")
        print(f"[*] Target GDrive Folder ID: {self.folder_id}")
        print(f"==================================================")

        gdrive_token = self.get_gdrive_token()
        if not gdrive_token:
            print("[-] Error: Failed to obtain Google Drive token.")
            return 0

        if not self.catalog_path.exists():
            print(f"[-] Catalog file not found: {self.catalog_path}")
            return 0

        catalog = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        games_map = {g["titleId"].upper(): g for g in catalog.get("games", [])}

        harvested_count = 0

        # Run SteamGridDB if requested and main mode
        if self.source in ["all", "steamgriddb"] and self.mode == "main":
            sg_limit = limit if self.source == "steamgriddb" else max(1, limit // 2)
            c = self.harvest_from_steamgriddb(sg_limit, catalog, games_map, gdrive_token)
            harvested_count += c

        # Run MoeWalls if requested or after-dark
        remaining = limit - harvested_count
        if remaining > 0 and (self.source in ["all", "moewalls"] or self.mode == "after_dark"):
            c = self.harvest_from_moewalls(remaining, catalog, games_map, gdrive_token)
            harvested_count += c

        if harvested_count > 0:
            catalog["updatedAt"] = datetime.now(timezone.utc).isoformat()
            catalog["totalGames"] = len(catalog["games"])
            catalog["totalVariants"] = sum(len(g.get("variants", [])) for g in catalog["games"])

            with open(self.catalog_path, "w", encoding="utf-8") as cf:
                json.dump(catalog, cf, ensure_ascii=False, indent=2)

            print(f"\n[+] Catalog updated: {catalog['totalGames']} games, {catalog['totalVariants']} variants.")
            print(f"[*] Pushing updates to GitHub branch '{self.branch}'...")

            gh_token, _ = GitHubPublisher.get_stored_credentials()
            repo_url = f"https://x-access-token:{gh_token}@github.com/Holy3holy-dev/H3H-Backgrounds.git"
            rel_cat = str(self.catalog_path.relative_to(PROJECT_ROOT)).replace("\\", "/")

            # Pull remote changes first to prevent collision with Telegram bot community uploads
            try:
                subprocess.run(["git", "pull", "--rebase", repo_url, "main"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

            subprocess.run(["git", "add", rel_cat, str(self.log_file.relative_to(PROJECT_ROOT))], check=True)
            subprocess.run(["git", "commit", "-m", f"feat(harvest): automated batch harvest {harvested_count} {self.mode} video themes ({self.codec.upper()})"], check=True)
            
            for push_att in range(1, 4):
                try:
                    if self.mode == "after_dark":
                        subprocess.run(["git", "push", "--force", repo_url, "HEAD:refs/heads/after-dark"], check=True)
                    subprocess.run(["git", "push", repo_url, "HEAD:refs/heads/main"], check=True)
                    print(f"[SUCCESS] Successfully pushed {harvested_count} new video backgrounds to GitHub!")
                    break
                except Exception as pe:
                    print(f"[!] Git push attempt {push_att}/3 failed: {pe}. Rebasing...")
                    subprocess.run(["git", "pull", "--rebase", repo_url, "main"], check=False)
                    time.sleep(2)

        return harvested_count


def main():
    parser = argparse.ArgumentParser(description="H3H Automated Video Harvester Pipeline")
    parser.add_argument("--mode", choices=["main", "after-dark", "all"], default="all", help="Target catalog mode")
    parser.add_argument("--source", choices=["all", "steamgriddb", "moewalls"], default="moewalls", help="Source provider")
    parser.add_argument("--codec", choices=["h264", "hevc"], default="h264", help="Video codec (h264 or hevc)")
    parser.add_argument("--limit", type=int, default=5, help="Number of backgrounds to harvest per batch")
    parser.add_argument("--continuous", action="store_true", help="Run continuously in a loop ('на поток')")
    parser.add_argument("--interval", type=int, default=30, help="Interval in seconds between continuous batches")
    parser.add_argument("--gdrive-token", type=str, default=None, help="Google Drive OAuth Access Token (ya29...)")
    parser.add_argument("--refresh-token", type=str, default=None, help="Google Drive OAuth Refresh Token (1//...)")
    args = parser.parse_args()

    # Update credentials if provided via CLI
    if args.gdrive_token or args.refresh_token:
        cfg = GoogleDriveHelper.get_stored_config()
        if args.gdrive_token:
            cfg["token"] = args.gdrive_token.strip()
        if args.refresh_token:
            cfg["refresh_token"] = args.refresh_token.strip()
        GoogleDriveHelper.save_stored_config(cfg)
        print("[+] Updated Google Drive credentials in config.")

    modes = ["main", "after-dark"] if args.mode == "all" else [args.mode]

    batch_num = 1
    while True:
        print(f"\n>>> [BATCH {batch_num}] Starting harvesting stream at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} <<<")
        for m in modes:
            try:
                h = AutoVideoHarvester(mode=m, codec=args.codec, source=args.source)
                h.harvest_stream(limit=args.limit)
            except Exception as ex:
                print(f"[!] Harvester stream error in mode {m}: {ex}")

        if not args.continuous:
            break

        print(f"\n[INFO] Batch {batch_num} complete. Sleeping {args.interval}s before next stream batch... (Press Ctrl+C to stop)")
        time.sleep(args.interval)
        batch_num += 1

if __name__ == "__main__":
    main()
