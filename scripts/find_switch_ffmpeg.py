import urllib.request
import re

for url in [
    "https://pkg.devkitpro.org/packages/",
    "https://pkg.devkitpro.org/packages/switch-portlibs/",
    "https://pkg.devkitpro.org/packages/switch-dev/",
    "https://downloads.devkitpro.org/packages/",
]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as resp:
            content = resp.read().decode("utf-8", errors="ignore")
            matches = [m for m in re.findall(r'href=["\']([^"\']+)["\']', content) if "ffmpeg" in m.lower()]
            print(f"{url} -> {matches}")
    except Exception as e:
        print(f"{url} -> {e}")
