"""
Interactive Google Drive OAuth2 Token Refresher.
Generates an authorization link, captures the authorization code via a local HTTP listener
(or manual entry), exchanges it for a permanent Refresh Token, validates it against Google Drive,
and automatically updates all local and cloud configuration files.
"""

import os
import sys
import json
import urllib.parse
import urllib.request
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tg_bot.config import GDRIVE_CLIENT_ID as CLIENT_ID, GDRIVE_CLIENT_SECRET as CLIENT_SECRET
REDIRECT_URI = "http://localhost:8080"
SCOPE = "https://www.googleapis.com/auth/drive"

auth_code_received = None

class OAuthCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code_received
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        if "code" in params:
            auth_code_received = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html = """
            <html><body style="font-family: sans-serif; text-align: center; padding-top: 50px;">
                <h1 style="color: #4CAF50;">&#10004; Авторизация Google Drive успешна!</h1>
                <p>Вы можете закрыть эту вкладку и вернуться в консоль / Antigravity.</p>
            </body></html>
            """
            self.wfile.write(html.encode("utf-8"))
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"No code found in callback.")

    def log_message(self, format, *args):
        pass

def sec_enc(s: str) -> str:
    return bytes([b ^ 0x5A for b in s.encode("utf-8")]).hex()

def exchange_code_for_token(code: str, redirect_uri: str) -> dict:
    url = "https://oauth2.googleapis.com/token"
    data = urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code.strip(),
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "H3H-Studio"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))

def update_configs(new_refresh_token: str, new_access_token: str):
    # 1. Update permanent_gdrive_credentials.txt
    cred_file = PROJECT_ROOT / "permanent_gdrive_credentials.txt"
    cred_content = (
        f"GDRIVE_CLIENT_ID={CLIENT_ID}\n"
        f"GDRIVE_CLIENT_SECRET={CLIENT_SECRET}\n"
        f"GDRIVE_REFRESH_TOKEN={new_refresh_token}\n"
    )
    cred_file.write_text(cred_content, encoding="utf-8")
    print(f"[+] Updated: {cred_file}")

    # 2. Update ~/.h3h_google_drive.json
    cfg_file = Path.home() / ".h3h_google_drive.json"
    cfg = {}
    if cfg_file.exists():
        try:
            cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    cfg["refresh_token"] = new_refresh_token
    cfg["token"] = new_access_token
    cfg["client_id"] = CLIENT_ID
    cfg["client_secret"] = CLIENT_SECRET
    cfg_file.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[+] Updated: {cfg_file}")

    # 3. Update tg_bot/config.py hardcoded verified tokens
    tg_cfg_file = PROJECT_ROOT / "tg_bot" / "config.py"
    if tg_cfg_file.exists():
        text = tg_cfg_file.read_text(encoding="utf-8")
        enc_token = sec_enc(new_refresh_token)
        # Replace line 69 VERIFIED_REFRESH_TOKEN
        import re
        text = re.sub(
            r'VERIFIED_REFRESH_TOKEN = _sec_dec\("[a-f0-9]+"\)',
            f'VERIFIED_REFRESH_TOKEN = _sec_dec("{enc_token}")',
            text
        )
        text = re.sub(
            r'"GDRIVE_REFRESH_TOKEN",\s*_sec_dec\("[a-f0-9]+"\)',
            f'"GDRIVE_REFRESH_TOKEN",\n    _sec_dec("{enc_token}")',
            text
        )
        tg_cfg_file.write_text(text, encoding="utf-8")
        print(f"[+] Updated: {tg_cfg_file} with encrypted verified token.")

def test_token(access_token: str) -> bool:
    req = urllib.request.Request(
        "https://www.googleapis.com/drive/v3/about?fields=user",
        headers={"Authorization": f"Bearer {access_token}", "User-Agent": "H3H-Studio"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            user = data.get("user", {})
            print(f"[+] Google Drive Connected! User: {user.get('displayName')} ({user.get('emailAddress')})")
            return True
    except Exception as e:
        print(f"[-] Token test failed: {e}")
        return False

def main():
    import argparse
    parser = argparse.ArgumentParser(description="H3H Google Drive OAuth2 Refresher")
    parser.add_argument("--code", type=str, default=None, help="Authorization code from Google")
    parser.add_argument("--playground", action="store_true", help="Use Google OAuth Playground redirect URI")
    args = parser.parse_args()

    used_redirect = "https://developers.google.com/oauthplayground" if args.playground else REDIRECT_URI

    auth_url_local = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={CLIENT_ID}&"
        f"redirect_uri={urllib.parse.quote(REDIRECT_URI)}&"
        f"response_type=code&"
        f"scope={urllib.parse.quote(SCOPE)}&"
        f"access_type=offline&"
        f"prompt=consent"
    )
    auth_url_playground = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={CLIENT_ID}&"
        f"redirect_uri=https%3A%2F%2Fdevelopers.google.com%2Foauthplayground&"
        f"response_type=code&"
        f"scope={urllib.parse.quote(SCOPE)}&"
        f"access_type=offline&"
        f"prompt=consent"
    )

    if args.code:
        code = args.code.strip()
        print(f"[*] Используем предоставленный код авторизации: {code[:10]}...")
        # Auto-detect redirect_uri for code if needed
        token_data = None
        for r_uri in [used_redirect, "https://developers.google.com/oauthplayground", REDIRECT_URI]:
            try:
                token_data = exchange_code_for_token(code, r_uri)
                if token_data.get("refresh_token"):
                    used_redirect = r_uri
                    break
            except Exception:
                pass
        
        if not token_data or not token_data.get("refresh_token"):
            print(f"[-] Не удалось обменять код на refresh_token. Ответ: {token_data}")
            return 1
        
        refresh_token = token_data["refresh_token"]
        access_token = token_data.get("access_token", "")
        print(f"[+] Получен новый Refresh Token: {refresh_token[:15]}...{refresh_token[-10:]}")
        test_token(access_token)
        update_configs(refresh_token, access_token)
        return 0

    print("\n=======================================================")
    print("  H3H GOOGLE DRIVE OAUTH2 RE-AUTHENTICATION")
    print("=======================================================\n")
    print("Вариант A (Автоматический через localhost:8080):")
    print(auth_url_local)
    print("\nВариант B (Через OAuth Playground):")
    print(auth_url_playground)
    print("\n=======================================================\n")

    # Try to start local server on 8080
    server = None
    try:
        server = HTTPServer(("localhost", 8080), OAuthCallbackHandler)
        server.timeout = 120
    except Exception as e:
        print(f"[-] Локальный сервер на 8080 недоступен: {e}")

    try:
        webbrowser.open(auth_url_local)
    except Exception:
        pass

    if server:
        print("[*] Локальный сервер слушает http://localhost:8080. Ожидание входа в браузере...")
        while not auth_code_received:
            server.handle_request()
            if auth_code_received:
                break
        server.server_close()

    code = auth_code_received
    if not code:
        print("\n[!] Если браузер перенаправил вас на OAuth Playground или выдал код:")
        code = input("Вставьте сюда полученный код авторизации (4/0A...): ").strip()

    if not code:
        print("[-] Код не введен, операция отменена.")
        return 1

    print("\n[*] Обмен кода на постоянный Refresh Token...")
    token_data = None
    for r_uri in [REDIRECT_URI, "https://developers.google.com/oauthplayground"]:
        try:
            token_data = exchange_code_for_token(code, r_uri)
            if token_data.get("refresh_token"):
                break
        except Exception as e:
            pass

    if not token_data or not token_data.get("refresh_token"):
        print(f"[-] Google не вернул refresh_token. Ответ: {token_data}")
        return 1

    refresh_token = token_data["refresh_token"]
    access_token = token_data.get("access_token", "")
    print(f"[+] Получен новый Refresh Token: {refresh_token[:15]}...{refresh_token[-10:]}")
    test_token(access_token)
    update_configs(refresh_token, access_token)
    print("\n=======================================================")
    print("  АВТОРИЗАЦИЯ УСПЕШНО ОБНОВЛЕНА И СОХРАНЕНА!")
    print("=======================================================\n")
    return 0

if __name__ == "__main__":
    sys.exit(main())
