"""
Upgrade AnimatedIconsFetcher with Steam Avatars (class 15), MoeWalls Live, and APNG support.
"""
from pathlib import Path

def patch_fetcher():
    fetcher_path = Path("studio/h3h_studio/core/animated_icons_fetcher.py")
    content = fetcher_path.read_text(encoding="utf-8")

    # 1. Patch search_steam_points
    old_steam_points = """                    murl = cdata.get("item_movie_mp4", "") or cdata.get("item_movie_webm", "")
                    img = cdata.get("item_image_large", "") or cdata.get("item_image_small", "")
                    
                    if murl:
                        full_murl = f"https://cdn.akamai.steamstatic.com/steamcommunity/public/images/items/{appid}/{murl}"
                        full_thumb = f"https://cdn.akamai.steamstatic.com/steamcommunity/public/images/items/{appid}/{img}" if img else full_murl
                        results.append({
                            "title": f"{appname} — {title}",
                            "source": "steam_points",
                            "source_label": "Магазин Steam",
                            "url": full_murl,
                            "thumb_url": full_thumb,
                            "format": "mp4",
                            "width": 300,
                            "height": 300,
                        })"""

    new_steam_points = """                    murl = cdata.get("item_movie_mp4", "") or cdata.get("item_movie_webm", "")
                    img = cdata.get("item_image_large", "") or cdata.get("item_image_small", "")
                    cclass = d.get("community_item_class", 0)
                    
                    # Steam Points Animated Avatars (class 15) and Stickers (class 11)
                    # store their loops as .gif in item_image_small!
                    if not murl and cdata.get("item_image_small", "").endswith(".gif"):
                        murl = cdata.get("item_image_small")

                    if murl:
                        full_murl = f"https://cdn.akamai.steamstatic.com/steamcommunity/public/images/items/{appid}/{murl}"
                        full_thumb = f"https://cdn.akamai.steamstatic.com/steamcommunity/public/images/items/{appid}/{img}" if img else full_murl
                        fmt = "gif" if murl.endswith(".gif") else ("webm" if murl.endswith(".webm") else "mp4")
                        source_label = "Аватар Steam" if cclass == 15 else ("Стикер Steam" if cclass == 11 else "Магазин Steam")
                        results.append({
                            "title": f"{appname} — {title}",
                            "source": "steam_points",
                            "source_label": source_label,
                            "url": full_murl,
                            "thumb_url": full_thumb,
                            "format": fmt,
                            "width": 300,
                            "height": 300,
                        })"""

    assert old_steam_points in content, "old_steam_points not found"
    content = content.replace(old_steam_points, new_steam_points, 1)

    # 2. Add search_moewalls and update search_all
    old_search_all = """    @classmethod
    def search_all(cls, game_name: str, source_filter: str = "all") -> List[Dict[str, Any]]:
        all_results = []
        if source_filter in ["all", "steam_points"]:
            all_results.extend(cls.search_steam_points(game_name))
        if source_filter in ["all", "steamgriddb"]:
            all_results.extend(cls.search_steamgriddb(game_name))
        if source_filter in ["all", "tenor"]:
            all_results.extend(cls.search_tenor(game_name))
        return all_results"""

    new_search_all = """    @classmethod
    def search_moewalls(cls, game_name: str) -> List[Dict[str, Any]]:
        results = []
        try:
            q = urllib.parse.quote_plus(game_name.strip())
            url = f"https://moewalls.com/?s={q}"
            req = urllib.request.Request(url, headers={"User-Agent": cls.USER_AGENT})
            with urllib.request.urlopen(req, timeout=12) as resp:
                html = resp.read().decode("utf-8", errors="ignore")

            articles = re.findall(
                r'<article[^>]*>.*?<a\s+href="([^"]+)"[^>]*>.*?<img[^>]+(?:data-src|src)="([^"]+)"[^>]*>.*?<h2[^>]*>(?:<a[^>]*>)?([^<]+)',
                html,
                re.DOTALL
            )
            for page_url, thumb_url, title in articles[:10]:
                results.append({
                    "title": f"{title.strip()} (1080p Живые обои)",
                    "source": "moewalls",
                    "source_label": "MoeWalls Live",
                    "url": page_url,
                    "thumb_url": thumb_url,
                    "format": "mp4",
                    "width": 1920,
                    "height": 1080,
                })
        except Exception as e:
            print(f"[-] MoeWalls search error: {e}")
        return results

    @classmethod
    def search_all(cls, game_name: str, source_filter: str = "all") -> List[Dict[str, Any]]:
        all_results = []
        if source_filter in ["all", "steam_points"]:
            all_results.extend(cls.search_steam_points(game_name))
        if source_filter in ["all", "steamgriddb"]:
            all_results.extend(cls.search_steamgriddb(game_name))
        if source_filter in ["all", "moewalls"]:
            all_results.extend(cls.search_moewalls(game_name))
        if source_filter in ["all", "tenor"]:
            all_results.extend(cls.search_tenor(game_name))
        return all_results"""

    assert old_search_all in content, "old_search_all not found"
    content = content.replace(old_search_all, new_search_all, 1)

    # 3. Patch download_and_convert_to_mp4 for MoeWalls & APNG/WebP
    old_download = """        # Use a safe UUID filename to prevent any Unicode/path escaping bugs
        safe_id = f"icon_{uuid.uuid4().hex[:10]}"
        raw_ext = "webp" if "webp" in fmt else ("gif" if "gif" in fmt else ("webm" if "webm" in fmt else "mp4"))
        raw_file = dest_dir / f"{safe_id}_raw.{raw_ext}"
        out_mp4 = dest_dir / f"{safe_id}.mp4"

        try:
            if on_progress:
                on_progress(25, "Скачивание анимации...")

            req = urllib.request.Request(url, headers={"User-Agent": cls.USER_AGENT})"""

    new_download = """        # If MoeWalls, resolve direct mp4 from page
        if item.get("source") == "moewalls":
            try:
                if on_progress:
                    on_progress(15, "Поиск прямого видеопотока MoeWalls...")
                m_req = urllib.request.Request(url, headers={"User-Agent": cls.USER_AGENT})
                with urllib.request.urlopen(m_req, timeout=15) as m_resp:
                    page_html = m_resp.read().decode("utf-8", errors="ignore")
                vlinks = re.findall(r'href="([^"]+\.mp4)"', page_html) or re.findall(r'src="([^"]+\.mp4)"', page_html)
                if vlinks:
                    url = vlinks[0]
                    fmt = "mp4"
            except Exception as e:
                print(f"[-] MoeWalls video resolve error: {e}")

        # Use a safe UUID filename to prevent any Unicode/path escaping bugs
        safe_id = f"icon_{uuid.uuid4().hex[:10]}"
        if "mp4" in fmt:
            raw_ext = "mp4"
        elif "png" in fmt:
            raw_ext = "png"
        elif "webp" in fmt:
            raw_ext = "webp"
        elif "webm" in fmt:
            raw_ext = "webm"
        elif "gif" in fmt:
            raw_ext = "gif"
        else:
            raw_ext = "mp4"

        raw_file = dest_dir / f"{safe_id}_raw.{raw_ext}"
        out_mp4 = dest_dir / f"{safe_id}.mp4"

        try:
            if on_progress:
                on_progress(25, "Скачивание анимации...")

            req = urllib.request.Request(url, headers={"User-Agent": cls.USER_AGENT})"""

    assert old_download in content, "old_download not found"
    content = content.replace(old_download, new_download, 1)

    fetcher_path.write_text(content, encoding="utf-8")
    print("SUCCESS: studio/h3h_studio/core/animated_icons_fetcher.py patched!")

if __name__ == "__main__":
    patch_fetcher()
