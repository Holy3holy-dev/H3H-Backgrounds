from pathlib import Path

p = Path("tg_bot/bot.py")
text = p.read_text(encoding="utf-8")
is_crlf = "\r\n" in text
if is_crlf:
    text = text.replace("\r\n", "\n")

health_code = """
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(b'<h1>H3H Backgrounds Telegram Bot is Live!</h1>')

    def log_message(self, format, *args):
        pass

def start_health_server():
    import os
    port = int(os.getenv('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    print(f'[*] Health check server listening on 0.0.0.0:{port}')
    server.serve_forever()

threading.Thread(target=start_health_server, daemon=True).start()
"""

target = "bot = telebot.TeleBot(BOT_TOKEN, parse_mode=\"HTML\")"

if "start_health_server" not in text and target in text:
    text = text.replace(target, target + "\n" + health_code)
    if is_crlf:
        text = text.replace("\n", "\r\n")
    p.write_text(text, encoding="utf-8")
    print("[+] Successfully added health server to bot.py!")
else:
    print("[-] Already present or target not found.")
