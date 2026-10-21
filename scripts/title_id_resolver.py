import json
import re
import difflib
from pathlib import Path
from typing import Optional, Tuple, List, Dict

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
    }

    def __init__(self, catalog_path: str = "catalog/data/catalog.json"):
        self.catalog_path = Path(catalog_path)
        self.games: List[Dict] = []
        self.normalized_games: List[Tuple[str, str, List[str]]] = []
        self.load_catalog()

    def load_catalog(self):
        if not self.catalog_path.exists():
            return
        data = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        self.games = data.get("games", [])
        self.normalized_games.clear()
        for g in self.games:
            tid = g.get("titleId", "")
            title = g.get("title", "")
            clean = self.clean_title(title)
            tokens = [t for t in re.split(r"[^a-z0-9]+", clean.lower()) if len(t) >= 2]
            self.normalized_games.append((tid, clean, tokens))

    @staticmethod
    def clean_title(title: str) -> str:
        t = re.sub(r"\[.*?\]", "", title)
        t = re.sub(r"\(.*?\)", "", t)
        t = re.sub(r"\+.*$", "", t)
        t = re.sub(r"[^\w\s\:\-\'\.]", " ", t)
        return " ".join(t.split())

    @classmethod
    def normalize_input(cls, query: str) -> str:
        """Converts Russian aliases and transliterates Cyrillic to Latin."""
        q = query.lower().strip()
        # Replace known Russian slang/aliases
        for ru, en in cls.RUSSIAN_ALIASES.items():
            pattern = r"\b" + re.escape(ru) + r"\b"
            q = re.sub(pattern, en, q)
        # Transliterate any remaining Cyrillic letters
        return "".join(cls.CYRILLIC_TO_LATIN.get(c, c) for c in q)

    def resolve_by_title_id(self, title_id: str) -> Optional[str]:
        """Looks up a clean game title directly by its 16-hex Title ID."""
        if not title_id:
            return None
        tid_upper = title_id.strip().upper()
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
        q_tokens = [t for t in re.split(r"[^a-z0-9]+", norm_query) if len(t) >= 2]

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
