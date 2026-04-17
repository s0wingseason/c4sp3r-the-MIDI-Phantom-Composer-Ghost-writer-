"""
Flask Server — FalconEYE AI Arpeggio Generator backend.
Serves the web UI and handles LLM API calls, MIDI preview, and pattern library.

(c) 2026 FalconEYE Software Dev
"""

import json
import logging
import os
import signal
import sys
import threading
import time
import traceback
from datetime import datetime

# Add parent dir to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def resource_path(relative_path: str) -> str:
    """Get absolute path to resource — works for dev and PyInstaller bundle."""
    try:
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    except AttributeError:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from llm_engine import create_provider, create_provider_by_name, get_available_providers
from midi_export import export_midi_file
from midi_preview import get_player
from pattern_library import PatternLibrary
from pattern_writer import (
    GM_DRUM_NAMES,
    find_reaper_data_path,
    find_reaper_effects_path,
    pattern_to_display,
    write_pattern_file,
)

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
# Logging — write to %APPDATA%/FalconEYE/logs/ with timestamped session files
_log_dir = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "FalconEYE", "logs")
os.makedirs(_log_dir, exist_ok=True)
_session_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
_log_file = os.path.join(_log_dir, f"session_{_session_stamp}.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(_log_file, mode="a", encoding="utf-8"),
        logging.StreamHandler(),  # keep console output for debug
    ],
)
logger = logging.getLogger("server")
logger.info("Session log: %s", _log_file)

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
CONFIG_PATH = os.path.join(PROJECT_DIR, "config.json")
STATIC_DIR = resource_path("static")
LIBRARY_DIR = os.path.join(PROJECT_DIR, "pattern_library")

# State — supports multi-result from multi-provider × multi-iteration
generation_status = {
    "status": "idle",
    "message": "",
    "pattern": None,         # currently active result (backward compat)
    "results": [],           # all generated results
    "result_index": 0,       # which result is active
    "total_expected": 1,     # providers × iterations
    "completed": 0,          # how many have finished
    "timestamp": None,
}
generation_lock = threading.Lock()

# Pattern library
library = PatternLibrary(LIBRARY_DIR)

# GM instrument names for the preview dropdown
GM_INSTRUMENTS = [
    "Acoustic Grand Piano", "Bright Acoustic Piano", "Electric Grand Piano",
    "Honky-tonk Piano", "Electric Piano 1", "Electric Piano 2", "Harpsichord",
    "Clavinet", "Celesta", "Glockenspiel", "Music Box", "Vibraphone",
    "Marimba", "Xylophone", "Tubular Bells", "Dulcimer", "Drawbar Organ",
    "Percussive Organ", "Rock Organ", "Church Organ", "Reed Organ",
    "Accordion", "Harmonica", "Tango Accordion", "Nylon Guitar",
    "Steel Guitar", "Jazz Guitar", "Clean Electric Guitar",
    "Muted Electric Guitar", "Overdriven Guitar", "Distortion Guitar",
    "Guitar Harmonics", "Acoustic Bass", "Finger Bass", "Pick Bass",
    "Fretless Bass", "Slap Bass 1", "Slap Bass 2", "Synth Bass 1",
    "Synth Bass 2", "Violin", "Viola", "Cello", "Contrabass",
    "Tremolo Strings", "Pizzicato Strings", "Orchestral Harp", "Timpani",
    "String Ensemble 1", "String Ensemble 2", "Synth Strings 1",
    "Synth Strings 2", "Choir Aahs", "Voice Oohs", "Synth Voice",
    "Orchestra Hit", "Trumpet", "Trombone", "Tuba", "Muted Trumpet",
    "French Horn", "Brass Section", "Synth Brass 1", "Synth Brass 2",
    "Soprano Sax", "Alto Sax", "Tenor Sax", "Baritone Sax", "Oboe",
    "English Horn", "Bassoon", "Clarinet", "Piccolo", "Flute", "Recorder",
    "Pan Flute", "Blown Bottle", "Shakuhachi", "Whistle", "Ocarina",
    "Lead 1 (Square)", "Lead 2 (Sawtooth)", "Lead 3 (Calliope)",
    "Lead 4 (Chiff)", "Lead 5 (Charang)", "Lead 6 (Voice)",
    "Lead 7 (Fifths)", "Lead 8 (Bass+Lead)", "Pad 1 (New Age)",
    "Pad 2 (Warm)", "Pad 3 (Polysynth)", "Pad 4 (Choir)",
    "Pad 5 (Bowed)", "Pad 6 (Metallic)", "Pad 7 (Halo)", "Pad 8 (Sweep)",
    "FX 1 (Rain)", "FX 2 (Soundtrack)", "FX 3 (Crystal)", "FX 4 (Atmosphere)",
    "FX 5 (Brightness)", "FX 6 (Goblins)", "FX 7 (Echoes)", "FX 8 (Sci-fi)",
    "Sitar", "Banjo", "Shamisen", "Koto", "Kalimba", "Bag Pipe", "Fiddle",
    "Shanai", "Tinkle Bell", "Agogo", "Steel Drums", "Woodblock",
    "Taiko Drum", "Melodic Tom", "Synth Drum", "Reverse Cymbal",
    "Guitar Fret Noise", "Breath Noise", "Seashore", "Bird Tweet",
    "Telephone Ring", "Helicopter", "Applause", "Gunshot",
]


def load_config() -> dict:
    """Load config from JSON file."""
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_config(config: dict):
    """Save config to JSON file."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


# ---------------------------------------------------------------------------
# Flask App
# ---------------------------------------------------------------------------
app = Flask(__name__, static_folder=STATIC_DIR)
CORS(app)


@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.route("/static/<path:filename>")
def static_files(filename: str):
    return send_from_directory(STATIC_DIR, filename)


# ---- Status & Config ----

@app.route("/api/status")
def get_status():
    with generation_lock:
        return jsonify(generation_status)


@app.route("/api/logs")
def get_logs():
    """Return the last N lines from the current session log file."""
    n = min(int(request.args.get("lines", 100)), 500)
    try:
        with open(_log_file, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        tail = lines[-n:] if len(lines) > n else lines
        return jsonify({
            "ok": True,
            "log_file": os.path.basename(_log_file),
            "total_lines": len(lines),
            "lines": [l.rstrip() for l in tail],
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "lines": []})

@app.route("/api/config", methods=["GET"])
def get_config():
    config = load_config()
    return jsonify({
        "llm_provider": config.get("llm_provider", "gemini"),
        "gemini_model": config.get("gemini_model", "gemini-2.5-flash"),
        "openai_model": config.get("openai_model", "gpt-4o-mini"),
        "claude_model": config.get("claude_model", "claude-sonnet-4-20250514"),
        "has_gemini_key": bool(config.get("gemini_api_key")),
        "has_openai_key": bool(config.get("openai_api_key")),
        "has_claude_key": bool(config.get("claude_api_key")),
        "default_providers": config.get("default_providers", [config.get("llm_provider", "gemini")]),
        "default_iterations": config.get("default_iterations", 1),
        "server_port": config.get("server_port", 8765),
    })


@app.route("/api/config", methods=["POST"])
def update_config():
    config = load_config()
    data = request.get_json()
    allowed = ["llm_provider", "gemini_api_key", "openai_api_key", "claude_api_key",
               "gemini_model", "openai_model", "claude_model", "reaper_data_path",
               "default_providers", "default_iterations"]
    for key in allowed:
        if key in data:
            config[key] = data[key]
    save_config(config)
    return jsonify({"ok": True})


# ---- Generation ----

@app.route("/api/generate", methods=["POST"])
def generate_pattern():
    with generation_lock:
        if generation_status["status"] == "generating":
            return jsonify({"error": "Generation already in progress"}), 409

    data = request.get_json()
    prompt = data.get("prompt", "").strip()
    if not prompt:
        return jsonify({"error": "Prompt is required"}), 400

    # Generation mode: "melodic" (default), "drums", or "chords"
    mode = data.get("mode", "melodic")
    if mode not in ("melodic", "drums", "chords"):
        mode = "melodic"

    # Build enhanced prompt
    params = []
    if mode == "melodic" or mode == "chords":
        for key, label in [("key", "Key"), ("scale", "Scale"),
                           ("time_sig", "Time signature"), ("bars", "Number of bars"),
                           ("subdivision", "Note subdivision"),
                           ("octave_range", "Octave range"), ("style", "Style/feel")]:
            if data.get(key):
                params.append(f"{label}: {data[key]}")
    else:
        # Drum mode — only relevant params
        for key, label in [("time_sig", "Time signature"), ("bars", "Number of bars"),
                           ("subdivision", "Note subdivision"),
                           ("style", "Style/feel")]:
            if data.get(key):
                params.append(f"{label}: {data[key]}")

    full_prompt = prompt
    if params:
        full_prompt += "\n\nMusical parameters:\n" + "\n".join(f"- {p}" for p in params)

    auto_save = data.get("auto_save", True)
    category = data.get("category", "Uncategorized")

    # Multi-provider + multi-iteration support
    config = load_config()
    providers = data.get("providers", config.get("default_providers",
                         [config.get("llm_provider", "gemini")]))
    iterations = int(data.get("iterations", config.get("default_iterations", 1)))
    iterations = max(1, min(iterations, 10))  # clamp 1–10

    # Validate providers — only use those with valid keys
    valid_providers = []
    for p in providers:
        p = p.lower().strip()
        if p == "gemini" and config.get("gemini_api_key"):
            valid_providers.append(p)
        elif p == "openai" and config.get("openai_api_key"):
            valid_providers.append(p)
        elif p == "claude" and config.get("claude_api_key"):
            valid_providers.append(p)
    if not valid_providers:
        return jsonify({"error": "No valid API keys configured for the selected providers."}), 400

    total = len(valid_providers) * iterations

    with generation_lock:
        generation_status["status"] = "generating"
        generation_status["message"] = "Starting generation..."
        generation_status["pattern"] = None
        generation_status["results"] = []
        generation_status["result_index"] = 0
        generation_status["total_expected"] = total
        generation_status["completed"] = 0
        generation_status["timestamp"] = datetime.now().isoformat()

    thread = threading.Thread(
        target=_generate_worker,
        args=(full_prompt, prompt, auto_save, category, mode,
              valid_providers, iterations),
        daemon=True
    )
    thread.start()

    provider_names = ", ".join(p.capitalize() for p in valid_providers)
    msg = f"Generation started — {total} result(s) via {provider_names}"
    return jsonify({"ok": True, "message": msg, "total_expected": total})


def _generate_worker(full_prompt: str, original_prompt: str,
                     auto_save: bool, category: str, mode: str,
                     providers: list, iterations: int):
    """Generate patterns across multiple providers and iterations."""
    global generation_status
    config = load_config()
    data_path = find_reaper_data_path(config.get("reaper_data_path", "auto"))
    pattern_file = config.get("pattern_file", "AI_Arpeggio_pattern_data.txt")
    output_path = os.path.join(data_path, pattern_file)
    total = len(providers) * iterations
    results = []
    errors = []

    task_num = 0
    for provider_name in providers:
        for iteration in range(1, iterations + 1):
            task_num += 1
            label_parts = []
            if len(providers) > 1:
                label_parts.append(provider_name.capitalize())
            if iterations > 1:
                label_parts.append(f"v{iteration}")
            task_label = " ".join(label_parts) if label_parts else "AI"

            with generation_lock:
                generation_status["message"] = (
                    f"Generating {task_num}/{total} ({task_label})..."
                )

            try:
                provider = create_provider_by_name(provider_name, config)
                pattern_data = provider.generate(full_prompt, mode=mode)

                # Write the latest result as the active REAPER pattern
                write_pattern_file(pattern_data, output_path)

                # Auto-export MIDI
                midi_path = os.path.splitext(output_path)[0] + ".mid"
                try:
                    export_midi_file(pattern_data, midi_path)
                except Exception as me:
                    logger.warning("MIDI export failed (non-fatal): %s", me)

                # Auto-save to library
                saved_entry = None
                if auto_save:
                    saved_entry = library.save_pattern(
                        pattern_data, original_prompt, category
                    )

                display = pattern_to_display(pattern_data)
                display["provider"] = provider_name
                if iterations > 1:
                    display["iteration"] = iteration
                if saved_entry:
                    display["library_id"] = saved_entry["id"]

                results.append(display)
                logger.info(
                    "Pattern generated [%s] via %s (v%d): %s",
                    mode, provider_name, iteration,
                    display.get("pattern_name", "?")
                )

            except Exception as e:
                err_msg = f"{provider_name.capitalize()} v{iteration}: {str(e)}"
                errors.append(err_msg)
                logger.error("Generation failed [%s/%s v%d]: %s\n%s",
                             mode, provider_name, iteration,
                             str(e), traceback.format_exc())

            with generation_lock:
                generation_status["completed"] = task_num
                if results:
                    generation_status["results"] = results
                    generation_status["pattern"] = results[0]
                    generation_status["result_index"] = 0

    # Final status
    with generation_lock:
        if results:
            generation_status["status"] = "done"
            generation_status["results"] = results
            generation_status["result_index"] = 0
            generation_status["pattern"] = results[0]
            count_str = f"{len(results)} result(s)"
            if errors:
                count_str += f" ({len(errors)} failed)"
            generation_status["message"] = (
                f"Done! {count_str} — "
                f"{results[0]['num_events']} events, "
                f"{results[0]['loop_length_beats']} beats"
            )
        else:
            generation_status["status"] = "error"
            generation_status["message"] = "All generations failed: " + "; ".join(errors)
            generation_status["pattern"] = None
            generation_status["results"] = []

        generation_status["timestamp"] = datetime.now().isoformat()


# ---- Results Navigation ----

@app.route("/api/results/navigate", methods=["POST"])
def navigate_results():
    """Navigate between multi-generation results."""
    data = request.get_json()
    with generation_lock:
        results = generation_status.get("results", [])
        if not results:
            return jsonify({"error": "No results available"}), 404

        idx = generation_status.get("result_index", 0)
        direction = data.get("direction", "next")

        if direction == "next":
            idx = (idx + 1) % len(results)
        elif direction == "prev":
            idx = (idx - 1) % len(results)
        elif direction == "index":
            idx = max(0, min(int(data.get("index", 0)), len(results) - 1))

        generation_status["result_index"] = idx
        generation_status["pattern"] = results[idx]

        # Also write this pattern to REAPER
        try:
            config = load_config()
            data_path = find_reaper_data_path(config.get("reaper_data_path", "auto"))
            pattern_file = config.get("pattern_file", "AI_Arpeggio_pattern_data.txt")
            # We need the raw pattern data, but display doesn't have it.
            # The library entry has it — load from library if available.
        except Exception:
            pass

        return jsonify({
            "ok": True,
            "result_index": idx,
            "total_results": len(results),
            "pattern": results[idx],
        })


# ---- Pattern Modification ----

@app.route("/api/modify", methods=["POST"])
def modify_pattern():
    """Modify an existing pattern via LLM."""
    with generation_lock:
        if generation_status["status"] == "generating":
            return jsonify({"error": "Generation already in progress"}), 409

    data = request.get_json()
    original_pattern = data.get("original_pattern")
    modification_prompt = data.get("modification_prompt", "").strip()
    overrides = data.get("overrides", {})
    mode = data.get("mode", original_pattern.get("type", "melodic") if original_pattern else "melodic")

    if not original_pattern:
        return jsonify({"error": "Original pattern is required"}), 400
    if not modification_prompt and not overrides:
        return jsonify({"error": "Provide a modification prompt or overrides"}), 400

    if not modification_prompt:
        modification_prompt = "Apply the following parameter changes."

    auto_save = data.get("auto_save", True)
    category = data.get("category", "Uncategorized")

    with generation_lock:
        generation_status["status"] = "generating"
        generation_status["message"] = "Modifying pattern..."
        generation_status["timestamp"] = datetime.now().isoformat()

    thread = threading.Thread(
        target=_modify_worker,
        args=(original_pattern, modification_prompt, overrides,
              auto_save, category, mode),
        daemon=True
    )
    thread.start()
    return jsonify({"ok": True, "message": "Modification started"})


def _modify_worker(original_pattern: dict, modification_prompt: str,
                   overrides: dict, auto_save: bool, category: str,
                   mode: str = "melodic"):
    """Background worker for pattern modification."""
    global generation_status
    try:
        config = load_config()
        with generation_lock:
            generation_status["message"] = "AI is modifying your pattern..."
        provider = create_provider(config)
        pattern_data = provider.generate_modification(
            original_pattern, modification_prompt, overrides, mode=mode
        )

        with generation_lock:
            generation_status["message"] = "Writing modified pattern to REAPER..."
        data_path = find_reaper_data_path(config.get("reaper_data_path", "auto"))
        pattern_file = config.get("pattern_file", "AI_Arpeggio_pattern_data.txt")
        output_path = os.path.join(data_path, pattern_file)
        write_pattern_file(pattern_data, output_path)

        # Auto-export as .mid
        midi_path = os.path.splitext(output_path)[0] + ".mid"
        try:
            export_midi_file(pattern_data, midi_path)
        except Exception as me:
            logger.warning("MIDI export failed (non-fatal): %s", me)

        saved_entry = None
        if auto_save:
            saved_entry = library.save_pattern(
                pattern_data, f"[Modified] {modification_prompt[:150]}", category
            )

        display = pattern_to_display(pattern_data)
        if saved_entry:
            display["library_id"] = saved_entry["id"]

        with generation_lock:
            generation_status["status"] = "done"
            generation_status["message"] = (
                f"Pattern modified! {display['num_events']} events, "
                f"{display['loop_length_beats']} beats"
            )
            generation_status["pattern"] = display
            generation_status["timestamp"] = datetime.now().isoformat()

        logger.info("Pattern modified: %s", display.get("pattern_name", "?"))

    except Exception as e:
        logger.error("Modification failed: %s\n%s", str(e), traceback.format_exc())
        with generation_lock:
            generation_status["status"] = "error"
            generation_status["message"] = f"Error: {str(e)}"
            generation_status["pattern"] = None
            generation_status["timestamp"] = datetime.now().isoformat()


# ---- Server Shutdown ----

@app.route("/api/shutdown", methods=["POST"])
def shutdown_server():
    """Gracefully shut down the server process."""
    logger.info("Shutdown requested via API")
    func = request.environ.get("werkzeug.server.shutdown")
    if func:
        func()
    else:
        import threading as _t
        _t.Thread(target=lambda: (time.sleep(0.5), os._exit(0)), daemon=True).start()
    return jsonify({"ok": True, "message": "Server shutting down..."})


# ---- MIDI Preview ----

@app.route("/api/preview/play", methods=["POST"])
def preview_play():
    """Play a pattern through the Windows MIDI synth."""
    data = request.get_json()
    pattern = data.get("pattern")
    bpm = float(data.get("bpm", 120))
    program = int(data.get("program", 0))
    loop = bool(data.get("loop", False))

    # If pattern_id provided, load from library
    if not pattern and data.get("pattern_id"):
        lib_data = library.get_pattern(data["pattern_id"])
        if lib_data:
            pattern = lib_data["pattern"]

    # If still no pattern, use the last generated one
    if not pattern:
        with generation_lock:
            if generation_status.get("pattern"):
                # Need the raw pattern data, reconstruct from display
                return jsonify({"error": "Pass pattern data directly"}), 400

    if not pattern:
        return jsonify({"error": "No pattern to preview"}), 400

    player = get_player()
    success = player.play(pattern, bpm=bpm, program=program, loop=loop)
    if success:
        return jsonify({"ok": True, "message": "Playback started"})
    else:
        return jsonify({"error": "Failed to open MIDI device"}), 500


@app.route("/api/preview/stop", methods=["POST"])
def preview_stop():
    """Stop MIDI preview playback."""
    player = get_player()
    player.stop()
    return jsonify({"ok": True})


@app.route("/api/preview/status")
def preview_status():
    """Get preview playback status."""
    player = get_player()
    status = player.get_status()
    return jsonify(status)


@app.route("/api/preview/instruments")
def preview_instruments():
    """Return list of GM instrument names."""
    return jsonify({"instruments": GM_INSTRUMENTS})


@app.route("/api/preview/drumnames")
def preview_drumnames():
    """Return GM percussion note-to-name mapping."""
    return jsonify({"drum_names": {str(k): v for k, v in GM_DRUM_NAMES.items()}})


# ---- Open Folder in Explorer ----

@app.route("/api/open-folder/data", methods=["POST"])
def open_data_folder():
    """Open the REAPER Data folder (where patterns & MIDI files live) in Explorer."""
    import subprocess
    config = load_config()
    data_path = find_reaper_data_path(config.get("reaper_data_path", "auto"))
    try:
        subprocess.Popen(["explorer", os.path.normpath(data_path)])
        return jsonify({"ok": True, "path": data_path})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/open-folder/library", methods=["POST"])
def open_library_folder():
    """Open the pattern library folder in Explorer."""
    import subprocess
    lib_path = library.library_dir
    try:
        subprocess.Popen(["explorer", os.path.normpath(lib_path)])
        return jsonify({"ok": True, "path": lib_path})
    except Exception as e:
        return jsonify({"error": str(e)}), 500



# ---- Pattern Library ----

@app.route("/api/library/list")
def library_list():
    """List saved patterns with optional filtering."""
    category = request.args.get("category")
    favorites = request.args.get("favorites") == "true"
    patterns = library.list_patterns(category=category, favorites_only=favorites)
    return jsonify({"patterns": patterns, "categories": library.get_categories()})


@app.route("/api/library/<pattern_id>")
def library_get(pattern_id: str):
    """Get a specific pattern's full data."""
    data = library.get_pattern(pattern_id)
    if data:
        return jsonify(data)
    return jsonify({"error": "Pattern not found"}), 404


@app.route("/api/library/<pattern_id>/load", methods=["POST"])
def library_load(pattern_id: str):
    """Load a library pattern into REAPER (write to pattern file)."""
    data = library.get_pattern(pattern_id)
    if not data:
        return jsonify({"error": "Pattern not found"}), 404

    config = load_config()
    data_path = find_reaper_data_path(config.get("reaper_data_path", "auto"))
    pattern_file = config.get("pattern_file", "AI_Arpeggio_pattern_data.txt")
    output_path = os.path.join(data_path, pattern_file)
    write_pattern_file(data["pattern"], output_path)

    display = pattern_to_display(data["pattern"])
    display["library_id"] = pattern_id

    with generation_lock:
        generation_status["status"] = "done"
        generation_status["message"] = f"Loaded: {data['meta']['name']}"
        generation_status["pattern"] = display

    return jsonify({"ok": True, "pattern": display})


@app.route("/api/library/<pattern_id>/rename", methods=["POST"])
def library_rename(pattern_id: str):
    data = request.get_json()
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Name is required"}), 400
    if library.rename_pattern(pattern_id, name):
        return jsonify({"ok": True})
    return jsonify({"error": "Pattern not found"}), 404


@app.route("/api/library/<pattern_id>/category", methods=["POST"])
def library_categorize(pattern_id: str):
    data = request.get_json()
    category = data.get("category", "Uncategorized")
    if library.set_category(pattern_id, category):
        return jsonify({"ok": True})
    return jsonify({"error": "Pattern not found"}), 404


@app.route("/api/library/<pattern_id>/favorite", methods=["POST"])
def library_favorite(pattern_id: str):
    result = library.toggle_favorite(pattern_id)
    if result is not None:
        return jsonify({"ok": True, "favorite": result})
    return jsonify({"error": "Pattern not found"}), 404


@app.route("/api/library/<pattern_id>", methods=["DELETE"])
def library_delete(pattern_id: str):
    if library.delete_pattern(pattern_id):
        return jsonify({"ok": True})
    return jsonify({"error": "Pattern not found"}), 404


@app.route("/api/library/categories", methods=["POST"])
def library_add_category():
    data = request.get_json()
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Category name required"}), 400
    library.add_category(name)
    return jsonify({"ok": True, "categories": library.get_categories()})



# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    config = load_config()
    port = config.get("server_port", 8765)

    print("=" * 60)
    print("  FalconEYE AI Arpeggio Generator — Backend Server")
    print("=" * 60)
    print(f"  Web UI:    http://localhost:{port}")
    print(f"  Provider:  {config.get('llm_provider', 'gemini').upper()}")
    print(f"  Config:    {CONFIG_PATH}")
    print(f"  Library:   {LIBRARY_DIR}")
    print("=" * 60)

    data_path = find_reaper_data_path(config.get("reaper_data_path", "auto"))
    effects_path = find_reaper_effects_path()
    print(f"  REAPER Data:    {data_path}")
    if effects_path:
        print(f"  REAPER Effects: {effects_path}")
    print("=" * 60)
    print()

    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
