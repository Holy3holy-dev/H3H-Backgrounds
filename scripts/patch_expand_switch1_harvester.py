"""Expands auto_video_harvester.py with 35+ more Switch 1 games and full 12-item page scanning up to 15 pages."""
import json
from pathlib import Path

p = Path("scripts/auto_video_harvester.py")
text = p.read_text(encoding="utf-8")

extra_games = '''    ("01007300020FA000", "Astral Chain", ["tag:astral-chain", "astral chain"]),
    ("010076F0049A4000", "Bayonetta 2", ["tag:bayonetta-2", "bayonetta 2", "jeanne bayonetta"]),
    ("010076F0049A2000", "Bayonetta", ["cereza bayonetta", "bayonetta"]),
    ("01008CF01BAAC000", "The Legend of Zelda: Echoes of Wisdom", ["echoes of wisdom", "princess zelda"]),
    ("01006BB00C6F0000", "The Legend of Zelda: Link's Awakening", ["links awakening", "zelda link"]),
    ("0100DA9013230000", "The Legend of Zelda: Skyward Sword HD", ["skyward sword", "zelda skyward sword"]),
    ("0100ECD018EBE000", "Paper Mario: The Thousand-Year Door", ["paper mario", "thousand year door"]),
    ("0100BC0018138000", "Super Mario RPG", ["super mario rpg"]),
    ("0100B7C00933A000", "Pikmin 4", ["tag:pikmin", "pikmin"]),
    ("0100702008E12000", "Donkey Kong Country: Tropical Freeze", ["tag:donkey-kong", "donkey kong"]),
    ("0100A6301214E000", "Fire Emblem Engage", ["fire emblem engage", "fire emblem edelgard", "fire emblem byleth"]),
    ("0100ABF008968000", "Pokemon Sword", ["tag:pokemon-sword-and-shield", "pokemon sword", "pokemon shield", "pokemon lucario", "pokemon gardevoir", "pokemon greninja"]),
    ("0100B220146BA000", "Assassin's Creed: The Ezio Collection", ["tag:assassins-creed", "ezio auditore", "assassins creed"]),
    ("01007F600B134000", "Metal Gear Solid: Master Collection Vol. 1", ["tag:metal-gear", "tag:metal-gear-solid", "tag:metal-gear-rising-revengeance", "solid snake", "raiden metal gear", "metal gear"]),
    ("01006C1014796000", "KINGDOM HEARTS Integrum Masterpiece", ["tag:kingdom-hearts", "kingdom hearts", "sora kingdom hearts", "roxas kingdom hearts"]),
    ("0100D79014A20000", "Grand Theft Auto: The Trilogy – The Definitive Edition", ["tag:grand-theft-auto", "gta san andreas", "gta vice city", "grand theft auto"]),
    ("0100C1F00B2B6000", "Crash Bandicoot N. Sane Trilogy", ["tag:crash-bandicoot", "crash bandicoot"]),
    ("010077B00E046000", "Spyro Reignited Trilogy", ["tag:spyro", "spyro"]),
    ("01005E1004076000", "Rayman Legends Definitive Edition", ["tag:rayman", "rayman"]),
    ("01008DF01290C000", "Ghostrunner", ["tag:ghostrunner", "ghostrunner"]),
    ("01004990172B0000", "Sifu", ["tag:sifu", "sifu"]),
    ("01004E9013A66000", "NINJA GAIDEN: Master Collection", ["tag:ninja-gaiden", "ninja gaiden", "ryu hayabusa"]),
    ("010099F003C4E000", "Darkest Dungeon", ["tag:darkest-dungeon", "darkest dungeon"]),
    ("01005F600B3C2000", "Slay the Spire", ["tag:slay-the-spire", "slay the spire"]),
    ("0100E4A00CBCE000", "Risk of Rain 2", ["tag:risk-of-rain", "risk of rain 2", "risk of rain"]),
    ("01009B9013E56000", "Factorio", ["tag:factorio", "factorio"]),
    ("010075100BFEC000", "Don't Starve Together", ["tag:dont-starve", "dont starve"]),
    ("010022A011A62000", "Crysis Remastered Trilogy", ["tag:crysis", "crysis"]),
    ("010066E016522000", "Alan Wake Remastered", ["tag:alan-wake", "alan wake"]),
    ("010063F014170000", "Danganronpa Decadence", ["tag:danganronpa", "danganronpa", "junko enoshima", "chiaki nanami", "kyoko kirigiri"]),
    ("0100B3900C3E2000", "Phoenix Wright: Ace Attorney Trilogy", ["tag:ace-attorney", "ace attorney", "phoenix wright"]),
    ("010023301E41C000", "Fate/stay night REMASTERED", ["tag:fate-series", "tag:fate-stay-night", "tag:saber", "saber fate", "rin tohsaka", "fate stay night"]),
    ("01002F401C950000", "Tsukihime -A piece of blue glass moon-", ["tag:tsukihime", "tsukihime", "arcueid"]),
    ("01005A7013EA0000", "Doki Doki Literature Club Plus!", ["tag:doki-doki-literature-club", "doki doki literature club", "monika ddlc"]),
    ("01007560153F0000", "Five Nights at Freddy's: Security Breach", ["tag:five-nights-at-freddys", "five nights at freddys", "fnaf", "springtrap"]),
    ("010035301980C000", "Poppy Playtime: Chapter 1", ["tag:poppy-playtime", "poppy playtime", "huggy wuggy"]),
    ("0100210019428000", "Prince of Persia: The Lost Crown", ["tag:prince-of-persia", "prince of persia"]),
    ("010075D00E8BA000", "Alien: Isolation", ["tag:alien", "alien isolation", "xenomorph"]),
    ("0100AF800D570000", "gris", ["tag:gris", "gris"])'''

target_end = '    ("0100AF800D570000", "gris", ["tag:gris", "gris"])'
if target_end in text and "01007F600B134000" not in text:
    text = text.replace(target_end, extra_games)

# Upgrade page article scan limit from 4 to 15 (full page of 12 items)
text = text.replace("self.search_moewalls_articles(q, limit=4, page=current_p)", "self.search_moewalls_articles(q, limit=15, page=current_p)")

# Upgrade max pagination depth from 4 to 15 pages
text = text.replace("current_p + 1 if current_p < 4 else 1", "current_p + 1 if current_p < 15 else 1")

# Upgrade per-game variant cap from 40 to 65
text = text.replace("< 40:", "< 65:").replace(">= 40:", ">= 65:")

p.write_text(text, encoding="utf-8")
print("[+] Patched auto_video_harvester.py with 35+ new Switch 1 titles and full 12-card page scanning!")

# Reset page_cursors to 1 so previously skipped items 5..12 on page 1 of every game are harvested!
for log_name in ("video_harvest_log_main.json", "video_harvest_log_after_dark.json"):
    lp = Path("catalog/data") / log_name
    if lp.exists():
        ld = json.loads(lp.read_text(encoding="utf-8"))
        ld["page_cursors"] = {}
        ld["priority_cursor"] = 0
        ld["query_cursor"] = 0
        lp.write_text(json.dumps(ld, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[+] Reset page_cursors in {log_name} to harvest full pages 1..15")
