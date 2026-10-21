import urllib.request
import re

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

def search_moewalls(query):
    url = f"https://moewalls.com/?s={urllib.parse.quote(query)}"
    req = urllib.request.Request(url, headers=headers)
    try:
        html = urllib.request.urlopen(req, timeout=10).read().decode('utf-8', errors='ignore')
        # Moewalls cards
        posts = re.findall(r'<article[^>]*>.*?<a href="([^"]+)"[^>]*rel="bookmark">(.*?)</a>', html, re.DOTALL)
        if not posts:
            posts = re.findall(r'<a href="(https://moewalls\.com/[^"/]+-[^"/]+/)"[^>]*>(.*?)</a>', html, re.DOTALL)
        print(f"Query '{query}': found {len(posts)} articles")
        for u, t in posts[:5]:
            clean_title = re.sub('<[^<]+?>', '', t).strip()
            print(f"  - {clean_title}: {u}")
    except Exception as e:
        print(f"Error querying {query}: {e}")

def check_article(url):
    req = urllib.request.Request(url, headers=headers)
    html = urllib.request.urlopen(req, timeout=10).read().decode('utf-8', errors='ignore')
    sections = re.findall(r'<section[^>]*id="content[12]"[^>]*>(.*?)</section>', html, re.DOTALL)
    for i, s in enumerate(sections):
        print(f"=== SECTION {i+1} ===")
        for a in re.findall(r'<a\s+[^>]*href="([^"]+)"[^>]*>(.*?)</a>', s, re.DOTALL):
            print("  A:", a)

if __name__ == '__main__':
    check_article("https://moewalls.com/anime/2b-blindfold-nier-automata-live-wallpaper/")

