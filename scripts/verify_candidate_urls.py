import urllib.request

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

test_urls = [
    ("nier-2b-white-lily", "https://moewalls.com/wp-content/uploads/preview/2024/2b-in-the-field-of-blue-lilies-nier-automata-preview.webm"),
    ("ff7-tifa-starry-sky", "https://moewalls.com/wp-content/uploads/preview/2022/tifa-lockhart-starry-sky-final-fantasy-vii-preview.webm"),
    ("ff7-tifa-flower-field", "https://moewalls.com/wp-content/uploads/preview/2026/tifa-relaxing-flower-field-final-fantasy-vii-remake-preview.webm"),
    ("zelda-holy-knight", "https://moewalls.com/wp-content/uploads/preview/2026/zelda-holy-knight-the-legend-of-zelda-preview.webm"),
    ("bayonetta-cereza-glamour", "https://moewalls.com/wp-content/uploads/preview/2026/cereza-bayonetta-preview.webm"),
    ("genshin-raiden-throne", "https://moewalls.com/wp-content/uploads/preview/2026/raiden-shogun-throne-room-genshin-impact-preview.webm"),
    ("genshin-yae-sakura", "https://moewalls.com/wp-content/uploads/preview/2026/yae-miko-sakura-cherry-blossoms-genshin-impact-preview.webm"),
    ("genshin-arlecchino-blood", "https://moewalls.com/wp-content/uploads/preview/2026/arlecchino-crimson-moon-genshin-impact-preview.webm"),
    ("cyberpunk-lucy-moon", "https://moewalls.com/wp-content/uploads/preview/2022/lucy-cyberpunk-edgerunners-1-preview.webm"),
    ("stellar-blade-eve-suit", "https://moewalls.com/wp-content/uploads/preview/2025/eve-stellar-blade-preview.webm"),
    ("nikke-cinderella-bikini", "https://moewalls.com/wp-content/uploads/preview/2026/cinderella-bikini-goddess-of-victory-nikke-preview.webm"),
    ("nikke-sakura-summer", "https://moewalls.com/wp-content/uploads/preview/2026/nikke-sakura-bloom-in-summer-preview.webm"),
    ("azur-lane-prinz-eugen-bikini", "https://moewalls.com/wp-content/uploads/preview/2022/prinz-eugen-bikini-azur-lane-preview.webm"),
    ("honkai-kafka-spider", "https://moewalls.com/wp-content/uploads/preview/2024/kafka-honkai-star-rail-1-preview.webm"),
    ("chainsaw-makima-eyes", "https://moewalls.com/wp-content/uploads/preview/2022/makima-controlling-chainsaw-man-y-preview.webm")
]

for vid_id, u in test_urls:
    req = urllib.request.Request(u, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            print(f"[OK] {vid_id}: {r.status} (Size: {r.headers.get('Content-Length')})")
    except Exception as e:
        print(f"[FAIL] {vid_id}: {e}")
