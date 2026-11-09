"""Patch script to upgrade auto_video_harvester.py for strict Switch 1 Wallpaper Engine repository harvesting."""
from pathlib import Path

p = Path("scripts/auto_video_harvester.py")
text = p.read_text(encoding="utf-8")

# 1. Remove Cyberpunk 2077 from MATURE_SWITCH_GAMES and classify_after_dark_title
text = text.replace('    ("0100435942450000", "Cyberpunk 2077", ["lucy cyberpunk", "rebecca cyberpunk", "lucy edgerunners"]),\n', '')
text = text.replace('        if any(k in combined for k in ["cyberpunk", "lucy", "rebecca"]):\n            return ("0100435942450000", "Cyberpunk 2077")\n', '')
text = text.replace(', "tag:cyberpunk"', '')

# 2. Replace POPULAR_SWITCH_SFW_GAMES with rich Wallpaper Engine repository tag mappings for authentic Switch 1 games
old_sfw_start = text.index("# Known popular Switch games & famous Homebrew ports for SFW Main catalog\nPOPULAR_SWITCH_SFW_GAMES = [")
old_sfw_end = text.index("NSFW_KEYWORDS = [")

new_sfw_block = '''# Known popular Switch 1 games mapped directly to Wallpaper Engine repository /games/ tags & queries
POPULAR_SWITCH_SFW_GAMES = [
    # Nintendo Switch 1 Flagships & Exclusives
    ("0100F2C0115B6000", "The Legend of Zelda: Tears of the Kingdom", ["tag:tears-of-the-kingdom", "tag:the-legend-of-zelda", "tears of the kingdom", "zelda link"]),
    ("01007EF00011E000", "The Legend of Zelda: Breath of the Wild", ["tag:breath-of-the-wild", "breath of the wild", "zelda breath of the wild"]),
    ("0100000000010000", "Super Mario Odyssey", ["tag:super-mario", "tag:mario", "super mario", "mario bowser"]),
    ("010015100B514000", "Super Mario Bros. Wonder", ["super mario bros wonder", "mario wonder", "princess daisy mario"]),
    ("0100152000022000", "Mario Kart 8 Deluxe", ["mario kart", "rainbow road mario"]),
    ("01000A10041EA000", "Super Smash Bros. Ultimate", ["tag:super-smash-bros", "super smash bros"]),
    ("01002DA013484000", "Metroid Dread", ["tag:metroid", "tag:samus-aran", "metroid dread", "samus aran"]),
    ("010012101468C000", "Metroid Prime Remastered", ["metroid prime", "samus metroid"]),
    ("01006F8002326000", "Animal Crossing: New Horizons", ["tag:animal-crossing", "animal crossing"]),
    ("0100C2500FC20000", "Splatoon 3", ["tag:splatoon", "splatoon"]),
    ("01003BC0000A0000", "Kirby and the Forgotten Land", ["tag:kirby", "kirby"]),
    ("0100FF500E34A000", "Xenoblade Chronicles Definitive Edition", ["tag:xenoblade-chronicles", "xenoblade chronicles"]),
    ("0100E95004038000", "Xenoblade Chronicles 2", ["tag:xenoblade-chronicles-2", "xenoblade 2", "pyra mythra"]),
    ("010074F013262000", "Xenoblade Chronicles 3", ["xenoblade chronicles 3", "xenoblade 3"]),
    ("010055D009F78000", "Fire Emblem: Three Houses", ["tag:fire-emblem", "fire emblem"]),
    ("01001F5010DFA000", "Pokemon Legends: Arceus", ["tag:pokemon", "pokemon arceus", "pokemon gengar", "pokemon charizard", "pokemon rayquaza", "pokemon umbreon"]),
    ("0100A3D008C5C000", "Pokemon Scarlet", ["pokemon pikachu", "pokemon eevee", "pokemon mewtwo", "pokemon lugia"]),
    ("01004A4010FEA000", "Bayonetta 3", ["tag:bayonetta", "bayonetta"]),
    ("0100DCA0064A6000", "Luigi's Mansion 3", ["luigi mansion", "king boo"]),

    # Major RPGs & Masterpieces on Switch 1
    ("01003D100E9C6000", "The Witcher 3: Wild Hunt", ["tag:the-witcher-3-wild-hunt", "tag:the-witcher", "tag:geralt-of-rivia", "tag:ciri", "witcher 3"]),
    ("01005CA01580E000", "Persona 5 Royal", ["tag:persona-5", "tag:persona", "persona 5"]),
    ("0100DCD01525A000", "Persona 3 Portable", ["tag:persona-3", "persona 3"]),
    ("010062B01525C000", "Persona 4 Golden", ["tag:persona-4", "persona 4"]),
    ("01005C000B2AE000", "NieR:Automata", ["tag:nier-automata", "tag:nier", "nier automata"]),
    ("01004AB00A260000", "Dark Souls: Remastered", ["tag:dark-souls", "tag:dark-souls-iii", "dark souls", "bonfire dark souls", "artorias"]),
    ("010028D005A3C000", "The Elder Scrolls V: Skyrim", ["tag:skyrim", "tag:the-elder-scrolls", "skyrim"]),
    ("01007820196A6000", "Red Dead Redemption", ["tag:red-dead-redemption", "red dead redemption"]),
    ("0100B04011742000", "Monster Hunter Rise", ["tag:monster-hunter", "monster hunter"]),
    ("0100A5B00BDC6000", "Final Fantasy VII", ["tag:final-fantasy-vii", "tag:final-fantasy", "tag:cloud-strife", "tag:sephiroth", "final fantasy vii"]),
    ("01004BC0166CC000", "Crisis Core: Final Fantasy VII Reunion", ["zack fair", "crisis core"]),
    ("010069C01AB82000", "Shin Megami Tensei V: Vengeance", ["shin megami tensei"]),
    ("010057D006492000", "Octopath Traveler", ["octopath traveler"]),
    ("01006C300E9F0000", "Dragon Quest XI S", ["dragon quest"]),
    ("01001B300B9BE000", "Diablo III: Eternal Collection", ["tag:diablo", "diablo"]),
    ("0100D870045B6000", "DARKSIDERS GENESIS", ["tag:darksiders", "darksiders"]),

    # Action, Shooters & Iconic Hits on Switch 1
    ("01000B900D8B0000", "DOOM Eternal", ["tag:doom-eternal", "tag:doom", "tag:doom-slayer", "doom eternal", "doom slayer"]),
    ("01007C000E5B2000", "Devil May Cry 3 Special Edition", ["tag:devil-may-cry", "tag:vergil", "tag:dante", "devil may cry"]),
    ("010099A00BC1E000", "Resident Evil 4", ["tag:resident-evil", "tag:leon-s-kennedy", "tag:ada-wong", "resident evil"]),
    ("01003F00163CE000", "Batman: Arkham Trilogy", ["tag:batman-arkham", "tag:batman", "batman arkham"]),
    ("01008C8012920000", "Dying Light: Platinum Edition", ["tag:dying-light", "dying light"]),
    ("010053500D3A8000", "Assassin's Creed: The Rebel Collection", ["tag:assassins-creed", "assassins creed"]),
    ("010038800C3DC000", "BioShock Remastered", ["tag:bioshock", "bioshock"]),
    ("010065000C3DE000", "BioShock Infinite", ["bioshock infinite"]),
    ("010014200B0D0000", "Metro 2033 Redux", ["tag:metro", "metro 2033", "metro exodus"]),
    ("01000F900C404000", "Borderlands 2", ["tag:borderlands", "borderlands"]),
    ("0100A6901170A000", "Need for Speed: Hot Pursuit Remastered", ["tag:need-for-speed", "need for speed"]),
    ("0100ABD01785C000", "Portal Companion Collection", ["tag:portal", "portal 2"]),
    ("010042400D600000", "No Man's Sky", ["tag:no-mans-sky", "no mans sky"]),
    ("0100E5F00E88C000", "Subnautica", ["tag:subnautica", "subnautica"]),
    ("0100F2200C984000", "Mortal Kombat 11", ["tag:mortal-kombat", "mortal kombat"]),
    ("0100C960066EE000", "Street Fighter 30th Anniversary Collection", ["tag:street-fighter", "street fighter"]),
    ("0100AB401F136000", "Guilty Gear -Strive-", ["tag:guilty-gear", "guilty gear"]),
    ("010031D00D59C000", "Overwatch 2", ["tag:overwatch", "overwatch"]),
    ("01005D6010402000", "Apex Legends", ["tag:apex-legends", "apex legends"]),
    ("0100A250097F0000", "Warframe", ["tag:warframe", "warframe"]),
    ("010025400AECE000", "Fortnite", ["tag:fortnite", "fortnite"]),
    ("01004060153FA000", "Sonic Frontiers", ["tag:sonic-the-hedgehog", "tag:shadow-the-hedgehog", "sonic frontiers", "sonic"]),
    ("0100092021C80000", "Tomb Raider I-III Remastered", ["tag:tomb-raider", "lara croft"]),
    ("010055500D850000", "Castlevania Anniversary Collection", ["tag:castlevania", "castlevania"]),

    # Beloved Indie Masterpieces on Switch 1
    ("010036500ECF2000", "Hollow Knight", ["tag:hollow-knight", "hollow knight"]),
    ("010052300B254000", "Hades", ["tag:hades", "hades zagreus"]),
    ("01008C3005A66000", "Dead Cells", ["tag:dead-cells", "dead cells"]),
    ("0100698009C6E000", "Blasphemous", ["tag:blasphemous", "blasphemous"]),
    ("010079C009494000", "Cuphead", ["tag:cuphead", "cuphead"]),
    ("01002B30028F6000", "Celeste", ["tag:celeste", "celeste"]),
    ("010086C00AF7C000", "Ori and the Will of the Wisps", ["tag:ori", "ori and the will of the wisps", "ori and the blind forest"]),
    ("0100D71004694000", "Minecraft", ["tag:minecraft", "minecraft"]),
    ("0100646009FBE000", "Terraria", ["tag:terraria", "terraria"]),
    ("010093800B8C8000", "Stardew Valley", ["tag:stardew-valley", "stardew valley"]),
    ("010080B00AD66000", "Undertale", ["tag:undertale", "tag:deltarune", "undertale"]),
    ("01002AC014DF8000", "OMORI", ["tag:omori", "omori"]),
    ("01002E7016C46000", "Cult of the Lamb", ["tag:cult-of-the-lamb", "cult of the lamb"]),
    ("010097100EDD6000", "Little Nightmares II", ["tag:little-nightmares", "little nightmares"]),
    ("01003DC0144B6000", "Outer Wilds", ["tag:outer-wilds", "outer wilds"]),
    ("010029600D56A000", "Katana ZERO", ["tag:katana-zero", "katana zero"]),
    ("0100307018934000", "SIGNALIS", ["tag:signalis", "signalis"]),
    ("0100AF800D570000", "gris", ["tag:gris", "gris"])
]

'''

text = text[:old_sfw_start] + new_sfw_block + text[old_sfw_end:]

# 3. Enforce strict /games/ category filter in search_moewalls_articles for main mode
old_search_cond = '''                clean_title = re.sub('<[^<]+?>', '', raw_title).strip()
                if self.mode == "main" and self.is_nsfw_text(clean_title):
                    continue'''

new_search_cond = '''                clean_title = re.sub('<[^<]+?>', '', raw_title).strip()
                if self.mode == "main":
                    if "/games/" not in page_url:
                        continue
                    if self.is_nsfw_text(clean_title):
                        continue'''

assert old_search_cond in text, "old_search_cond not found"
text = text.replace(old_search_cond, new_search_cond)

# 4. Replace harvest_from_moewalls queue logic so it ONLY harvests authentic curated Switch 1 games (no 7000-DB blind guessing, no < 4 cap)
old_queue_start = text.index("        if self.mode == \"main\":\n            # 1. Curated SFW gaming targets")
old_queue_end = text.index("        if not query_queue:")

new_queue_block = '''        if self.mode == "main":
            # Strictly curated Switch 1 games mapped to Wallpaper Engine /games/ repository tags & queries
            for tid, gname, qlist in POPULAR_SWITCH_SFW_GAMES:
                vcount = len(games_map.get(tid.upper(), {}).get("variants", []))
                if vcount < 40:
                    for q in qlist:
                        query_queue.append((tid, gname, q))
        else:
            # 1. Prioritize Switch games with mature / waifu / adult filters
            for tid, gname, qlist in MATURE_SWITCH_GAMES:
                for q in qlist:
                    query_queue.append((tid, gname, q))
            # 2. General waifus and adult collections
            for q in AFTER_DARK_GENERAL_QUERIES:
                query_queue.append(("0000000000000000", "★ Коллекция After Dark (Свободный выбор)", q))

'''

text = text[:old_queue_start] + new_queue_block + text[old_queue_end:]

# 5. Remove the < 4 cap in priority_count and loop inside harvest_from_moewalls
text = text.replace('if len(games_map.get(tid.upper(), {}).get("variants", [])) < 4:', 'if len(games_map.get(tid.upper(), {}).get("variants", [])) < 40:')
text = text.replace('if tid != "0000000000000000" and len(games_map.get(tid.upper(), {}).get("variants", [])) >= 4:', 'if tid != "0000000000000000" and len(games_map.get(tid.upper(), {}).get("variants", [])) >= 40:')

p.write_text(text, encoding="utf-8")
print("PATCHED auto_video_harvester.py OK")
