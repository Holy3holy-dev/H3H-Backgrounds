from pathlib import Path

p = Path("studio/h3h_studio/core/steamgriddb.py")
text = p.read_text(encoding="utf-8")

old_code = '''    def search_game(self, query: str) -> List[Dict[str, Any]]:
        """Search SteamGridDB for games matching query string."""
        if not query or not query.strip():
            return []
        term = urllib.parse.quote(query.strip())
        url = f"{self.BASE_URL}/search/autocomplete/{term}"
        req = urllib.request.Request(url, headers=self._get_headers())
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("success"):
                    return data.get("data", [])
        except Exception as e:
            logger.error("SteamGridDB search error for '%s': %s", query, e)
        return []

    def get_animated_heroes(self, game_id: int) -> List[Dict[str, Any]]:
        """Get animated hero artworks (wide banners) for a game."""
        url = f"{self.BASE_URL}/heroes/game/{game_id}?types=animated"
        req = urllib.request.Request(url, headers=self._get_headers())
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("success"):
                    return data.get("data", [])
        except Exception as e:
            logger.error("SteamGridDB get_animated_heroes error for %s: %s", game_id, e)
        return []

    def get_animated_grids(self, game_id: int) -> List[Dict[str, Any]]:
        """Get animated grid artworks (covers) for a game."""
        url = f"{self.BASE_URL}/grids/game/{game_id}?types=animated"
        req = urllib.request.Request(url, headers=self._get_headers())
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("success"):
                    return data.get("data", [])
        except Exception as e:
            logger.error("SteamGridDB get_animated_grids error for %s: %s", game_id, e)
        return []'''

new_code = '''    def _fetch_json_with_retry(self, url: str, retries: int = 2) -> Optional[Dict[str, Any]]:
        req = urllib.request.Request(url, headers=self._get_headers())
        for attempt in range(retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=25) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except Exception as e:
                if attempt == retries:
                    logger.warning("SteamGridDB request failed after %d retries: %s (%s)", retries, url, e)
                time.sleep(1)
        return None

    def search_game(self, query: str) -> List[Dict[str, Any]]:
        """Search SteamGridDB for games matching query string."""
        if not query or not query.strip():
            return []
        term = urllib.parse.quote(query.strip())
        url = f"{self.BASE_URL}/search/autocomplete/{term}"
        data = self._fetch_json_with_retry(url)
        if data and data.get("success"):
            return data.get("data", [])
        return []

    def get_animated_heroes(self, game_id: int) -> List[Dict[str, Any]]:
        """Get animated hero artworks (wide banners) for a game."""
        url = f"{self.BASE_URL}/heroes/game/{game_id}?types=animated"
        data = self._fetch_json_with_retry(url)
        if data and data.get("success"):
            return data.get("data", [])
        return []

    def get_animated_grids(self, game_id: int) -> List[Dict[str, Any]]:
        """Get animated grid artworks (covers) for a game."""
        url = f"{self.BASE_URL}/grids/game/{game_id}?types=animated"
        data = self._fetch_json_with_retry(url)
        if data and data.get("success"):
            return data.get("data", [])
        return []'''

assert old_code in text, "old_code not found in steamgriddb.py"
text = text.replace(old_code, new_code)
# Ensure import time is present
if "import time" not in text:
    text = "import time\n" + text
p.write_text(text, encoding="utf-8")
print("Successfully patched steamgriddb.py with retries and timeout=25!")
