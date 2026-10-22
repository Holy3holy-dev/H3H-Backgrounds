from pathlib import Path

bot_py = Path("tg_bot/bot.py")
text = bot_py.read_text(encoding="utf-8")

old_health = '''# --- Cloud Web Health Check Server (Port 10000 for Render) ---

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(b'<h1>H3H Backgrounds Telegram Bot is Live!</h1>')

    def log_message(self, format, *args):
        pass

def start_health_server():
    port = int(os.getenv('PORT', 10000))
    try:
        server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
        print(f'[*] Health check server listening on 0.0.0.0:{port}')
        server.serve_forever()
    except Exception as e:
        print(f'[*] Health check server notice (safe to ignore locally): {e}')

threading.Thread(target=start_health_server, daemon=True).start()'''

new_health = '''# --- Cloud Web Health Check Server & Anti-Sleep Self-Pinger (Port 10000 for Render) ---

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(b'<h1>H3H Backgrounds Telegram Bot is Live (24/7 Anti-Sleep)!</h1>')

    def log_message(self, format, *args):
        pass

def keep_alive_self_pinger():
    """Pings Render external URL every 8 minutes through public edge to prevent 15-min idle spin-down."""
    time.sleep(30)  # Wait for initial boot
    url = (os.getenv("RENDER_EXTERNAL_URL") or os.getenv("RENDER_SERVICE_URL") or "").strip()
    if not url:
        return
    print(f"[*] Render Anti-Sleep Self-Pinger activated for: {url}")
    while True:
        time.sleep(8 * 60)  # Ping every 8 minutes (Render spins down at 15 minutes)
        try:
            req = urllib.request.Request(
                f"{url.rstrip('/')}/",
                headers={"User-Agent": "H3H-AntiSleep-KeepAlive/1.0"}
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                print(f"[*] Keep-Alive self-ping OK ({resp.status})")
        except Exception as e:
            print(f"[-] Keep-Alive ping notice: {e}")

def start_health_server():
    port = int(os.getenv('PORT', 10000))
    try:
        server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
        print(f'[*] Health check server listening on 0.0.0.0:{port}')
        server.serve_forever()
    except Exception as e:
        print(f'[*] Health check server notice (safe to ignore locally): {e}')

threading.Thread(target=start_health_server, daemon=True).start()
threading.Thread(target=keep_alive_self_pinger, daemon=True).start()'''

if old_health in text:
    text = text.replace(old_health, new_health, 1)
    print("[+] Patched bot.py with Anti-Sleep Self-Pinger")
else:
    old_crlf = old_health.replace("\n", "\r\n")
    if old_crlf in text:
        text = text.replace(old_crlf, new_health.replace("\n", "\r\n"), 1)
        print("[+] Patched bot.py with Anti-Sleep Self-Pinger (CRLF)")
    else:
        print("[!] Warning: old_health pattern not found")

bot_py.write_text(text, encoding="utf-8")
print("[+] Successfully wrote tg_bot/bot.py")
