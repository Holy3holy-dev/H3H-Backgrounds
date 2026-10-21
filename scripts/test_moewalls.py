import urllib.request
import re

url = "https://moewalls.com/category/anime/"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
html = urllib.request.urlopen(req, timeout=10).read().decode("utf-8")

posts = re.findall(r'<h2 class="entry-title"[^>]*><a href="([^"]+)"[^>]*>([^<]+)</a>', html)
print(f"[*] Found {len(posts)} posts:")
for url, title in posts[:5]:
    print(f"  - {title}: {url}")

if posts:
    sample_url = posts[0][0]
    p_html = urllib.request.urlopen(urllib.request.Request(sample_url, headers={"User-Agent": "Mozilla/5.0"})).read().decode("utf-8")
    vids = re.findall(r'<source[^>]*src="([^"]+\.mp4)"', p_html)
    if not vids:
        vids = re.findall(r'href="([^"]+\.mp4)"', p_html)
    print(f"[*] Video URLs for '{posts[0][1]}':", vids)
