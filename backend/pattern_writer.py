"""
Pattern Writer — Converts LLM JSON patterns to JSFX-readable text files.

File format (all values are whitespace-separated numbers):
  Line 1: num_events  loop_length_beats  bpm  key_root  type
          type: 0 = melodic (default), 1 = drums
  Lines 2+: beat_pos  note  velocity  duration_beats

(c) 2026 FalconEYE Software Dev
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# GM Percussion note-to-name map (standard General MIDI Level 1)
GM_DRUM_NAMES = {
    35: "Kick 2", 36: "Kick 1", 37: "Side Stick", 38: "Snare",
    39: "Clap", 40: "E.Snare", 41: "Lo Floor Tom", 42: "Closed HH",
    43: "Hi Floor Tom", 44: "Pedal HH", 45: "Low Tom", 46: "Open HH",
    47: "Lo-Mid Tom", 48: "Hi-Mid Tom", 49: "Crash 1", 50: "High Tom",
    51: "Ride 1", 52: "Chinese Cym", 53: "Ride Bell", 54: "Tambourine",
    55: "Splash Cym", 56: "Cowbell", 57: "Crash 2", 58: "Vibraslap",
    59: "Ride 2", 60: "Hi Bongo", 61: "Lo Bongo", 62: "Mute Conga",
    63: "Open Conga", 64: "Lo Conga", 65: "Hi Timbale", 66: "Lo Timbale",
    67: "Hi Agogo", 68: "Lo Agogo", 69: "Cabasa", 70: "Maracas",
    71: "Short Whistle", 72: "Long Whistle", 73: "Short Guiro",
    74: "Long Guiro", 75: "Claves", 76: "Hi Woodblock", 77: "Lo Woodblock",
    78: "Mute Cuica", 79: "Open Cuica", 80: "Mute Triangle", 81: "Open Triangle",
}


def find_reaper_data_path(config_path: str = "auto") -> str:
    """
    Auto-detect or use configured REAPER Data directory.
    JSFX file_open looks in the REAPER resource path's Data subfolder.
    """
    if config_path and config_path.lower() != "auto":
        os.makedirs(config_path, exist_ok=True)
        return config_path

    # Auto-detect: REAPER stores its resource path in the registry or APPDATA
    # Common locations on Windows:
    candidates = []

    # Check APPDATA (most common for portable/standard installs)
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        candidates.append(os.path.join(appdata, "REAPER", "Data"))

    # Check common install locations
    userprofile = os.environ.get("USERPROFILE", "")
    if userprofile:
        candidates.append(os.path.join(userprofile, "Documents", "REAPER", "Data"))

    # Also check for portable installs in Program Files
    progfiles = os.environ.get("PROGRAMFILES", "C:\\Program Files")
    candidates.append(os.path.join(progfiles, "REAPER", "Data"))
    progfiles86 = os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)")
    candidates.append(os.path.join(progfiles86, "REAPER", "Data"))

    for path in candidates:
        parent = os.path.dirname(path)
        if os.path.isdir(parent):
            os.makedirs(path, exist_ok=True)
            logger.info("Auto-detected REAPER Data path: %s", path)
            return path

    # Fallback: create next to the script
    fallback = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reaper_data")
    os.makedirs(fallback, exist_ok=True)
    logger.warning("Could not auto-detect REAPER Data path, using fallback: %s", fallback)
    return fallback


def find_reaper_effects_path() -> Optional[str]:
    """Auto-detect REAPER Effects directory for JSFX installation."""
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        effects_path = os.path.join(appdata, "REAPER", "Effects")
        if os.path.isdir(os.path.dirname(effects_path)):
            os.makedirs(effects_path, exist_ok=True)
            return effects_path
    return None


def write_pattern_file(pattern_data: dict, output_path: str) -> str:
    """
    Write validated pattern data to a JSFX-readable text file.

    Args:
        pattern_data: Validated pattern dict from LLM engine
        output_path: Full path to the output file

    Returns:
        The output file path
    """
    events = pattern_data["events"]
    loop_len = float(pattern_data["loop_length_beats"])
    bpm = float(pattern_data.get("bpm_suggestion", 120))
    key_root = int(pattern_data.get("key_root", 60))
    pattern_type = 0  # default: melodic
    if pattern_data.get("type") == "drums":
        pattern_type = 1
    elif pattern_data.get("type") == "chords":
        pattern_type = 2

    lines = []

    # Header line: num_events  loop_length_beats  bpm  key_root  type
    lines.append(f"{len(events)} {loop_len} {bpm} {key_root} {pattern_type}")

    # Event lines: beat_pos  note  velocity  duration_beats
    for evt in events:
        beat = evt["beat"]
        note = evt["note"]
        vel = evt["velocity"]
        dur = evt["duration"]
        lines.append(f"{beat} {note} {vel} {dur}")

    content = "\n".join(lines) + "\n"

    # Ensure directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    type_label = "drum" if pattern_type == 1 else "melodic"
    logger.info("Pattern written (%s): %d events, %.1f beats → %s",
                type_label, len(events), loop_len, output_path)
    return output_path


def pattern_to_display(pattern_data: dict) -> dict:
    """Convert pattern data to a display-friendly format for the web UI."""
    events = pattern_data.get("events", [])
    is_drums = pattern_data.get("type") == "drums"

    # Note name mapping
    NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

    display_events = []
    for evt in events:
        note_num = evt["note"]
        if is_drums:
            note_name = GM_DRUM_NAMES.get(note_num, f"Perc {note_num}")
        else:
            octave = (note_num // 12) - 1
            note_name = f"{NOTE_NAMES[note_num % 12]}{octave}"
        display_events.append({
            "beat": evt["beat"],
            "note": note_num,
            "note_name": note_name,
            "velocity": evt["velocity"],
            "duration": evt["duration"],
        })

    result = {
        "pattern_name": pattern_data.get("pattern_name", "AI Pattern"),
        "type": pattern_data.get("type", "melodic"),
        "key_root": pattern_data.get("key_root", 60),
        "scale_name": pattern_data.get("scale_name", "chromatic"),
        "time_sig": f"{pattern_data.get('time_signature_num', 4)}/{pattern_data.get('time_signature_den', 4)}",
        "loop_length_beats": pattern_data.get("loop_length_beats", 4),
        "bpm_suggestion": pattern_data.get("bpm_suggestion", 120),
        "num_events": len(events),
        "events": display_events,
    }

    if is_drums:
        result["kit_name"] = pattern_data.get("kit_name", "Standard Kit")

    if pattern_data.get("type") == "chords":
        result["chord_symbols"] = pattern_data.get("chord_symbols", [])

    return result
