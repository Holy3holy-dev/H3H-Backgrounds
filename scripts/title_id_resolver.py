import json
import re
import difflib
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any

class TitleIdResolver:
    """
    Intelligent fuzzy title and character matcher that resolves user input,
    typos, Russian slang, and character names to official Nintendo Switch Title IDs.
    """

    RUSSIAN_ALIASES = {
        'ведьмак': 'witcher',
        'слезы королевства': 'tears of the kingdom',
        'дыхание дикой природы': 'breath of the wild',
        'ботва': 'breath of the wild',
        'тотк': 'tears of the kingdom',
        'ботв': 'breath of the wild',
        'смеш': 'smash bros',
        'сэш': 'smash bros',
        'аид': 'hades',
        'хейдис': 'hades',
        'ниер': 'nier',
        'нир': 'nier',
        'персона': 'persona',
        'дарк соулс': 'dark souls',
        'темные души': 'dark souls',
        'покемон': 'pokemon',
        'покемоны': 'pokemon',
        'метроид': 'metroid',
        'байонетта': 'bayonetta',
        'байонета': 'bayonetta',
        'ксеноблейд': 'xenoblade',
        'зеноблейд': 'xenoblade',
        'марио': 'mario',
        'соник': 'sonic',
        'донки конг': 'donkey kong',
        'мортал комбат': 'mortal kombat',
        'доа': 'dead or alive',
        'дед ор элайв': 'dead or alive',
        'киберпанк': 'cyberpunk',
        'финалка': 'final fantasy',
        'файнал фэнтези': 'final fantasy',
        'звёздные войны': 'star wars',
        'звездные войны': 'star wars',
        'одиссея': 'odyssey',
        'одисея': 'odyssey',
        'карт': 'kart',
        'марио кролики': 'mario rabbids',
        'кролики': 'mario rabbids',
        'рабидс': 'mario rabbids',
        'лабиринт': 'last labyrinth',
        'ласт лабиринт': 'last labyrinth',
        'обра динн': 'obra dinn',
        'обра дин': 'obra dinn',
        'обро динн': 'obra dinn',
        'внешние дебри': 'outer wilds',
        'аутер вайлдс': 'outer wilds',
        'мгр': 'metal gear rising',
        'райзинг': 'metal gear rising',
        'метал гир райзинг': 'metal gear rising',
        'сенатор армстронг': 'metal gear rising',
        'джетстрим сэм': 'metal gear rising',
        'рейден': 'metal gear rising',
        'гта': 'grand theft auto',
        'гта 5': 'grand theft auto v',
        'гта 4': 'grand theft auto iv',
        'гта сан андреас': 'san andreas',
        'сан андреас': 'san andreas',
        'вайс сити': 'vice city',
        'дби': 'dbi',
        'тинфоил': 'tinfoil',
        'ретроарх': 'retroarch',
        'халф лайф': 'half-life',
        'халфа': 'half-life',
        'портал': 'portal',
        'дум': 'doom',
        'диабло': 'diablo',
        'морровинд': 'morrowind',
        'фоллаут': 'fallout',
        'герои': 'heroes of might and magic',
    }

    CYRILLIC_TO_LATIN = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
    }

    CHARACTER_MAPPINGS = {
        "2b": "Nier Automata",
        "a2": "Nier Automata",
        "9s": "Nier Automata",
        "yorha": "Nier Automata",
        "pyra": "Xenoblade Chronicles 2",
        "mythra": "Xenoblade Chronicles 2",
        "homura": "Xenoblade Chronicles 2",
        "hikari": "Xenoblade Chronicles 2",
        "purah": "Tears of the Kingdom",
        "zelda": "Breath of the Wild",
        "midna": "Twilight Princess",
        "mipha": "Breath of the Wild",
        "urbosa": "Breath of the Wild",
        "bowsette": "Super Mario Odyssey",
        "peach": "Super Mario Odyssey",
        "rosalina": "Super Mario Galaxy",
        "pauline": "Super Mario Odyssey",
        "boosette": "Luigi's Mansion 3",
        "tifa": "Final Fantasy",
        "aerith": "Final Fantasy",
        "bayonetta": "Bayonetta",
        "jeanne": "Bayonetta",
        "makoto": "Persona 5 Royal",
        "ann": "Persona 5 Royal",
        "kasumi": "Persona 5 Royal",
        "futaba": "Persona 5 Royal",
        "mitsuru": "Persona 3 Portable",
        "aigis": "Persona 3 Portable",
        "samus": "Metroid Dread",
        "zero suit samus": "Super Smash Bros Ultimate",
        "chun li": "Street Fighter",
        "cammy": "Street Fighter",
        "juri": "Street Fighter",
        "morrigan": "Capcom Fighting Collection",
        "mai shiranui": "Fatal Fury",
        "honoka": "Dead or Alive Xtreme",
        "marie rose": "Dead or Alive Xtreme",
        "kasumi doa": "Dead or Alive",
        "asuka": "Senran Kagura",
        "homura sk": "Senran Kagura",
        "lucy": "Cyberpunk",
        "rebecca": "Cyberpunk",
        "yennefer": "Witcher 3",
        "triss": "Witcher 3",
        "ciri": "Witcher 3",
        "aphrodite": "Hades",
        "nyx": "Hades",
        "megaera": "Hades",
        "edelgard": "Fire Emblem Three Houses",
        "byleth": "Fire Emblem Three Houses",
        "dimitri": "Fire Emblem Three Houses",
        "rhea": "Fire Emblem Three Houses",
        "giselle": "The House in Fata Morgana",
        "fata morgana": "The House in Fata Morgana",
        "morgana": "The House in Fata Morgana",
        "honoka": "Dead or Alive Xtreme",
        "marie rose": "Dead or Alive Xtreme",
    }

    BUILTIN_TITLE_IDS = {
        # GTA Series & Ports
        "0100B00B51230000": "Grand Theft Auto V (GTA 5)",
        "0100B00B51240000": "Grand Theft Auto IV (GTA 4)",
        "0100658013E42000": "Grand Theft Auto: San Andreas - The Definitive Edition",
        "01006E8013E44000": "Grand Theft Auto: Vice City - The Definitive Edition",
        "01007E3013E40000": "Grand Theft Auto III - The Definitive Edition",
        "010065A014024000": "Grand Theft Auto: The Trilogy - The Definitive Edition",
        "0100524533000000": "Grand Theft Auto: Vice City (reVC Classic Port)",
        "0100524533000001": "Grand Theft Auto III (re3 Classic Port)",
        "0100475441435700": "Grand Theft Auto: Chinatown Wars",
        "01004754414C4353": "Grand Theft Auto: Liberty City Stories",

        # Essential Homebrew Apps & Tools
        "010000000000100D": "DBI (Title, Ticket and File Manager)",
        "0100000000001000": "Tinfoil (Game & Content Manager)",
        "010000000000100B": "RetroArch (Multi-system Retro Emulator)",
        "0100000000001003": "PPSSPP (PlayStation Portable Emulator)",
        "0100000000001002": "Moonlight NX (PC Game Streaming Client)",
        "0100000000001004": "Chiaki (PlayStation 4/5 Remote Play)",
        "0100000000001005": "NX-Shell (Multipurpose File Manager)",
        "0100000000001006": "NX-Activity-Log (Playtime Tracker)",
        "0100000000001007": "Daybreak (Atmosphere Firmware Updater)",
        "0100000000001008": "Awoo Installer",
        "4212056000000000": "H3H Backgrounds (Official 4IFIR Video Themes)",
        "0100483348414400": "H3H After Dark (Official 18+ Themes)",

        # Famous PC Classic Ports on Switch
        "0100888000001001": "Half-Life (Xash3D-FWGS Port)",
        "0100888000001002": "Portal (Source Engine NX)",
        "0100888000001003": "Doom 3 (dhewm3 Port)",
        "0100888000001004": "Return to Castle Wolfenstein (iortcw)",
        "0100888000001005": "The Elder Scrolls III: Morrowind (OpenMW)",
        "0100888000001006": "Fallout 1 (fallout1-ce)",
        "0100888000001007": "Fallout 2 (fallout2-ce)",
        "0100888000001008": "Diablo (DevilutionX)",
        "0100888000001009": "Heroes of Might and Magic III (VCMI)",
        "0100888000001010": "Max Payne (Android wrapper port)",
        "0100534D36340000": "Super Mario 64 (SM64-NX Native Port)",
        "01005A454C444101": "The Legend of Zelda: Ocarina of Time (Ship of Harkinian)",
        "01005A454C444102": "The Legend of Zelda: Majora's Mask (2Ship2Harkinian)",

        "05988A343C507000": "Metal Gear Rising: Revengeance",
        "01004D4752000000": "Metal Gear Rising: Revengeance",
        "010067300059A000": "Mario + Rabbids Kingdom Battle",
        "01009C701A35E000": "Last Labyrinth -Lucidity Lost-",
        "01003DC0144B6000": "Outer Wilds Archaeologist Edition",
        "010032E00E6E2000": "Return of the Obra Dinn",
        "010028600EBDA000": "Super Mario 3D World + Bowser's Fury",
        "0100C1F0051B6000": "Donkey Kong Country: Tropical Freeze",
        "010016101100A000": "The House in Fata Morgana: Dreams of the Revenants Edition",
        "01007E100C4D0000": "Dead or Alive Xtreme 3 Scarlet",
        "0100AC200ED5E000": "Azur Lane Crosswave",
        "010079C009494000": "Senran Kagura Reflexions",
        "0100E95004038000": "Xenoblade Chronicles 2",
        "010074600E9F2000": "Xenoblade Chronicles 3",
        "01005C000B2AE000": "NieR:Automata The End of YoRHa Edition",
        "0100A5B00BDC6000": "Final Fantasy VII",
        "0100F2C0115B6000": "The Legend of Zelda: Tears of the Kingdom",
        "0100000000010000": "Super Mario Odyssey",
        "0100E8B00BDC6000": "The Witcher 3: Wild Hunt - Complete Edition",
        "010091200CDA4000": "Persona 5 Royal",
    }

    def __init__(self, catalog_path: str = "catalog/data/catalog.json"):
        self.catalog_path = Path(catalog_path)
        self.games: List[Dict] = []
        self.normalized_games: List[Tuple[str, str, List[str]]] = []
        self.load_catalog()

    def load_catalog(self):
        paths = [
            self.catalog_path,
            self.catalog_path.parent / "catalog_after_dark.json"
        ]
        self.games = []
        seen_tids = set()
        for p in paths:
            if p.exists():
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    for g in data.get("games", []):
                        tid = g.get("titleId", "")
                        if tid and tid not in seen_tids:
                            self.games.append(g)
                            seen_tids.add(tid)
                except Exception:
                    pass

        # Also add built-in common titles if not in catalog
        for tid, name in self.BUILTIN_TITLE_IDS.items():
            if tid not in seen_tids:
                self.games.append({"titleId": tid, "title": name})
                seen_tids.add(tid)

        # Also load all official Switch titles and homebrews from database
        db_path = self.catalog_path.parent.parent.parent / "studio" / "h3h_studio" / "data" / "switch_titles_db.json"
        if not db_path.exists():
            db_path = Path("studio/h3h_studio/data/switch_titles_db.json")
        if db_path.exists():
            try:
                db_data = json.loads(db_path.read_text(encoding="utf-8"))
                games_by_tid = {g.get("titleId", "").upper(): g for g in self.games}
                for entry in db_data:
                    tid = entry.get("titleId", "").upper()
                    if len(tid) == 16 and tid.isalnum():
                        if tid in games_by_tid:
                            g = games_by_tid[tid]
                            if not g.get("publisher") or g.get("publisher") == "Unknown":
                                g["publisher"] = entry.get("publisher", "Official")
                            if not g.get("genre"):
                                g["genre"] = entry.get("genre", "Nintendo Switch")
                            if "isHomebrew" in entry:
                                g["isHomebrew"] = entry.get("isHomebrew", False)
                        else:
                            self.games.append(entry)
                            games_by_tid[tid] = entry
                            seen_tids.add(tid)
            except Exception:
                pass

        self.normalized_games.clear()
        for g in self.games:
            tid = g.get("titleId", "")
            title = g.get("title", "")
            clean = self.clean_title(title)
            tokens = [t for t in re.split(r"[^a-z0-9]+", clean.lower()) if t]
            self.normalized_games.append((tid, clean, tokens))

    @staticmethod
    def clean_title(title: str) -> str:
        t = re.sub(r"\[.*?\]", " ", title)
        t = re.sub(r"\+\s*(?:dlc|update|v\d+|season|expansion).*", "", t, flags=re.IGNORECASE)
        t = re.sub(r"[^\w\s\:\-\'\.\+]", " ", t)
        return " ".join(t.split())

    COMMON_EXPANSIONS = {
        r"\bgta\b": "grand theft auto gta",
        r"\bgta\s*5\b": "grand theft auto v 5 gta5",
        r"\bgta\s*v\b": "grand theft auto v 5 gta5",
        r"\bgta\s*4\b": "grand theft auto iv 4 gta4",
        r"\bgta\s*iv\b": "grand theft auto iv 4 gta4",
        r"\bgta\s*sa\b": "grand theft auto san andreas",
        r"\bgta\s*vc\b": "grand theft auto vice city",
        r"\bgta\s*3\b": "grand theft auto iii 3 gta3",
        r"\bgta\s*iii\b": "grand theft auto iii 3 gta3",
        r"\brdr\b": "red dead redemption",
        r"\brdr2\b": "red dead redemption 2",
        r"\btotk\b": "tears of the kingdom",
        r"\bbotw\b": "breath of the wild",
        r"\bsm64\b": "super mario 64",
        r"\bmgr\b": "metal gear rising revengeance",
    }

    @classmethod
    def normalize_input(cls, query: str) -> str:
        """Converts Russian aliases, abbreviations, and transliterates Cyrillic to Latin."""
        q = query.lower().strip()
        # Replace known Russian slang/aliases
        for ru, en in cls.RUSSIAN_ALIASES.items():
            pattern = r"\b" + re.escape(ru) + r"\b"
            q = re.sub(pattern, en, q)
        # Transliterate any remaining Cyrillic letters
        q = "".join(cls.CYRILLIC_TO_LATIN.get(c, c) for c in q)
        # Expand gaming acronyms
        for pat, rep in cls.COMMON_EXPANSIONS.items():
            q = re.sub(pat, rep, q)
        return q

    def resolve_by_title_id(self, title_id: str) -> Optional[str]:
        """Looks up a clean game title directly by its 16-hex Title ID."""
        if not title_id:
            return None
        tid_upper = title_id.strip().upper()
        if tid_upper in self.BUILTIN_TITLE_IDS:
            return self.BUILTIN_TITLE_IDS[tid_upper]
        for g in self.games:
            if g.get("titleId", "").upper() == tid_upper:
                return g.get("title", "")
        for tid, clean_name, _ in self.normalized_games:
            if tid.upper() == tid_upper:
                return clean_name
        return None

    @staticmethod
    def extract_title_id(text: str) -> Optional[str]:
        """Extracts a 16-hex Nintendo Switch Title ID from a string, filename, or caption."""
        if not text:
            return None
        # Match exactly 16 hexadecimal characters with non-hex boundaries
        match = re.search(r'(?i)(?<![0-9a-f])([0-9a-f]{16})(?![0-9a-f])', text)
        if match:
            return match.group(1).upper()
        return None

    def resolve(self, query: str) -> Optional[Tuple[str, str]]:
        """Resolves to the single best matching (titleId, gameName)."""
        candidates = self.resolve_multiple(query, limit=1)
        if candidates:
            return (candidates[0][0], candidates[0][1])
        return None

    @staticmethod
    def clean_display_title(title: str) -> str:
        import re
        t = re.sub(r"\[.*?\]", "", title)
        t = re.sub(r"\+\s*(?:dlc|update|v\d+|season|expansion).*", "", t, flags=re.IGNORECASE)
        t = re.sub(r"\s*\([\s,]*\)\s*", " ", t)
        t = re.sub(r"\s+", " ", t).strip()
        return t or title

    def search_games_rich(self, query: str, limit: int = 6) -> List[Dict[str, Any]]:
        """
        Searches all titles and returns rich objects:
        [{\"titleId\": ..., \"title\": ..., \"publisher\": ..., \"genre\": ..., \"isHomebrew\": ...}]
        """
        if not query or not query.strip():
            return []

        q_clean = query.strip()
        tid_match = self.extract_title_id(q_clean)

        # 1. Direct Title ID match
        if tid_match:
            tid_upper = tid_match.upper()
            found_entry = next((g for g in self.games if g.get("titleId", "").upper() == tid_upper), None)
            if found_entry:
                raw_t = found_entry.get("title", f"Game ({tid_upper})")
                return [{
                    "titleId": tid_upper,
                    "title": self.clean_display_title(raw_t),
                    "rawTitle": raw_t,
                    "publisher": found_entry.get("publisher", "Community"),
                    "genre": found_entry.get("genre", "Game"),
                    "isHomebrew": found_entry.get("isHomebrew", False),
                    "score": 100.0
                }]
            title = self.resolve_by_title_id(tid_upper) or f"Game ({tid_upper})"
            return [{
                "titleId": tid_upper,
                "title": self.clean_display_title(title),
                "rawTitle": title,
                "publisher": "Official / Homebrew",
                "genre": "Game",
                "isHomebrew": False,
                "score": 100.0
            }]

        # 2. Fuzzy Multiple Match
        matches = self.resolve_multiple(q_clean, limit=limit)
        results = []
        for tid, name, score in matches:
            found_entry = next((g for g in self.games if g.get("titleId", "").upper() == tid.upper()), {})
            raw_title = found_entry.get("title", name)
            display_title = self.clean_display_title(raw_title)
            results.append({
                "titleId": tid.upper(),
                "title": display_title,
                "rawTitle": raw_title,
                "publisher": found_entry.get("publisher", "Community"),
                "genre": found_entry.get("genre", "Nintendo Switch"),
                "isHomebrew": found_entry.get("isHomebrew", False),
                "score": score
            })
        return results

    def resolve_multiple(self, query: str, limit: int = 4) -> List[Tuple[str, str, float]]:
        """
        Resolves query with typo-tolerance and transliteration.
        Returns a list of tuples: [(titleId, cleanGameName, score), ...]
        sorted by highest score first.
        """
        if not query or not query.strip():
            return []

        # 1. Normalize query
        norm_query = self.normalize_input(query)
        q_tokens = [t for t in re.split(r"[^a-z0-9]+", norm_query) if t]

        # 2. Check character mapping
        char_bonus_game = None
        for char_name, mapped_game in self.CHARACTER_MAPPINGS.items():
            if re.search(r"\b" + re.escape(char_name) + r"\b", norm_query):
                char_bonus_game = mapped_game.lower()
                break

        scored: List[Tuple[str, str, float]] = []

        for tid, clean_name, g_tokens in self.normalized_games:
            clean_lower = clean_name.lower()
            score = 0.0

            # Character match bonus
            if char_bonus_game and char_bonus_game in clean_lower:
                score += 50.0

            # Substring match
            if norm_query in clean_lower:
                score += 40.0
            
            # Token matching with fuzzy typo tolerance
            for qt in q_tokens:
                if qt in g_tokens:
                    score += 15.0
                else:
                    # Check fuzzy match against each token in game title
                    best_token_ratio = max([difflib.SequenceMatcher(None, qt, gt).ratio() for gt in g_tokens] + [0.0])
                    if best_token_ratio >= 0.8:
                        score += 12.0 * best_token_ratio
                    elif best_token_ratio >= 0.65:
                        score += 6.0 * best_token_ratio

            # Whole-string sequence similarity bonus
            full_ratio = difflib.SequenceMatcher(None, norm_query, clean_lower).ratio()
            score += full_ratio * 20.0

            if score >= 12.0:
                scored.append((tid, clean_name, round(score, 2)))

        # Sort descending by score
        scored.sort(key=lambda x: x[2], reverse=True)

        # Deduplicate by Title ID keeping highest score
        seen = set()
        deduped = []
        for tid, name, sc in scored:
            if tid not in seen:
                seen.add(tid)
                deduped.append((tid, name, sc))
            if len(deduped) >= limit:
                break

        return deduped

_global_resolver: Optional[TitleIdResolver] = None

def get_resolver() -> TitleIdResolver:
    global _global_resolver
    if _global_resolver is None:
        _global_resolver = TitleIdResolver()
    return _global_resolver

def search_games_rich(query: str, limit: int = 8) -> List[Dict[str, Any]]:
    return get_resolver().search_games_rich(query, limit=limit)

def resolve_title_id(query: str) -> Optional[Tuple[str, str]]:
    return get_resolver().resolve(query)

if __name__ == "__main__":
    resolver = TitleIdResolver()
    tests = [
        "марио одисея",       # Russian with typo
        "зельда тотк",        # Russian slang
        "ведьмак 3",          # Russian translation
        "слезы королевства",  # Russian full translation
        "ниер автомата 2б",   # Russian translit + character
        "smash broz ultimte", # Multiple typos
        "вайчер 3",           # Phonetic typo
        "metroid dret",       # Typo
        "ксеноблейд 2 пайра", # Russian translit + character
    ]
    print(f"Loaded {len(resolver.games)} games from catalog.\n")
    for t in tests:
        res = resolver.resolve_multiple(t, limit=3)
        print(f"Query: '{t}'")
        for tid, name, sc in res:
            print(f"   -> [{sc}] {name} ({tid})")
        print()
