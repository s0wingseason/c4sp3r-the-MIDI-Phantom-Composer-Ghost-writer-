"""
Desktop Launcher — FalconEYE AI Arpeggio Generator.
Opens the web UI in a standalone native-like window.
Uses flaskwebgui (Chrome/Edge) or falls back to system browser.

(c) 2026 FalconEYE Software Dev
"""

import os
import sys
import logging
from datetime import datetime

# Configure logging to AppData (no console needed for background operation)
_log_dir = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "FalconEYE", "logs")
os.makedirs(_log_dir, exist_ok=True)
_session_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
_log_file = os.path.join(_log_dir, f"session_{_session_stamp}.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(_log_file, mode="a", encoding="utf-8"),
    ],
)
logger = logging.getLogger("launcher")


def resource_path(relative_path: str) -> str:
    """Get absolute path to resource — works for dev and PyInstaller bundle."""
    try:
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    except AttributeError:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


def get_config():
    """Load config.json from project root."""
    import json
    # In bundled mode, config is next to the .exe; in dev, it's in project root
    try:
        config_path = os.path.join(sys._MEIPASS, "..", "config.json")  # type: ignore
    except AttributeError:
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config.json"
        )
    config_path = os.path.normpath(config_path)
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def main():
    """Launch the desktop application."""
    config = get_config()
    port = config.get("server_port", 8765)

    # Import the Flask app
    from server import app

    try:
        # Try flaskwebgui first — renders in a standalone Chrome/Edge window
        from flaskwebgui import FlaskUI
        logger.info("Launching with FlaskUI (standalone window)")
        FlaskUI(
            app=app,
            server="flask",
            port=port,
            width=1300,
            height=850,
        ).run()
    except ImportError:
        try:
            # Fallback: try pywebview
            import webview
            import threading
            from waitress import serve

            def run_server():
                serve(app, host="127.0.0.1", port=port, threads=4)

            server_thread = threading.Thread(target=run_server, daemon=True)
            server_thread.start()

            import time
            import urllib.request
            for _ in range(50):
                try:
                    urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=1)
                    break
                except Exception:
                    time.sleep(0.2)

            window = webview.create_window(
                title="FalconEYE AI Arpeggio Generator",
                url=f"http://127.0.0.1:{port}",
                width=1280, height=820,
                min_size=(900, 600), resizable=True, text_select=True,
            )
            webview.start(debug=False)
        except ImportError:
            # Final fallback: just open in system browser with waitress
            import webbrowser
            logger.info("No GUI library available, opening in browser")
            webbrowser.open(f"http://127.0.0.1:{port}")
            try:
                from waitress import serve
                serve(app, host="127.0.0.1", port=port, threads=4)
            except ImportError:
                app.run(host="127.0.0.1", port=port, debug=False, threaded=True)


if __name__ == "__main__":
    # Ensure we can import sibling modules
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    main()
