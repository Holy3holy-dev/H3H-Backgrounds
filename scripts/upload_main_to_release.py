import sys
sys.path.insert(0, "studio")
import json, urllib.request
from pathlib import Path
from h3h_studio.core.github_publisher import GitHubPublisher

token, _ = GitHubPublisher.get_stored_credentials()
headers = {
    "Authorization": f"token {token}",
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "H3H-Uploader"
}
req = urllib.request.Request("https://api.github.com/repos/Holy3holy-dev/H3H-Backgrounds/releases/tags/v1.2.5", headers=headers)
rel = json.loads(urllib.request.urlopen(req).read())
upload_base = rel["upload_url"].split("{")[0]

for asset in rel.get("assets", []):
    if asset.get("name") == "H3H-Backgrounds.nro":
        print(f"Deleting old asset {asset['id']}")
        del_req = urllib.request.Request(f"https://api.github.com/repos/Holy3holy-dev/H3H-Backgrounds/releases/assets/{asset['id']}", headers=headers, method="DELETE")
        urllib.request.urlopen(del_req)

nro_path = Path("downloader/H3H-Backgrounds.nro")
data = nro_path.read_bytes()
up_url = f"{upload_base}?name=H3H-Backgrounds.nro"
up_headers = {
    "Authorization": f"token {token}",
    "Content-Type": "application/octet-stream",
    "User-Agent": "H3H-Uploader"
}
up_req = urllib.request.Request(up_url, data=data, headers=up_headers, method="POST")
res = json.loads(urllib.request.urlopen(up_req).read())
print("[SUCCESS] Uploaded H3H-Backgrounds.nro:", res.get("browser_download_url"))
