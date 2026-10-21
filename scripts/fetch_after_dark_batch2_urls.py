import urllib.request
import re
import json

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

pages = [
    # Xenoblade Chronicles 2
    {"tid": "0100E95004038000", "game": "Xenoblade Chronicles 2", "name": "Mythra: Full Moon Starry Night", "page": "https://moewalls.com/anime/mythra-full-moon-starry-night-xenoblade-chronicles-2-live-wallpaper/"},
    # Persona 5 Royal
    {"tid": "010091200CDA4000", "game": "Persona 5 Royal", "name": "Ann Takamaki: Summer Vacation", "page": "https://moewalls.com/games/ann-takamaki-summer-vacation-persona-5-live-wallpaper/"},
    {"tid": "010091200CDA4000", "game": "Persona 5 Royal", "name": "Kasumi Yoshizawa: Violet Blossom", "page": "https://moewalls.com/anime/kasumi-yoshizawa-persona-5-royal-x-heaven-burns-red-live-wallpaper/"},
    # NieR:Automata
    {"tid": "01005C000B2AE000", "game": "NieR:Automata The End of YoRHa Edition", "name": "2B & A2: In the Rain", "page": "https://moewalls.com/games/2b-and-a2-in-the-rain-nier-automata-live-wallpaper/"},
    {"tid": "01005C000B2AE000", "game": "NieR:Automata The End of YoRHa Edition", "name": "A2: Lying on the Water", "page": "https://moewalls.com/games/a2-lying-on-the-water-nier-automata-live-wallpaper/"},
    # The Witcher 3
    {"tid": "0100E8B00BDC6000", "game": "The Witcher 3: Wild Hunt - Complete Edition", "name": "Yennefer & Geralt: Midnight Embrace", "page": "https://moewalls.com/games/geralt-and-yennefer-the-witcher-3-wild-hunt-live-wallpaper/"},
    # Free Choice (0000000000000000)
    {"tid": "0000000000000000", "game": "★ Коллекция After Dark (Свободный выбор)", "name": "Sugar: Killer Rabbit Bunny Suit (NIKKE)", "page": "https://moewalls.com/anime/sugar-killer-rabbit-nikke-live-wallpaper/"},
    {"tid": "0000000000000000", "game": "★ Коллекция After Dark (Свободный выбор)", "name": "Akane: Bunny Girl (Blue Archive)", "page": "https://moewalls.com/anime/murokasa-akane-bunny-girl-blue-archive-live-wallpaper/"},
    {"tid": "0000000000000000", "game": "★ Коллекция After Dark (Свободный выбор)", "name": "Makoto: Summer Swimsuit (Blue Archive)", "page": "https://moewalls.com/anime/hanuma-makoto-swimsuit-blue-archive-live-wallpaper/"},
    {"tid": "0000000000000000", "game": "★ Коллекция After Dark (Свободный выбор)", "name": "Mai Sakurajima: Bunny Girl Senpai", "page": "https://moewalls.com/anime/mai-sakurajima-in-her-bunny-suit-rascal-does-not-dream-of-a-dreaming-girl-live-wallpaper/"},
    {"tid": "0000000000000000", "game": "★ Коллекция After Dark (Свободный выбор)", "name": "Scathach: Crimson Lancer (Fate)", "page": "https://moewalls.com/anime/scathach-fate-grand-order-2-live-wallpaper/"},
    {"tid": "0000000000000000", "game": "★ Коллекция After Dark (Свободный выбор)", "name": "Saber: White Lilies (Fate)", "page": "https://moewalls.com/anime/saber-white-lilies-fate-series-live-wallpaper/"},
    {"tid": "0000000000000000", "game": "★ Коллекция After Dark (Свободный выбор)", "name": "Power: Blood Fiend (Chainsaw Man)", "page": "https://moewalls.com/anime/power-chainsaw-man-5-y-live-wallpaper/"}
]

found = []
for item in pages:
    req = urllib.request.Request(item["page"], headers=headers)
    try:
        html = urllib.request.urlopen(req, timeout=12).read().decode('utf-8', errors='ignore')
        # Find video preview or download URL
        # Moewalls uses <source src="...preview.webm" or "...preview.mp4"
        vids = re.findall(r'<source[^>]*src="([^"]+\.(?:webm|mp4))"', html)
        if not vids:
            vids = re.findall(r'href="([^"]+\.(?:webm|mp4))"', html)
        if vids:
            vid_url = vids[0]
            item["vid_url"] = vid_url
            found.append(item)
            print(f"[+] {item['name']} -> {vid_url}")
        else:
            print(f"[-] No video found for {item['name']}")
    except Exception as e:
        print(f"[!] Error fetching {item['name']}: {e}")

with open('tmp_after_dark_batch2.json', 'w', encoding='utf-8') as f:
    json.dump(found, f, indent=2, ensure_ascii=False)
print(f"Found {len(found)} candidate videos saved to tmp_after_dark_batch2.json")
