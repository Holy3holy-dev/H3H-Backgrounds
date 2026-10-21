import json
import re
from pathlib import Path
from typing import Optional, Tuple, List, Dict

class TitleIdResolver:
    """
    Intelligent title and character matcher that resolves Wallpaper Engine items
    and 18+ animated backgrounds to official Nintendo Switch Title IDs.
    """
    def __init__(self, catalog_path: str = "catalog/data/catalog.json"):
        self.catalog_path = Path(catalog_path)
        self.games: List[Dict] = []
        self.normalized_games: List[Tuple[str, str, List[str]]] = []
        self.load_catalog()

        # Character -> Game Title associations for 18+ content
        self.character_mappings = {
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

    def resolve(self, query: str) -> Optional[Tuple[str, str]]:
        """
        Resolves a search query (e.g. 'NieR Automata 2B' or 'Purah Tears of the Kingdom')
        to the best matching (titleId, gameName).
        Returns None if no confident match is found.
        """
        if not query or not query.strip():
            return None
        
        q_lower = query.lower()
        
        # Check character mapping first
        for char_name, mapped_game in self.character_mappings.items():
            if re.search(r"\b" + re.escape(char_name) + r"\b", q_lower):
                # Search using mapped game name
                res = self._match_tokens(mapped_game)
                if res:
                    return res

        return self._match_tokens(query)

    def _match_tokens(self, query: str) -> Optional[Tuple[str, str]]:
        q_tokens = [t for t in re.split(r"[^a-z0-9]+", query.lower()) if len(t) >= 2]
        if not q_tokens:
            return None

        best_score = 0
        best_match = None

        for tid, clean_name, g_tokens in self.normalized_games:
            score = 0
            for qt in q_tokens:
                if qt in g_tokens:
                    score += 10
                elif any(qt in gt for gt in g_tokens):
                    score += 5
            
            # Bonus for exact phrase inclusion
            if query.lower() in clean_name.lower():
                score += 25

            if score > best_score:
                best_score = score
                best_match = (tid, clean_name)

        if best_score >= 10:
            return best_match
        return None

if __name__ == "__main__":
    resolver = TitleIdResolver()
    tests = [
        "NieR Automata 2B Battle Scene",
        "Purah Tears of the Kingdom",
        "Xenoblade Chronicles 2 Pyra & Mythra",
        "Super Smash Bros Ultimate",
        "Witcher 3 Yennefer",
        "Bowsette Super Mario",
        "Hades Aphrodite Romance",
        "Persona 5 Royal Makoto Niijima"
    ]
    print(f"Loaded {len(resolver.games)} games from catalog.")
    for t in tests:
        res = resolver.resolve(t)
        print(f"Query: '{t}' -> Resolved: {res}")
