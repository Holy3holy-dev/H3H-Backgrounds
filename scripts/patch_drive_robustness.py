from pathlib import Path

path = Path("studio/h3h_studio/core/google_drive.py")
content = path.read_text(encoding="utf-8")

old_block = """        try:
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
        return None"""

new_block = """        for attempt in range(1, 5):
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    msg_b64 = data.get("Response", {}).get("message-body", "")
                    if msg_b64:
                        body_str = base64.b64decode(msg_b64).decode("utf-8")
                        token_data = json.loads(body_str)
                        new_tok = token_data.get("access_token")
                        if new_tok and new_tok.startswith("ya29."):
                            return new_tok
            except Exception as e:
                print(f"[-] Auto-refresh attempt {attempt}/4 error: {e}")
                if attempt < 4:
                    time.sleep(2 * attempt)
        return None"""

if old_block in content:
    content = content.replace(old_block, new_block)
    path.write_text(content, encoding="utf-8")
    print("SUCCESS: patched refresh_access_token")
else:
    print("ERROR: old_block not found in google_drive.py")
