"""
H3H Permanent Google Drive OAuth Token Generator.
Runs a local loopback server, opens Google Auth in your browser,
exchanges the auth code for a permanent offline Refresh Token,
and saves everything to ~/.h3h_google_drive.json.
"""

import sys
import json
import urllib.request
import urllib.parse
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

def load_credentials():
    cfg_file = Path.home() / ".h3h_google_drive.json"
    if cfg_file.exists():
        try:
            cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
            cid = cfg.get("client_id")
            csec = cfg.get("client_secret")
            if cid and csec:
                return cid, csec
        except Exception:
            pass

    # Look for client_secret_*.json in Downloads
    dl = Path.home() / "Downloads"
    for f in dl.glob("client_secret_*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            installed = data.get("installed") or data.get("web")
            if installed:
                return installed.get("client_id"), installed.get("client_secret")
        except Exception:
            pass
    return None, None

PORT = 8088
REDIRECT_URI = f"http://localhost:{PORT}"

auth_code = None

class OAuthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)

        if "code" in params:
            auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html = """
            <html>
            <body style="font-family: sans-serif; text-align: center; padding: 50px; background: #0f172a; color: #f8fafc;">
                <h1 style="color: #38bdf8;">✅ Авторизация успешна!</h1>
                <p style="font-size: 18px;">Вечный токен Google Drive получен и сохранён в H3H Studio.</p>
                <p style="color: #94a3b8;">Теперь это окно можно закрыть.</p>
            </body>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
        else:
            err = params.get("error", ["Unknown error"])[0]
            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(f"<h1>Ошибка авторизации: {err}</h1>".encode("utf-8"))

    def log_message(self, format, *args):
        pass  # suppress request logging

def main():
    print("=" * 60)
    print("  H3H GOOGLE DRIVE - PERMANENT REFRESH TOKEN GENERATOR")
    print("=" * 60)

    client_id, client_secret = load_credentials()
    if not client_id or not client_secret:
        print("[-] Credentials not found. Please provide client_secret_*.json in Downloads or ~/.h3h_google_drive.json")
        return 1

    # Scopes: Drive access for uploading Switch wallpapers
    scope = "https://www.googleapis.com/auth/drive"
    
    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        + urllib.parse.urlencode({
            "client_id": client_id,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": scope,
            "access_type": "offline",  # Request permanent refresh token
            "prompt": "consent"        # Ensure Google returns refresh_token every time
        })
    )

    print(f"[*] Starting local OAuth listener on port {PORT}...")
    server = HTTPServer(("localhost", PORT), OAuthHandler)

    print("[*] Opening Google login in your default browser...")
    webbrowser.open(auth_url)

    print(f"\nЕсли браузер не открылся автоматически, перейдите по этой ссылке:\n{auth_url}\n")
    print("[*] Ожидание подтверждения в браузере...")

    while not auth_code:
        server.handle_request()

    server.server_close()
    print("[+] Код авторизации получен!")
    print("[*] Обмен кода на вечный Refresh Token у Google...")

    token_payload = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "code": auth_code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=token_payload,
        headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "H3H-OAuth"}
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            token_data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[-] Ошибка обмена токена: {e}")
        return 1

    refresh_token = token_data.get("refresh_token")
    access_token = token_data.get("access_token")

    if not refresh_token:
        print("[-] Ошибка: Google не вернул refresh_token в ответе:")
        print(token_data)
        return 1

    # Save to user config first
    cfg_file = Path.home() / ".h3h_google_drive.json"
    cfg = {}
    if cfg_file.exists():
        try:
            cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    cfg["client_id"] = client_id
    cfg["client_secret"] = client_secret
    cfg["refresh_token"] = refresh_token
    if access_token:
        cfg["token"] = access_token

    cfg_file.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")

    out_file = Path(__file__).resolve().parent.parent / "permanent_gdrive_credentials.txt"
    out_file.write_text(
        f"GDRIVE_CLIENT_ID={client_id}\n"
        f"GDRIVE_CLIENT_SECRET={client_secret}\n"
        f"GDRIVE_REFRESH_TOKEN={refresh_token}\n",
        encoding="utf-8"
    )

    print("\n" + "=" * 60)
    print("[SUCCESS] PERMANENT REFRESH TOKEN RECEIVED AND SAVED!")
    print("=" * 60)
    print(f"Refresh Token: {refresh_token}")
    print("=" * 60)
    print(f"[+] Saved to {cfg_file}")
    print(f"[+] Saved to {out_file}")
    print(f"[+] Также сохранено в {out_file} (для настроек хостинга)")
    print("\nГотово! Теперь этот токен никогда не сгорит!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
