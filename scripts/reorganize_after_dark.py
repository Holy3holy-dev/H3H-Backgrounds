import json
import re
from pathlib import Path

CATALOG_PATH = Path("catalog/data/catalog_after_dark.json")

# Dedicated Waifu & Anime Franchise Definitions for After Dark
FRANCHISES = [
    {
        "titleId": "0100EC0000000001",
        "title": "Genshin Impact (Waifus)",
        "publisher": "HoYoverse",
        "keywords": ["genshin", "raiden", "yae miko", "ganyu", "hu tao", "furina", "arlecchino", "mona", "shenhe", "yelan", "clorinde", "navia", "keqing", "nilou", "ayaka", "yoimiya", "kokomi", "eula", "lisa genshin", "jean genshin"]
    },
    {
        "titleId": "0100EC0000000002",
        "title": "Blue Archive (Swimsuit & Bunny)",
        "publisher": "NEXON Games / Yostar",
        "keywords": ["blue archive", "makoto", "akane", "chiaki", "satsuki", "asuna blue", "karin blue", "toki blue", "shiroko", "hina blue", "yuuka"]
    },
    {
        "titleId": "0100EC0000000003",
        "title": "Chainsaw Man (Makima & Power)",
        "publisher": "MAPPA / Shueisha",
        "keywords": ["chainsaw man", "makima", "power blood", "reze"]
    },
    {
        "titleId": "0100EC0000000004",
        "title": "GODDESS OF VICTORY: NIKKE",
        "publisher": "SHIFT UP",
        "keywords": ["nikke", "cinderella", "anis nikke", "dorothy nikke", "elegg", "rapi nikke", "sugar nikke", "viper nikke", "rupee nikke", "helm nikke", "scarlet nikke"]
    },
    {
        "titleId": "0100EC0000000005",
        "title": "Honkai: Star Rail (Waifus)",
        "publisher": "HoYoverse",
        "keywords": ["honkai", "star rail", "kafka", "firefly", "acheron", "black swan", "himeko", "silver wolf", "tingyun", "sparkle", "march 7th", "feixiao", "topaz", "jade honkai", "elysia", "mobius"]
    },
    {
        "titleId": "0100EC0000000006",
        "title": "Darling in the Franxx (Zero Two)",
        "publisher": "Trigger / CloverWorks",
        "keywords": ["zero two", "darling in the franxx", "ichigo darling"]
    },
    {
        "titleId": "0100EC0000000007",
        "title": "Stellar Blade (Eve)",
        "publisher": "SHIFT UP",
        "keywords": ["stellar blade", "eve nano", "eve stellar"]
    },
    {
        "titleId": "0100EC0000000008",
        "title": "Rascal Does Not Dream (Mai Sakurajima)",
        "publisher": "CloverWorks",
        "keywords": ["bunny girl senpai", "mai sakurajima"]
    },
    {
        "titleId": "0100EC0000000009",
        "title": "SPY x FAMILY (Yor Forger)",
        "publisher": "WIT Studio / CloverWorks",
        "keywords": ["yor forger", "yor spy", "spy x family"]
    },
    {
        "titleId": "0100EC000000000A",
        "title": "Zenless Zone Zero",
        "publisher": "HoYoverse",
        "keywords": ["zenless", "zzz", "ellen joe", "nicole demara", "zhu yuan"]
    },
    {
        "titleId": "0100EC000000000B",
        "title": "My Dress-Up Darling (Marin Kitagawa)",
        "publisher": "CloverWorks",
        "keywords": ["marin kitagawa", "my dress-up darling", "marin cosplay"]
    },
    {
        "titleId": "0100EC000000000C",
        "title": "Overlord (Albedo & Shalltear)",
        "publisher": "Madhouse",
        "keywords": ["overlord", "albedo", "shalltear"]
    },
    {
        "titleId": "0100EC000000000D",
        "title": "Re:Zero (Rem & Emilia)",
        "publisher": "White Fox",
        "keywords": ["re:zero", "re zero", "rem fallen", "rem re:zero", "emilia re:zero", "echidna"]
    },
    {
        "titleId": "0100EC000000000E",
        "title": "KonoSuba (Megumin & Aqua)",
        "publisher": "Drive / Studio Deen",
        "keywords": ["konosuba", "megumin", "aqua konosuba", "darkness konosuba"]
    },
    {
        "titleId": "0100EC000000000F",
        "title": "Hololive VTubers (Marine, Gura, Calli)",
        "publisher": "Cover Corp",
        "keywords": ["hololive", "houshou marine", "gawr gura", "calliope", "pekora", "kronii"]
    },
    {
        "titleId": "0100EC0000000010",
        "title": "High School DxD (Rias & Akeno)",
        "publisher": "TNK / Passione",
        "keywords": ["high school dxd", "dxd", "rias gremory", "akeno"]
    },
    {
        "titleId": "0100EC0000000011",
        "title": "To Love-Ru Darkness",
        "publisher": "Xebec",
        "keywords": ["to love ru", "to love-ru", "lala satalin", "golden darkness", "momo belia"]
    }
]

# Additional Nintendo Switch Mature & Ecchi Games to add to catalog
NEW_SWITCH_GAMES = [
    ("010099400D28E000", "Senran Kagura Peach Ball", "Marvelous / XSEED"),
    ("0100914008272000", "Senran Kagura Reflexions", "Marvelous / XSEED"),
    ("010034200B5B0000", "Dead or Alive Xtreme 3 Scarlet", "Koei Tecmo"),
    ("01008D9017646000", "Seven Pirates H", "Eastasiasoft / Compile Heart"),
    ("0100EBF010190000", "Moero Crystal H", "Eastasiasoft / Compile Heart"),
    ("01003E700CBA4000", "Moero Chronicle Hyper", "Compile Heart / Idea Factory"),
    ("0100C8801594E000", "Gal*Gun Double Peace", "PQube / Inti Creates"),
    ("010090F012644000", "Gal*Gun Returns", "PQube / Inti Creates"),
    ("010093800B9CE000", "Omega Labyrinth Life", "D3 Publisher"),
    ("01002EA0112A6000", "Waifu Uncovered", "Eastasiasoft"),
    ("01002270146AE000", "Waifu Discovered 2: Medieval Fantasy", "Eastasiasoft"),
    ("01008DE00C4FA000", "Super Neptunia RPG", "Idea Factory"),
    ("0100B9F01B63E000", "Neptunia Sisters VS Sisters", "Idea Factory"),
    ("0100DCE00FE24000", "Megadimension Neptunia VII", "Idea Factory"),
    ("010009B00E71A000", "Atelier Ryza: Ever Darkness & the Secret Hideout", "Koei Tecmo"),
    ("010052901243A000", "Atelier Ryza 2: Lost Legends & the Secret Fairy", "Koei Tecmo"),
    ("0100F48017B80000", "Atelier Ryza 3: Alchemist of the End", "Koei Tecmo"),
    ("010051B014524000", "Atelier Sophie 2: The Alchemist of the Mysterious Dream", "Koei Tecmo"),
    ("01004FE00CB04000", "Mary Skelter 2", "Compile Heart / Idea Factory"),
    ("0100D5D010EB4000", "Mary Skelter Finale", "Compile Heart / Idea Factory"),
    ("01000B0011C9C000", "Death end re;Quest", "Compile Heart / Idea Factory"),
    ("0100E2C0157E8000", "Death end re;Quest 2", "Compile Heart / Idea Factory"),
    ("01002F401C950000", "Tsukihime -A piece of blue glass moon-", "Aniplex / TYPE-MOON"),
    ("0100344018A1A000", "Witch on the Holy Night", "Aniplex / TYPE-MOON"),
    ("0100847012D78000", "Saya no Uta", "JAST USA / Nitroplus"),
    ("0100B9600E262000", "The Fruit of Grisaia: Remastered", "PROTOTYPE / Frontwing"),
    ("01001A800FCFE000", "Grisaia: Phantom Trigger 01 to 05", "PROTOTYPE / Frontwing"),
    ("010058C00A63C000", "Higurashi When They Cry Hou", "Entergram / 07th Expansion"),
    ("010025D00E71C000", "Umineko When They Cry Saku", "Entergram / 07th Expansion"),
    ("010065200DEB2000", "Gun Gun Pixies", "PQube / Compile Heart"),
    ("0100486009E48000", "Bullet Girls Phantasia", "D3 Publisher"),
    ("0100BD601309E000", "Crawlco Block Knockers", "Eastasiasoft"),
    ("0100C1A014E4C000", "Pretty Girls Mahjong Solitaire", "Eastasiasoft"),
    ("010020B01A3DE000", "Akiba's Trip: Undead & Undressed", "XSEED Games / Acquire"),
    ("01001F000CB7E000", "Date A Live: Rio Reincarnation", "Compile Heart / Idea Factory"),
    ("010027701815A000", "Date A Live: Ren Dystopia", "Compile Heart / Idea Factory"),
    ("0100C9E00CA3E000", "Sword Art Online: Fatal Bullet Complete Edition", "Bandai Namco"),
    ("0100D1A007038000", "Sword Art Online: Hollow Realization Deluxe Edition", "Bandai Namco")
]

def reorganize():
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    games_by_tid = {g["titleId"].upper(): g for g in catalog.get("games", [])}

    # Find the big generic 0000000000000000 entry
    g0 = games_by_tid.get("0000000000000000")
    if not g0:
        print("[!] 0000000000000000 not found!")
        return

    variants_to_move = g0.get("variants", [])
    remaining_variants = []

    print(f"[*] Starting reorganization of {len(variants_to_move)} variants currently in 0000000000000000...")

    # Ensure all dedicated franchises exist as game entries
    for franchise in FRANCHISES:
        tid = franchise["titleId"].upper()
        if tid not in games_by_tid:
            new_g = {
                "titleId": tid,
                "title": franchise["title"],
                "publisher": franchise["publisher"],
                "variants": []
            }
            catalog["games"].append(new_g)
            games_by_tid[tid] = new_g

    # Ensure all new Switch games exist as game entries
    for tid, title, pub in NEW_SWITCH_GAMES:
        tid_u = tid.upper()
        if tid_u not in games_by_tid:
            new_g = {
                "titleId": tid_u,
                "title": title,
                "publisher": pub,
                "variants": []
            }
            catalog["games"].append(new_g)
            games_by_tid[tid_u] = new_g

    # Reclassify variants from 0000000000000000
    moved_count = 0
    for v in variants_to_move:
        v_name = v.get("name", "")
        v_url = v.get("video_url", "")
        combined = (v_name + " " + v_url).lower()

        target_tid = None

        # Check existing classic games first
        if any(k in combined for k in ["nier", "2b", "a2", "9s"]):
            target_tid = "01005C000B2AE000"
        elif any(k in combined for k in ["azur lane", "prinz eugen", "taihou", "atago", "shinano", "belfast"]):
            target_tid = "0100A1900F3BA000"
        elif any(k in combined for k in ["cyberpunk", "lucy", "rebecca"]):
            target_tid = "0100435942450000"
        elif any(k in combined for k in ["fate", "saber", "scathach", "rin tohsaka", "tamamo", "nero"]):
            target_tid = "010023301E41C000"
        elif any(k in combined for k in ["witcher", "yennefer", "triss", "ciri"]):
            target_tid = "0100E8B00BDC6000"
        elif any(k in combined for k in ["persona", "ann takamaki", "makoto niijima", "kasumi yoshizawa"]):
            target_tid = "010091200CDA4000"
        elif any(k in combined for k in ["senran kagura", "senran"]):
            target_tid = "010099400D28E000"
        elif any(k in combined for k in ["dead or alive", "marie rose", "honoka"]):
            target_tid = "010034200B5B0000"
        elif any(k in combined for k in ["atelier", "ryza"]):
            target_tid = "010009B00E71A000"
        else:
            # Check dedicated franchises
            for franchise in FRANCHISES:
                if any(kw in combined for kw in franchise["keywords"]):
                    target_tid = franchise["titleId"].upper()
                    break

        if target_tid and target_tid in games_by_tid:
            # Avoid duplicate variants
            existing_urls = {var.get("video_url") for var in games_by_tid[target_tid].get("variants", [])}
            if v_url not in existing_urls:
                games_by_tid[target_tid]["variants"].append(v)
            moved_count += 1
        else:
            remaining_variants.append(v)

    # Update generic entry
    g0["title"] = "★ Коллекция After Dark: Ecchi & Waifus"
    g0["variants"] = remaining_variants

    print(f"[+] Moved {moved_count} variants to specific games/franchises!")
    print(f"[+] Remaining in general collection: {len(remaining_variants)}")
    print(f"[+] Total games now in After Dark: {len(catalog['games'])}")

    with open(CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)
    print(f"[SUCCESS] Saved updated catalog to {CATALOG_PATH}")

if __name__ == "__main__":
    reorganize()
