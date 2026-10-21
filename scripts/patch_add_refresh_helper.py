from pathlib import Path

p = Path("studio/h3h_studio/core/google_drive.py")
text = p.read_text(encoding="utf-8")

refresh_func = '''    @classmethod
    def refresh_access_token(cls, refresh_token: str) -> Optional[str]:
        """
        Refreshes access token via OAuth Playground refresh endpoint.
        Returns the new 'ya29...' access token or None.
        """
        if not refresh_token or not refresh_token.strip():
            return None
        url = "https://developers.google.com/oauthplayground/refreshAccessToken"
        payload = {
            "token_uri": "https://oauth2.googleapis.com/token",
            "refresh_token": refresh_token.strip()
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0"
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                msg_b64 = data.get("Response", {}).get("message-body", "")
                if msg_b64:
                    body_str = base64.b64decode(msg_b64).decode("utf-8")
                    token_data = json.loads(body_str)
                    new_tok = token_data.get("access_token")
                    if new_tok and new_tok.startswith("ya29."):
                        return new_tok
        except Exception as e:
            print(f"[-] Auto-refresh error: {e}")
        return None
'''

if "def refresh_access_token" not in text:
    target = "    @classmethod\n    def get_stored_config(cls) -> Dict[str, Any]:"
    text = text.replace(target, refresh_func + "\n" + target)
    p.write_text(text, encoding="utf-8")
    print("GoogleDriveHelper.refresh_access_token added!")
else:
    print("Already present.")
