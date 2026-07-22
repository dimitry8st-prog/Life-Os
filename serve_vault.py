"""Life OS — локальный веб-сервер для vault.

При открытии папки через http:// папки автоматически показывают index.html.

Запуск:  python serve_vault.py
"""

from __future__ import annotations

import http.server
import os
import socket
import socketserver
import sys
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.config import load_config

PORT = 8765


class VaultHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, fmt: str, *args) -> None:
        if str(args[1]) != "404":
            super().log_message(fmt, *args)


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex(("127.0.0.1", port)) == 0


def main() -> int:
    cfg = load_config()
    vault = cfg.vault_path
    if not vault or not vault.is_dir():
        print("Error: vault_path missing in config.yaml")
        return 1

    url = f"http://127.0.0.1:{PORT}/index.html"

    if _port_open(PORT):
        print(f"Already running: {url}")
        webbrowser.open(url)
        return 0

    os.chdir(vault)
    socketserver.TCPServer.allow_reuse_address = True

    print(f"Life OS vault: {vault}")
    print(f"Open: {url}")
    print("Stop: Ctrl+C")

    webbrowser.open(url)

    with socketserver.TCPServer(("127.0.0.1", PORT), VaultHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nСервер остановлен.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
