from __future__ import annotations

import argparse
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

# Add src/ to path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir / "src"))

from observability.server import run_server


def find_free_port(start_port: int = 8501, max_tries: int = 20) -> int:
    for port in range(start_port, start_port + max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("localhost", port)) != 0:
                return port
    return start_port


def main() -> None:
    parser = argparse.ArgumentParser(description="Khởi chạy Data Observability & Drift Monitor Web Dashboard")
    parser.add_argument("--port", type=int, default=8501, help="Cổng chạy server (mặc định 8501)")
    parser.add_argument("--no-browser", action="store_true", help="Không tự động mở trình duyệt")
    args = parser.parse_args()

    port = find_free_port(args.port)
    url = f"http://localhost:{port}"

    print("=" * 65)
    print(">>> KHỞI CHẠY INTERACTIVE OBSERVABILITY & DRIFT MONITOR DASHBOARD")
    print("=" * 65)
    print(f"  -> Server URL: {url}")
    print("  -> Tính năng: Giám sát Data Quality, Freshness SLA, Age Distribution, Data Drift")
    print("  -> Nhấn Ctrl+C để dừng server.\n")

    if not args.no_browser:
        def open_browser():
            time.sleep(1.0)
            webbrowser.open(url)
        threading.Thread(target=open_browser, daemon=True).start()

    run_server(port=port)


if __name__ == "__main__":
    main()
