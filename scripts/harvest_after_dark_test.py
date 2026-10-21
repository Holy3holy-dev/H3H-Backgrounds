import urllib.request
import re
import json

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

targets = [
    # (Category/Game, TitleID, SearchQuery, max_items)
    ("NieR:Automata", "01005C000B2AE000", "2b nier", 2),
    ("Final Fantasy VII", "0100A5B00BDC6000", "tifa", 2),
    ("Cyberpunk Edgerunners", "0000000000000000", "lucy cyberpunk", 2),
    ("Genshin Impact", "0000000000000000", "raiden shogun", 2),
    ("Stellar Blade", "0000000000000000", "eve stellar blade", 2),
    ("NIKKE", "0000000000000000", "nikke bikini", 2),
    ("Azur Lane", "0000000000000000", "azur lane bikini", 2),
    ("Honkai: Star Rail", "0000000000000000", "kafka honkai", 1),
]

def get_candidates():
    candidates = []
    for game_name, title_id, query, limit in targets:
        url = f"https://moewalls.com/?s={urllib.parse.quote(query)}"
        req = urllib.request.Request(url, headers=headers)
        try:
            html = urllib.request.urlopen(req, timeout=10).read().decode('utf-8', errors='ignore')
            articles = re.findall(r'<article[^>]*>.*?<a href="([^"]+)"[^>]*rel="bookmark">(.*?)</a>', html, re.DOTALL)
            count = 0
            for art_url, raw_title in articles:
                if count >= limit:
                    break
                clean_title = re.sub('<[^<]+?>', '', raw_title).strip()
                # Fetch article to get video and poster
                art_req = urllib.request.Request(art_url, headers=headers)
                art_html = urllib.request.urlopen(art_req, timeout=10).read().decode('utf-8', errors='ignore')
                
                # Find video source
                vid_match = re.search(r'<source\s+[^>]*src="([^"]+\.(?:webm|mp4))"', art_html)
                if not vid_match:
                    continue
                vid_url = vid_match.group(1)
                if vid_url.startswith('/'):
                    vid_url = f"https://moewalls.com{vid_url}"
                
                # Find poster
                poster_match = re.search(r'<video[^>]*poster="([^"]+)"', art_html)
                poster_url = None
                if poster_match:
                    poster_url = poster_match.group(1)
                    if poster_url.startswith('/'):
                        poster_url = f"https://moewalls.com{poster_url}"
                
                candidates.append({
                    "game_name": game_name,
                    "title_id": title_id,
                    "title": clean_title,
                    "art_url": art_url,
                    "vid_url": vid_url,
                    "poster_url": poster_url
                })
                count += 1
                print(f"[FOUND] {game_name}: {clean_title}")
                print(f"        Video:  {vid_url}")
                print(f"        Poster: {poster_url}")
        except Exception as e:
            print(f"Error on query {query}: {e}")
            
    print(f"\nTotal candidates collected: {len(candidates)}")
    with open("tmp_after_dark_candidates.json", "w", encoding="utf-8") as f:
        json.dump(candidates, f, indent=2, ensure_ascii=False)

if __name__ == '__main__':
    get_candidates()
