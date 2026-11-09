from pathlib import Path
import re

HARVESTER_PATH = Path("scripts/auto_video_harvester.py")
content = HARVESTER_PATH.read_text(encoding="utf-8").replace("\r\n", "\n")

# 1. Expand POPULAR_SWITCH_SFW_GAMES
old_sfw_anchor = '    ("010093800B8C8000", "Stardew Valley", ["stardew valley sunset", "stardew valley farm"])\n]'
new_sfw_additions = """    ("010093800B8C8000", "Stardew Valley", ["stardew valley sunset", "stardew valley farm"]),

    # Major First-Party & Top Switch Exclusives
    ("010015100B514000", "Super Mario Bros. Wonder", ["mario wonder", "super mario bros wonder"]),
    ("0100BC0018138000", "Super Mario RPG", ["super mario rpg", "mario rpg"]),
    ("0100ECD018EBE000", "Paper Mario: The Thousand-Year Door", ["thousand year door", "paper mario"]),
    ("010036B0034E4000", "Super Mario Party", ["super mario party", "mario party"]),
    ("01006BB00C6F0000", "Mario Party Superstars", ["mario party superstars"]),
    ("01004E301F252000", "The Legend of Zelda: Echoes of Wisdom", ["echoes of wisdom", "zelda echoes"]),
    ("01006BB00C6F0000", "The Legend of Zelda: Link's Awakening", ["links awakening", "zelda koholint"]),
    ("01002DA013484000", "The Legend of Zelda: Skyward Sword HD", ["skyward sword", "zelda skyward"]),
    ("01002B00111A2000", "Hyrule Warriors: Age of Calamity", ["age of calamity", "hyrule warriors"]),
    ("0100A3D008C5C000", "Pokemon Scarlet", ["pokemon scarlet", "koraidon pokemon"]),
    ("01008F6008C5E000", "Pokemon Violet", ["pokemon violet", "miraidon pokemon"]),
    ("01001F5010DFA000", "Pokemon Legends: Arceus", ["pokemon arceus", "hisui pokemon"]),
    ("0100ABF008968000", "Pokemon Sword", ["pokemon sword", "zacian pokemon"]),
    ("01008DB008C2C000", "Pokemon Shield", ["pokemon shield", "zamazenta pokemon"]),
    ("0100C2500FC20000", "Splatoon 3", ["splatoon 3", "splatoon octoling", "splatoon inkling"]),
    ("01003C700009C000", "Splatoon 2", ["splatoon 2", "splatoon agent"]),
    ("0100B7000B36E000", "Pikmin 4", ["pikmin 4", "pikmin olimar", "pikmin dog"]),
    ("010067300059A000", "Donkey Kong Country: Tropical Freeze", ["donkey kong country", "donkey kong tropical freeze"]),
    ("010012101468C000", "Metroid Prime Remastered", ["metroid prime", "metroid prime samus"]),
    ("0100A6301214E000", "Fire Emblem Engage", ["fire emblem engage", "alear fire emblem"]),
    ("0100FF500E34A000", "Xenoblade Chronicles: Definitive Edition", ["xenoblade shulk", "xenoblade definitive"]),
    ("01007300020FA000", "Astral Chain", ["astral chain", "astral chain legion"]),
    ("0100A3B0182E0000", "Bayonetta Origins", ["bayonetta origins", "cereza and the lost demon"]),
    ("0100600004034000", "Yoshi's Crafted World", ["yoshis crafted world", "yoshi nintendo"]),
    ("0100C4901C46E000", "Princess Peach: Showtime!", ["princess peach showtime", "princess peach swordfighter"]),
    ("01009B90006DC000", "Super Mario Maker 2", ["super mario maker", "mario maker 2"]),
    ("010057D006492000", "Octopath Traveler", ["octopath traveler", "octopath"]),
    ("01003C8014524000", "Octopath Traveler II", ["octopath traveler 2", "octopath 2"]),
    ("01005260128AC000", "Triangle Strategy", ["triangle strategy"]),
    ("01006C300E9F0000", "Dragon Quest XI S: Echoes of an Elusive Age", ["dragon quest xi", "dragon quest 11"]),
    ("010042000A986000", "Dragon Quest Builders 2", ["dragon quest builders", "dq builders"]),
    ("0100B9F01B63E000", "Shin Megami Tensei V", ["shin megami tensei v", "smt v nahobino"]),
    ("0100770008DD8000", "Monster Hunter Generations Ultimate", ["monster hunter generations", "mhgu"]),
    ("0100F7E00C70E000", "Hogwarts Legacy", ["hogwarts legacy castle", "hogwarts legacy"]),
    ("01007B0010FCD000", "Red Dead Redemption", ["red dead redemption", "john marston"]),
    ("01004E301F252000", "Sea of Stars", ["sea of stars game", "sea of stars"]),
    ("0100C8801594E000", "Dave the Diver", ["dave the diver game", "dave the diver"]),
    ("010090F012644000", "Cult of the Lamb", ["cult of the lamb", "the lamb cult"]),
    ("01002EA0112A6000", "Blasphemous", ["blasphemous penitent one", "blasphemous"]),
    ("01008DE00C4FA000", "Tunic", ["tunic game fox", "tunic fox"]),
    ("01003DC0144B6000", "Outer Wilds", ["outer wilds solar system", "outer wilds campfire"]),
    ("010032E00E6E2000", "Return of the Obra Dinn", ["return of the obra dinn", "obra dinn"]),
    ("010009B00E71A000", "Slay the Spire", ["slay the spire ironclad", "slay the spire"]),
    ("0100D03008362000", "Minecraft", ["minecraft shader", "minecraft scenery", "minecraft sunset"])
]"""

if old_sfw_anchor in content:
    content = content.replace(old_sfw_anchor, new_sfw_additions)
    print("[+] Successfully expanded POPULAR_SWITCH_SFW_GAMES")
else:
    print("[-] Could not find old_sfw_anchor")

# 2. Update harvest_from_moewalls for mode == "main"
old_mode_main_block = """        if self.mode == "main":
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
                        query_queue.append((tid, c_title, c_title))"""

new_mode_main_block = """        if self.mode == "main":
            # 1. High-yielding MoeWalls direct gaming tags
            gaming_tags = [
                "tag:zelda", "tag:super-mario", "tag:dark-souls", "tag:metroid",
                "tag:hollow-knight", "tag:sonic", "tag:skyrim", "tag:persona",
                "tag:final-fantasy", "tag:gaming", "tag:retro", "tag:elden-ring",
                "tag:cyberpunk", "tag:witcher", "tag:minecraft"
            ]
            for gtag in gaming_tags:
                query_queue.append(("0000000000000000", "Nintendo Switch Gaming", gtag))

            # 2. Curated SFW gaming targets
            for tid, gname, qlist in POPULAR_SWITCH_SFW_GAMES:
                for q in qlist:
                    query_queue.append((tid, gname, q))

            # 3. Games in catalog missing variants
            for g in catalog.get("games", []):
                tid = g.get("titleId", "").upper()
                if tid not in ("0000000000000000", "0000000000000001") and len(g.get("variants", [])) < 3:
                    c_title = clean_switch_title(g.get("title", ""))
                    if 4 <= len(c_title) <= 28 and not self.is_nsfw_text(c_title):
                        query_queue.append((tid, c_title, c_title))

            # 4. Official Switch titles database not yet in catalog (Massive expansion!)
            db_path = PROJECT_ROOT / "studio" / "h3h_studio" / "data" / "switch_titles_db.json"
            if db_path.exists():
                try:
                    db_data = json.loads(db_path.read_text(encoding="utf-8"))
                    existing_tids = {g.get("titleId", "").upper() for g in catalog.get("games", [])}
                    for entry in db_data:
                        tid = entry.get("titleId", "").upper()
                        if len(tid) == 16 and tid.isalnum() and tid not in existing_tids:
                            raw_t = entry.get("title", "")
                            c_t = clean_switch_title(raw_t)
                            if 4 <= len(c_t) <= 28 and not self.is_nsfw_text(c_t):
                                query_queue.append((tid, c_t, c_t))
                except Exception as e:
                    print(f"[!] Warning loading switch_titles_db in harvester: {e}")"""

if old_mode_main_block in content:
    content = content.replace(old_mode_main_block, new_mode_main_block)
    print("[+] Successfully updated harvest_from_moewalls mode == main queue logic")
else:
    print("[-] Could not find old_mode_main_block")

# 3. In the download loop, resolve titles dynamically in mode == "main" if tid == "0000000000000000"
old_assign_block = """                final_tid = tid
                final_name = default_game_name
                if self.mode == "after_dark" and tid == "0000000000000000":
                    c_tid, c_name = self.classify_after_dark_title(clean_name, vid_url)
                    final_tid = c_tid
                    final_name = c_name"""

new_assign_block = """                final_tid = tid
                final_name = default_game_name
                if self.mode == "after_dark" and tid == "0000000000000000":
                    c_tid, c_name = self.classify_after_dark_title(clean_name, vid_url)
                    final_tid = c_tid
                    final_name = c_name
                elif self.mode == "main":
                    # If tid is generic or from a tag search, resolve against official Nintendo Switch DB!
                    if tid in ("0000000000000000", "0000000000000001"):
                        resolved = self.resolver.resolve(clean_name)
                        if resolved:
                            final_tid, final_name = resolved
                        else:
                            # Skip if does not match an official Nintendo Switch game
                            continue"""

if old_assign_block in content:
    content = content.replace(old_assign_block, new_assign_block)
    print("[+] Successfully updated title assignment in main mode loop")
else:
    print("[-] Could not find old_assign_block")

HARVESTER_PATH.write_text(content, encoding="utf-8")
print("[SUCCESS] Patched harvester for Main Branch expansion!")
