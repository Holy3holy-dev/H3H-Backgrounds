import urllib.request
import re

url = 'https://moewalls.com/tag/bikini/'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
html = urllib.request.urlopen(req, timeout=8).read().decode('utf-8', errors='ignore')

# Check both patterns
articles = re.findall(r'<article[^>]*>.*?<a href="([^"]+)"[^>]*rel="bookmark">(.*?)</a>', html, re.DOTALL)
print('Articles with rel=bookmark:', len(articles))
if not articles:
    articles = re.findall(r'<article[^>]*>.*?<a href="([^"]+)"[^>]*title="([^"]+)"', html, re.DOTALL)
    print('Articles with title attribute:', len(articles))

for a in articles[:4]:
    print(' ', a[0], '->', a[1].strip())
