from pathlib import Path
import re

HARVESTER_PATH = Path("scripts/auto_video_harvester.py")

content = HARVESTER_PATH.read_text(encoding="utf-8")

# 1. Update AFTER_DARK_GENERAL_QUERIES
old_queries_block = """AFTER_DARK_GENERAL_QUERIES = [
    # Specific Ecchi & Waifu Sub-genres
    "visual novel", "galge", "neko", "catgirl", "bunny girl", "maid waifu",
    "yandere", "tsundere", "gothic girl", "cyberpunk girl", "schoolgirl",
    "monster girl", "ecchi", "bikini", "swimsuit", "beach anime", "lingerie waifu",

    # Iconic Anime / Mobile Waifus
    "nikke", "nikke bikini", "stellar blade eve", "blue archive", "blue archive swimsuit",
    "genshin impact waifu", "raiden shogun", "yae miko", "ganyu", "hu tao", "furina",
    "honkai star rail waifu", "kafka honkai", "firefly honkai", "acheron honkai",
    "chainsaw man makima", "makima bikini", "zero two", "marin kitagawa", "yor forger"
]"""

new_queries_block = """AFTER_DARK_GENERAL_QUERIES = [
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
]"""

# Normalize newlines for matching
content = content.replace("\r\n", "\n")
old_queries_norm = old_queries_block.replace("\r\n", "\n")
new_queries_norm = new_queries_block.replace("\r\n", "\n")

if old_queries_norm in content:
    content = content.replace(old_queries_norm, new_queries_norm)
    print("[+] Successfully replaced AFTER_DARK_GENERAL_QUERIES")
else:
    print("[-] Could not find old_queries_block in content")

# 2. Update search_moewalls_articles to support tag: and fallback regex
old_search_fn = """    def search_moewalls_articles(self, query: str, limit: int = 5, page: int = 1) -> List[Dict[str, str]]:
        if page > 1:
            url = f"https://moewalls.com/page/{page}/?s={urllib.parse.quote(query)}"
        else:
            url = f"https://moewalls.com/?s={urllib.parse.quote(query)}"
        req = urllib.request.Request(url, headers=HEADERS)
        results = []
        try:
            html = urllib.request.urlopen(req, timeout=12).read().decode('utf-8', errors='ignore')
            articles = re.findall(r'<article[^>]*>.*?<a href="([^"]+)"[^>]*rel="bookmark">(.*?)</a>', html, re.DOTALL)
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
        return results"""

new_search_fn = """    def search_moewalls_articles(self, query: str, limit: int = 5, page: int = 1) -> List[Dict[str, str]]:
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
        return results"""

old_search_norm = old_search_fn.replace("\r\n", "\n")
new_search_norm = new_search_fn.replace("\r\n", "\n")

if old_search_norm in content:
    content = content.replace(old_search_norm, new_search_norm)
    print("[+] Successfully replaced search_moewalls_articles")
else:
    print("[-] Could not find old_search_fn in content")

# 3. Add classify_after_dark_title and update is_suitable_for_after_dark
old_suitable_block = """        if any(w in t_low or w in q_low for w in waifu_characters):
            return True

        # If query is a targeted mature Switch game and wallpaper has no male flags, accept
        for _, gname, qlist in MATURE_SWITCH_GAMES:
            if any(q == q_low for q in qlist):
                return True

        return False"""

new_suitable_block = """        if any(w in t_low or w in q_low for w in waifu_characters):
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
        \"\"\"Classifies an After Dark wallpaper into a specific game or dedicated franchise entry.\"\"\"
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

        return ("0000000000000000", "★ Коллекция After Dark: Ecchi & Waifus")"""

old_suitable_norm = old_suitable_block.replace("\r\n", "\n")
new_suitable_norm = new_suitable_block.replace("\r\n", "\n")

if old_suitable_norm in content:
    content = content.replace(old_suitable_norm, new_suitable_norm)
    print("[+] Successfully replaced is_suitable_for_after_dark and added classify_after_dark_title")
else:
    print("[-] Could not find old_suitable_block in content")

# 4. Update harvest_from_moewalls loop to use classification
old_harvest_call = """                print(f"\\n[*] Harvesting MoeWalls video: '{clean_name}' (Target: {default_game_name} [{tid}])")
                ok = self.process_and_upload_asset(
                    asset_url=vid_url,
                    title_id=tid,
                    game_title=default_game_name,"""

new_harvest_call = """                final_tid = tid
                final_name = default_game_name
                if self.mode == "after_dark" and tid == "0000000000000000":
                    c_tid, c_name = self.classify_after_dark_title(clean_name, vid_url)
                    final_tid = c_tid
                    final_name = c_name

                print(f"\\n[*] Harvesting MoeWalls video: '{clean_name}' (Target: {final_name} [{final_tid}])")
                ok = self.process_and_upload_asset(
                    asset_url=vid_url,
                    title_id=final_tid,
                    game_title=final_name,"""

old_call_norm = old_harvest_call.replace("\r\n", "\n")
new_call_norm = new_harvest_call.replace("\r\n", "\n")

if old_call_norm in content:
    content = content.replace(old_call_norm, new_call_norm)
    print("[+] Successfully updated process_and_upload_asset call in harvest_from_moewalls")
else:
    print("[-] Could not find old_harvest_call in content")

# Update pagination wrap from 8 to 15
content = content.replace("page_cursors[q] = current_p + 1 if current_p < 8 else 1", "page_cursors[q] = current_p + 1 if current_p < 15 else 1")

HARVESTER_PATH.write_text(content, encoding="utf-8")
print("[SUCCESS] Patched auto_video_harvester.py successfully!")
