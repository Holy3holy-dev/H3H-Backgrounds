import json
import urllib.request

cat = json.load(open('catalog/data/catalog.json', encoding='utf-8'))
zero_variants = []
for g in cat['games']:
    for v in g.get('variants', []):
        if v.get('sizeBytes', 0) == 0:
            zero_variants.append((g['title'], v['name'], v.get('url', ''), v.get('previewUrl', '')))

print(f"Total zero size variants: {len(zero_variants)}")
print("Checking first 10 zero-size variants...")

ua = 'Mozilla/5.0 (Nintendo Switch; ShareApplet) AppleWebKit/609.4 (KHTML, like Gecko) NF/6.0.2.22.5 NintendoBrowser/5.1.0.22474'

for title, name, url, p_url in zero_variants[:10]:
    # Check video url
    v_stat = 'OK'
    v_size = 0
    try:
        req = urllib.request.Request(url, headers={'User-Agent': ua})
        with urllib.request.urlopen(req, timeout=6) as r:
            data = r.read(128)
            v_size = len(data)
            ct = r.headers.get('Content-Type')
            is_mp4 = b'ftyp' in data or b'moov' in data
            v_stat = f"{r.status} {ct} is_mp4={is_mp4}"
    except Exception as e:
        v_stat = f"ERR: {e}"

    # Check preview url
    p_stat = 'OK'
    try:
        t_url = p_url.replace('sz=w640', 'sz=w1280')
        req = urllib.request.Request(t_url, headers={'User-Agent': ua})
        with urllib.request.urlopen(req, timeout=6) as r:
            p_data = r.read(64)
            p_stat = f"{r.status} {r.headers.get('Content-Type')} is_jpg={p_data[:2] == b'\xff\xd8'}"
    except Exception as e:
        p_stat = f"ERR: {e}"

    print(f"\n{title} - {name}:")
    print(f"  Video:   {v_stat}")
    print(f"  Preview: {p_stat}")
