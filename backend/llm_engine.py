"""
LLM Engine — Abstraction layer for AI pattern generation.
Supports Google Gemini (free tier, default) and OpenAI as fallback.
Uses direct REST API calls to minimize dependencies.
Supports both melodic arpeggio and drum loop generation modes.

(c) 2026 s0wingseason / Calvin D. Roberts
"""

import json
import logging
import re
import urllib.request
import urllib.error
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompts — Melodic Arpeggio mode
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are a professional music composer and MIDI programmer. The user will describe a musical arpeggio or MIDI pattern they want. You must generate a precise MIDI pattern as a JSON object.

RULES:
1. Return ONLY valid JSON, no markdown, no explanation, no code fences.
2. Use standard MIDI note numbers (C4 = 60, middle C).
3. All timing is in beats (quarter notes). Beat 0 = start of pattern.
4. Respect the requested key, scale, time signature, and feel.
5. Make musically interesting patterns — not just ascending/descending scales. Use inversions, skips, rhythmic variation, ghost notes (low velocity), and musical phrasing.
6. Velocities should be expressive (accent patterns, dynamics), ranging 40-127.
7. Duration values should create the requested articulation (legato = longer, staccato = shorter).

OUTPUT FORMAT (strict JSON):
{
  "pattern_name": "descriptive name",
  "type": "melodic",
  "key_root": <MIDI note number of root, e.g. 60 for C4>,
  "scale_name": "e.g. minor pentatonic",
  "time_signature_num": 4,
  "time_signature_den": 4,
  "loop_length_beats": <total beats in the loop>,
  "bpm_suggestion": <suggested BPM>,
  "events": [
    {"beat": 0.0, "note": 60, "velocity": 100, "duration": 0.25},
    {"beat": 0.25, "note": 64, "velocity": 90, "duration": 0.25}
  ]
}

IMPORTANT:
- "beat" = position in beats from start (0-indexed, float)
- "note" = MIDI note number (0-127)
- "velocity" = MIDI velocity (1-127)
- "duration" = note length in beats (float)
- Events MUST be sorted by beat position
- All events must fit within loop_length_beats
- Minimum 4 events
- Generate enough events to fill the ENTIRE requested loop_length_beats — do NOT truncate early
- For longer loops (16+ bars), scale event count accordingly — a 32-bar pattern needs many more events than a 4-bar pattern
- For longer loops, use musical variation (don't just repeat the same 4 bars)"""

MODIFY_SYSTEM_PROMPT = """You are a professional music composer and MIDI programmer. You will receive an existing MIDI pattern as JSON, along with modification instructions from the user.

Your task is to modify the existing pattern according to the user's instructions while PRESERVING the overall character, style, and musical identity of the original.

RULES:
1. Return ONLY valid JSON, no markdown, no explanation, no code fences.
2. Keep the same JSON structure as the original pattern.
3. Preserve elements the user did NOT ask to change (e.g. if they only want to change BPM, keep the notes/rhythm the same).
4. If the user changes key or scale, transpose the notes intelligently — maintain intervals and musical relationships.
5. If the user changes length (bars), extend or trim the pattern musically — don't just cut or repeat mechanically.
6. If the user asks for stylistic changes ("add ghost notes", "make it darker"), apply those musically while keeping the core identity.
7. Velocities should remain expressive (40-127 range).
8. All events must fit within the new loop_length_beats.
9. Events MUST be sorted by beat position.

OUTPUT FORMAT (same as original):
{
  "pattern_name": "descriptive name reflecting the modification",
  "type": "melodic",
  "key_root": <MIDI note number>,
  "scale_name": "scale name",
  "time_signature_num": 4,
  "time_signature_den": 4,
  "loop_length_beats": <total beats>,
  "bpm_suggestion": <BPM>,
  "events": [
    {"beat": 0.0, "note": 60, "velocity": 100, "duration": 0.25}
  ]
}"""

# ---------------------------------------------------------------------------
# System prompts — Drum Loop mode
# ---------------------------------------------------------------------------
DRUM_SYSTEM_PROMPT = """You are a professional drummer and MIDI programmer. The user will describe a drum pattern or beat they want. You must generate a precise MIDI drum pattern as a JSON object using standard General MIDI percussion note mapping.

GM PERCUSSION NOTE MAP (use ONLY these note numbers):
  35 = Acoustic Bass Drum    36 = Bass Drum 1          37 = Side Stick
  38 = Acoustic Snare        39 = Hand Clap            40 = Electric Snare
  41 = Low Floor Tom         42 = Closed Hi-Hat        43 = High Floor Tom
  44 = Pedal Hi-Hat          45 = Low Tom              46 = Open Hi-Hat
  47 = Low-Mid Tom           48 = Hi-Mid Tom           49 = Crash Cymbal 1
  50 = High Tom              51 = Ride Cymbal 1        52 = Chinese Cymbal
  53 = Ride Bell             54 = Tambourine           55 = Splash Cymbal
  56 = Cowbell               57 = Crash Cymbal 2       58 = Vibraslap
  59 = Ride Cymbal 2         69 = Cabasa               70 = Maracas
  75 = Claves                76 = Hi Wood Block        77 = Low Wood Block

RULES:
1. Return ONLY valid JSON, no markdown, no explanation, no code fences.
2. Use ONLY the GM percussion note numbers listed above.
3. All timing is in beats (quarter notes). Beat 0 = start of pattern.
4. Create realistic, groovy drum patterns with proper kick/snare/hi-hat interplay.
5. Use velocity variation for dynamics — ghost notes (40-60), normal hits (80-110), accents (115-127).
6. Hi-hats should have variable velocity for a human feel.
7. Use appropriate durations: kicks ~0.25, snares ~0.25, hi-hats ~0.125, crashes ~0.5-1.0.
8. IMPORTANT: Drums can overlap — multiple drum hits on the same beat are normal and expected (e.g. kick + hi-hat together).

OUTPUT FORMAT (strict JSON):
{
  "pattern_name": "descriptive name",
  "type": "drums",
  "kit_name": "e.g. Standard Kit, 808, Brush Kit",
  "time_signature_num": 4,
  "time_signature_den": 4,
  "loop_length_beats": <total beats in the loop>,
  "bpm_suggestion": <suggested BPM>,
  "events": [
    {"beat": 0.0, "note": 36, "velocity": 110, "duration": 0.25},
    {"beat": 0.0, "note": 42, "velocity": 90, "duration": 0.125},
    {"beat": 0.5, "note": 42, "velocity": 70, "duration": 0.125},
    {"beat": 1.0, "note": 38, "velocity": 120, "duration": 0.25}
  ]
}

IMPORTANT:
- "beat" = position in beats from start (0-indexed, float)
- "note" = GM percussion MIDI note (35-81 ONLY)
- "velocity" = MIDI velocity (1-127)
- "duration" = note length in beats (float)
- Events MUST be sorted by beat position
- All events must fit within loop_length_beats
- Minimum 4 events — generate enough events to fill the ENTIRE requested loop_length_beats
- For longer loops (16+ bars), scale your event count proportionally — a 32-bar drum loop needs 200-400+ events
- Multiple simultaneous hits are encouraged (kick+hat, snare+crash, etc.)
- Think like a real drummer — consistent kick/snare backbone with hi-hat pattern on top
- Do NOT truncate the pattern early — every bar should have drum activity"""

DRUM_MODIFY_SYSTEM_PROMPT = """You are a professional drummer and MIDI programmer. You will receive an existing drum pattern as JSON, along with modification instructions from the user.

Your task is to modify the existing drum pattern according to the user's instructions while PRESERVING the groove and feel of the original.

GM PERCUSSION NOTE MAP (use ONLY these note numbers):
  35 = Acoustic Bass Drum    36 = Bass Drum 1          37 = Side Stick
  38 = Acoustic Snare        39 = Hand Clap            40 = Electric Snare
  41 = Low Floor Tom         42 = Closed Hi-Hat        43 = High Floor Tom
  44 = Pedal Hi-Hat          45 = Low Tom              46 = Open Hi-Hat
  47 = Low-Mid Tom           48 = Hi-Mid Tom           49 = Crash Cymbal 1
  50 = High Tom              51 = Ride Cymbal 1        52 = Chinese Cymbal
  53 = Ride Bell             54 = Tambourine           55 = Splash Cymbal
  56 = Cowbell               57 = Crash Cymbal 2

RULES:
1. Return ONLY valid JSON, no markdown, no explanation, no code fences.
2. Keep the same JSON structure as the original pattern.
3. Preserve elements the user did NOT ask to change.
4. If adding fills, use toms (41, 43, 45, 47, 48, 50) leading into a crash (49).
5. If asked to simplify, reduce ghost notes and toms but keep the kick/snare backbone.
6. Velocities should remain dynamic (40-127 range) with human-like variation.
7. All events must fit within loop_length_beats.
8. Events MUST be sorted by beat position.
9. Keep "type": "drums" in the output.

OUTPUT FORMAT (same as original):
{
  "pattern_name": "descriptive name reflecting the modification",
  "type": "drums",
  "kit_name": "kit name",
  "time_signature_num": 4,
  "time_signature_den": 4,
  "loop_length_beats": <total beats>,
  "bpm_suggestion": <BPM>,
  "events": [
    {"beat": 0.0, "note": 36, "velocity": 110, "duration": 0.25}
  ]
}"""


def _repair_truncated_json(text: str) -> dict:
    """
    Attempt to repair truncated JSON from LLM responses.
    Common case: the events array is cut off mid-entry.
    Strategy: close any open structures and parse what we have.
    """
    # Remove any trailing incomplete event entry (partial object)
    # Look for the last complete event object
    last_complete = text.rfind('}')
    if last_complete == -1:
        raise ValueError("No complete JSON object found")

    # Try progressively closing the JSON
    truncated = text[:last_complete + 1]

    # Count open brackets/braces to determine what needs closing
    closers_needed = []
    in_string = False
    escape_next = False
    for ch in truncated:
        if escape_next:
            escape_next = False
            continue
        if ch == '\\':
            escape_next = True
            continue
        if ch == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '{':
            closers_needed.append('}')
        elif ch == '[':
            closers_needed.append(']')
        elif ch == '}' and closers_needed and closers_needed[-1] == '}':
            closers_needed.pop()
        elif ch == ']' and closers_needed and closers_needed[-1] == ']':
            closers_needed.pop()

    # Close any remaining open structures
    repaired = truncated + ''.join(reversed(closers_needed))

    try:
        data = json.loads(repaired)
        logger.warning("Repaired truncated JSON (closed %d brackets)", len(closers_needed))
        return data
    except json.JSONDecodeError:
        pass

    # More aggressive: find the events array and close it
    events_match = re.search(r'"events"\s*:\s*\[', text)
    if events_match:
        # Find all complete event objects {...}
        events_start = events_match.end()
        complete_events = []
        for m in re.finditer(r'\{[^{}]+\}', text[events_start:]):
            try:
                obj = json.loads(m.group())
                if 'beat' in obj and 'note' in obj:
                    complete_events.append(obj)
            except json.JSONDecodeError:
                continue

        if complete_events:
            # Extract header fields from the beginning of the JSON
            header = text[:events_match.start()]
            # Try to build a valid JSON with just header + events
            repaired = header + '"events": ' + json.dumps(complete_events) + '}'
            try:
                data = json.loads(repaired)
                logger.warning("Reconstructed JSON with %d recovered events", len(complete_events))
                return data
            except json.JSONDecodeError:
                pass

    raise ValueError("Could not repair truncated JSON")


def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response, handling markdown code fences and truncation."""
    # Strip code fences if present
    text = text.strip()
    if text.startswith("```"):
        # Remove opening fence (```json or ```)
        text = re.sub(r'^```\w*\n?', '', text)
        # Remove closing fence
        text = re.sub(r'\n?```$', '', text)
        text = text.strip()

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object in the text
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Try to repair truncated JSON (common with large patterns)
    try:
        return _repair_truncated_json(text)
    except (ValueError, json.JSONDecodeError):
        pass

    raise ValueError(f"Could not extract valid JSON from LLM response:\n{text[:500]}")


def _validate_pattern(data: dict) -> dict:
    """Validate and sanitize a melodic pattern from LLM."""
    required = ["events", "loop_length_beats"]
    for key in required:
        if key not in data:
            raise ValueError(f"Missing required field: {key}")

    events = data["events"]
    if not isinstance(events, list) or len(events) < 1:
        raise ValueError("Events list is empty or invalid")

    loop_len = float(data["loop_length_beats"])
    if loop_len <= 0:
        raise ValueError("loop_length_beats must be positive")

    # Sanitize events
    clean_events = []
    for evt in events:
        beat = float(evt.get("beat", 0))
        note = int(evt.get("note", 60))
        vel = int(evt.get("velocity", 100))
        dur = float(evt.get("duration", 0.25))

        # Clamp values
        note = max(0, min(127, note))
        vel = max(1, min(127, vel))
        dur = max(0.01, min(loop_len, dur))
        beat = max(0, min(loop_len - 0.01, beat))

        clean_events.append({
            "beat": round(beat, 4),
            "note": note,
            "velocity": vel,
            "duration": round(dur, 4)
        })

    # Sort by beat position
    clean_events.sort(key=lambda e: e["beat"])

    data["events"] = clean_events
    data["loop_length_beats"] = loop_len
    data.setdefault("type", "melodic")
    data.setdefault("key_root", 60)
    data.setdefault("scale_name", "chromatic")
    data.setdefault("pattern_name", "AI Pattern")
    data.setdefault("bpm_suggestion", 120)
    data.setdefault("time_signature_num", 4)
    data.setdefault("time_signature_den", 4)

    return data


def _validate_drum_pattern(data: dict) -> dict:
    """Validate and sanitize a drum pattern from LLM."""
    required = ["events", "loop_length_beats"]
    for key in required:
        if key not in data:
            raise ValueError(f"Missing required field: {key}")

    events = data["events"]
    if not isinstance(events, list) or len(events) < 1:
        raise ValueError("Events list is empty or invalid")

    loop_len = float(data["loop_length_beats"])
    if loop_len <= 0:
        raise ValueError("loop_length_beats must be positive")

    # Valid GM percussion note range
    GM_DRUM_MIN = 35
    GM_DRUM_MAX = 81

    # Sanitize events
    clean_events = []
    for evt in events:
        beat = float(evt.get("beat", 0))
        note = int(evt.get("note", 36))
        vel = int(evt.get("velocity", 100))
        dur = float(evt.get("duration", 0.25))

        # Clamp to GM drum range
        note = max(GM_DRUM_MIN, min(GM_DRUM_MAX, note))
        vel = max(1, min(127, vel))
        dur = max(0.01, min(loop_len, dur))
        beat = max(0, min(loop_len - 0.01, beat))

        clean_events.append({
            "beat": round(beat, 4),
            "note": note,
            "velocity": vel,
            "duration": round(dur, 4)
        })

    # Sort by beat position, then note (for consistent ordering of simultaneous hits)
    clean_events.sort(key=lambda e: (e["beat"], e["note"]))

    data["events"] = clean_events
    data["loop_length_beats"] = loop_len
    data["type"] = "drums"
    data.setdefault("kit_name", "Standard Kit")
    data.setdefault("pattern_name", "AI Drum Pattern")
    data.setdefault("bpm_suggestion", 120)
    data.setdefault("time_signature_num", 4)
    data.setdefault("time_signature_den", 4)
    # Drums don't use key_root/scale_name but we keep them for format compat
    data.setdefault("key_root", 0)
    data.setdefault("scale_name", "percussion")

    return data


# ---------------------------------------------------------------------------
# System prompts — Chord Progression mode
# ---------------------------------------------------------------------------
CHORD_SYSTEM_PROMPT = """You are a professional music composer and MIDI programmer. The user will describe a chord progression they want. You must generate a precise MIDI chord pattern as a JSON object.

RULES:
1. Return ONLY valid JSON, no markdown, no explanation, no code fences.
2. Use standard MIDI note numbers (C4 = 60, middle C).
3. All timing is in beats (quarter notes). Beat 0 = start of pattern.
4. Each chord should have 3-6 simultaneous notes (triads, 7ths, extensions).
5. Multiple notes at the same beat position form a chord.
6. Use appropriate voicings — avoid overly wide spreads for realistic playing.
7. Velocities should be consistent within chords, with slight accent on roots.
8. Use inversions and voice leading to create smooth transitions between chords.
9. Duration of chord notes should typically be 1-4 beats depending on style.

OUTPUT FORMAT (strict JSON):
{
  "pattern_name": "descriptive name",
  "type": "chords",
  "key_root": <MIDI note number of root, e.g. 60 for C4>,
  "scale_name": "e.g. major",
  "chord_symbols": ["Cmaj7", "Am7", "Dm7", "G7"],
  "time_signature_num": 4,
  "time_signature_den": 4,
  "loop_length_beats": <total beats in the loop>,
  "bpm_suggestion": <suggested BPM>,
  "events": [
    {"beat": 0.0, "note": 60, "velocity": 95, "duration": 4.0},
    {"beat": 0.0, "note": 64, "velocity": 88, "duration": 4.0},
    {"beat": 0.0, "note": 67, "velocity": 85, "duration": 4.0},
    {"beat": 0.0, "note": 71, "velocity": 82, "duration": 4.0}
  ]
}

IMPORTANT:
- Multiple notes at the same "beat" position form a chord
- Use proper voice leading between chords (minimal movement between voices)
- Include chord extensions (7ths, 9ths, 11ths) when the style calls for it
- Minimum 8 events (2+ chords) — generate enough events to fill the ENTIRE requested loop_length_beats
- For longer progressions (16+ bars), scale event count accordingly
- Events MUST be sorted by beat position
- All events must fit within loop_length_beats"""

CHORD_MODIFY_SYSTEM_PROMPT = """You are a professional music composer and MIDI programmer. You will receive an existing chord progression pattern as JSON, along with modification instructions from the user.

Your task is to modify the existing chord progression according to the user's instructions while PRESERVING the harmonic identity and voice leading.

RULES:
1. Return ONLY valid JSON, no markdown, no explanation, no code fences.
2. Keep the same JSON structure as the original pattern.
3. Preserve elements the user did NOT ask to change.
4. If transposing, maintain all intervals and chord qualities.
5. If adding extensions, use musically appropriate chord tones.
6. If changing style (e.g. "make it jazzier"), add 7ths/9ths/13ths appropriately.
7. Update the chord_symbols array to reflect changes.
8. Velocities should remain consistent within chords.
9. Keep "type": "chords" in the output.
10. Events MUST be sorted by beat position.

OUTPUT FORMAT (same as original):
{
  "pattern_name": "descriptive name reflecting modification",
  "type": "chords",
  "key_root": <MIDI note>,
  "scale_name": "scale name",
  "chord_symbols": ["chord1", "chord2"],
  "time_signature_num": 4,
  "time_signature_den": 4,
  "loop_length_beats": <total beats>,
  "bpm_suggestion": <BPM>,
  "events": [...]
}"""


def _validate_chord_pattern(data: dict) -> dict:
    """Validate and sanitize a chord pattern from LLM."""
    required = ["events", "loop_length_beats"]
    for key in required:
        if key not in data:
            raise ValueError(f"Missing required field: {key}")

    events = data["events"]
    if not isinstance(events, list) or len(events) < 1:
        raise ValueError("Events list is empty or invalid")

    loop_len = float(data["loop_length_beats"])
    if loop_len <= 0:
        raise ValueError("loop_length_beats must be positive")

    clean_events = []
    for evt in events:
        beat = float(evt.get("beat", 0))
        note = int(evt.get("note", 60))
        vel = int(evt.get("velocity", 90))
        dur = float(evt.get("duration", 1.0))

        note = max(0, min(127, note))
        vel = max(1, min(127, vel))
        dur = max(0.01, min(loop_len, dur))
        beat = max(0, min(loop_len - 0.01, beat))

        clean_events.append({
            "beat": round(beat, 4),
            "note": note,
            "velocity": vel,
            "duration": round(dur, 4)
        })

    clean_events.sort(key=lambda e: (e["beat"], e["note"]))

    data["events"] = clean_events
    data["loop_length_beats"] = loop_len
    data["type"] = "chords"
    data.setdefault("key_root", 60)
    data.setdefault("scale_name", "major")
    data.setdefault("chord_symbols", [])
    data.setdefault("pattern_name", "AI Chord Progression")
    data.setdefault("bpm_suggestion", 120)
    data.setdefault("time_signature_num", 4)
    data.setdefault("time_signature_den", 4)

    return data


# ---------------------------------------------------------------------------
# System prompts — Full Arrangement mode
# ---------------------------------------------------------------------------
ARRANGEMENT_SYSTEM_PROMPT = """You are a professional music producer and MIDI programmer. The user will describe a musical style or concept. You must generate a COMPLETE multi-track arrangement as a single JSON object containing coordinated Drums, Bass, Chords, and Melody patterns that work together musically.

RULES:
1. Return ONLY valid JSON, no markdown, no explanation, no code fences.
2. Generate 4 coordinated tracks that form a cohesive musical arrangement.
3. All tracks share the same key, tempo, time signature, and loop length.
4. Use standard MIDI note numbers (C4 = 60).
5. Drums use GM percussion mapping (channel 10): Kick=36, Snare=38, HH=42/46, Ride=51, Crash=49.
6. Bass should be monophonic in octaves 2-3 (MIDI notes 36-59), rhythmically locked to the kick drum.
7. Chords should use proper voice leading with 3-5 notes per chord, octaves 4-5.
8. Melody should be a singable lead line in octaves 4-5, with rhythmic variety and phrasing.
9. Tracks should complementary — melody plays during chord sustained sections, bass locks with kick.
10. Use velocity dynamics: ghost notes (40-60), normal (80-110), accents (115-127).
11. Keep it musical — this should sound like a real song section, not random notes.

OUTPUT FORMAT (strict JSON):
{
  "arrangement_name": "descriptive name",
  "key_root": 60,
  "scale_name": "minor",
  "time_signature_num": 4,
  "time_signature_den": 4,
  "loop_length_beats": 16,
  "bpm_suggestion": 120,
  "tracks": {
    "drums": {
      "pattern_name": "drum track name",
      "type": "drums",
      "kit_name": "Standard Kit",
      "events": [
        {"beat": 0.0, "note": 36, "velocity": 110, "duration": 0.25}
      ]
    },
    "bass": {
      "pattern_name": "bass track name",
      "type": "melodic",
      "events": [
        {"beat": 0.0, "note": 36, "velocity": 100, "duration": 0.5}
      ]
    },
    "chords": {
      "pattern_name": "chord track name",
      "type": "chords",
      "chord_symbols": ["Am", "F", "C", "G"],
      "events": [
        {"beat": 0.0, "note": 57, "velocity": 85, "duration": 4.0}
      ]
    },
    "melody": {
      "pattern_name": "melody track name",
      "type": "melodic",
      "events": [
        {"beat": 0.0, "note": 72, "velocity": 95, "duration": 0.5}
      ]
    }
  }
}

IMPORTANT:
- All events must fit within loop_length_beats
- Events within each track MUST be sorted by beat position
- Drums: use simultaneous hits (kick+hat, snare+crash)
- Bass: keep monophonic — one note at a time, rhythmically interesting
- Chords: multiple simultaneous notes form chords, use smooth voice leading
- Melody: singable line with musical phrasing (not just scale runs)
- Generate enough events per track to fill the entire loop
- For 4-bar patterns (16 beats): drums ~30-60 events, bass ~12-24, chords ~12-20, melody ~16-32"""

ARRANGEMENT_MODIFY_SYSTEM_PROMPT = """You are a professional music producer and MIDI programmer. You will receive an existing multi-track arrangement as JSON, along with modification instructions from the user.

Your task is to modify the arrangement while PRESERVING the musical cohesion between tracks.

RULES:
1. Return ONLY valid JSON, no markdown, no explanation, no code fences.
2. Keep the same JSON structure with "tracks" containing drums, bass, chords, melody.
3. If the user changes one track, ensure other tracks still complement it.
4. If transposing, transpose bass, chords, and melody together (not drums).
5. If changing style, adjust ALL tracks to match the new feel.
6. Keep all shared parameters (key, tempo, time sig, loop length) consistent.
7. Events MUST be sorted by beat position within each track.

OUTPUT FORMAT: Same as the original arrangement JSON structure."""


def _validate_arrangement(data: dict) -> dict:
    """Validate and sanitize a multi-track arrangement from LLM."""
    if "tracks" not in data:
        raise ValueError("Missing 'tracks' in arrangement")

    tracks = data["tracks"]
    if not isinstance(tracks, dict):
        raise ValueError("'tracks' must be a dict")

    loop_len = float(data.get("loop_length_beats", 16))
    if loop_len <= 0:
        raise ValueError("loop_length_beats must be positive")

    # Shared metadata
    key_root = int(data.get("key_root", 60))
    bpm = float(data.get("bpm_suggestion", 120))
    time_num = int(data.get("time_signature_num", 4))
    time_den = int(data.get("time_signature_den", 4))
    scale_name = data.get("scale_name", "minor")

    validated_tracks = {}
    for track_name in ["drums", "bass", "chords", "melody"]:
        if track_name not in tracks:
            continue  # optional tracks
        track = tracks[track_name]
        events = track.get("events", [])
        if not isinstance(events, list):
            continue

        clean_events = []
        for evt in events:
            beat = float(evt.get("beat", 0))
            note = int(evt.get("note", 60))
            vel = int(evt.get("velocity", 100))
            dur = float(evt.get("duration", 0.25))

            note = max(0, min(127, note))
            vel = max(1, min(127, vel))
            dur = max(0.01, min(loop_len, dur))
            beat = max(0, min(loop_len - 0.01, beat))

            clean_events.append({
                "beat": round(beat, 4),
                "note": note,
                "velocity": vel,
                "duration": round(dur, 4)
            })

        if track_name == "drums":
            clean_events.sort(key=lambda e: (e["beat"], e["note"]))
        else:
            clean_events.sort(key=lambda e: (e["beat"], e["note"]))

        # Build individual pattern dict
        pattern = {
            "pattern_name": track.get("pattern_name", f"AI {track_name.title()}"),
            "type": track.get("type", "drums" if track_name == "drums" else "melodic"),
            "key_root": key_root,
            "scale_name": scale_name if track_name != "drums" else "percussion",
            "time_signature_num": time_num,
            "time_signature_den": time_den,
            "loop_length_beats": loop_len,
            "bpm_suggestion": bpm,
            "events": clean_events,
        }
        if track_name == "drums":
            pattern["kit_name"] = track.get("kit_name", "Standard Kit")
        if track_name == "chords":
            pattern["chord_symbols"] = track.get("chord_symbols", [])
            pattern["type"] = "chords"

        validated_tracks[track_name] = pattern

    if not validated_tracks:
        raise ValueError("No valid tracks in arrangement")

    data["tracks"] = validated_tracks
    data["loop_length_beats"] = loop_len
    data["key_root"] = key_root
    data["bpm_suggestion"] = bpm
    data["scale_name"] = scale_name
    data.setdefault("arrangement_name", "AI Arrangement")
    data.setdefault("time_signature_num", time_num)
    data.setdefault("time_signature_den", time_den)
    data["type"] = "arrangement"

    return data


def _get_prompts(mode: str = "melodic"):
    """Return the appropriate system prompts for the given mode."""
    if mode == "drums":
        return DRUM_SYSTEM_PROMPT, DRUM_MODIFY_SYSTEM_PROMPT
    if mode == "chords":
        return CHORD_SYSTEM_PROMPT, CHORD_MODIFY_SYSTEM_PROMPT
    if mode == "arrangement":
        return ARRANGEMENT_SYSTEM_PROMPT, ARRANGEMENT_MODIFY_SYSTEM_PROMPT
    return SYSTEM_PROMPT, MODIFY_SYSTEM_PROMPT


def _get_validator(mode: str = "melodic"):
    """Return the appropriate validator for the given mode."""
    if mode == "drums":
        return _validate_drum_pattern
    if mode == "chords":
        return _validate_chord_pattern
    if mode == "arrangement":
        return _validate_arrangement
    return _validate_pattern


class GeminiProvider:
    """Google Gemini API provider (REST, free tier compatible)."""

    API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        self.api_key = api_key
        self.model = model

    def generate(self, user_prompt: str, mode: str = "melodic") -> dict:
        """Send prompt to Gemini and return parsed pattern JSON."""
        sys_prompt, _ = _get_prompts(mode)
        validate = _get_validator(mode)

        url = f"{self.API_URL.format(model=self.model)}?key={self.api_key}"

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": sys_prompt + "\n\nUSER REQUEST:\n" + user_prompt}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.8,
                "topP": 0.95,
                "maxOutputTokens": 16384,
                "responseMimeType": "application/json"
            }
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            logger.error("Gemini API HTTP %d: %s", e.code, body[:500])
            raise RuntimeError(f"Gemini API error ({e.code}): {body[:200]}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Network error: {e.reason}")

        # Extract text from Gemini response
        try:
            text = result["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as e:
            logger.error("Unexpected Gemini response: %s", json.dumps(result)[:500])
            raise RuntimeError(f"Unexpected Gemini response format: {e}")

        pattern = _extract_json(text)
        return validate(pattern)

    def generate_modification(self, original_pattern: dict,
                              modification_prompt: str,
                              overrides: dict = None,
                              mode: str = "melodic") -> dict:
        """Modify an existing pattern via LLM."""
        _, mod_prompt = _get_prompts(mode)
        validate = _get_validator(mode)

        # Build the modification request
        override_lines = []
        if overrides:
            for key, val in overrides.items():
                if val:
                    override_lines.append(f"- {key}: {val}")

        user_msg = f"""EXISTING PATTERN:
{json.dumps(original_pattern, indent=2)}

MODIFICATION REQUEST:
{modification_prompt}"""
        if override_lines:
            user_msg += "\n\nHARD OVERRIDES (must apply these exactly):\n" + "\n".join(override_lines)

        url = f"{self.API_URL.format(model=self.model)}?key={self.api_key}"
        payload = {
            "contents": [{
                "parts": [{"text": mod_prompt + "\n\n" + user_msg}]
            }],
            "generationConfig": {
                "temperature": 0.7,
                "topP": 0.9,
                "maxOutputTokens": 16384,
                "responseMimeType": "application/json"
            }
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Gemini API error ({e.code}): {body[:200]}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Network error: {e.reason}")

        try:
            text = result["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Unexpected Gemini response format: {e}")

        pattern = _extract_json(text)
        return validate(pattern)


class OpenAIProvider:
    """OpenAI API provider (fallback)."""

    API_URL = "https://api.openai.com/v1/chat/completions"

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model = model

    def generate(self, user_prompt: str, mode: str = "melodic") -> dict:
        """Send prompt to OpenAI and return parsed pattern JSON."""
        sys_prompt, _ = _get_prompts(mode)
        validate = _get_validator(mode)

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.8,
            "max_tokens": 16384,
            "response_format": {"type": "json_object"}
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.API_URL,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            },
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            logger.error("OpenAI API HTTP %d: %s", e.code, body[:500])
            raise RuntimeError(f"OpenAI API error ({e.code}): {body[:200]}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Network error: {e.reason}")

        try:
            text = result["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Unexpected OpenAI response format: {e}")

        pattern = _extract_json(text)
        return validate(pattern)

    def generate_modification(self, original_pattern: dict,
                              modification_prompt: str,
                              overrides: dict = None,
                              mode: str = "melodic") -> dict:
        """Modify an existing pattern via LLM."""
        _, mod_prompt = _get_prompts(mode)
        validate = _get_validator(mode)

        override_lines = []
        if overrides:
            for key, val in overrides.items():
                if val:
                    override_lines.append(f"- {key}: {val}")

        user_msg = f"""EXISTING PATTERN:
{json.dumps(original_pattern, indent=2)}

MODIFICATION REQUEST:
{modification_prompt}"""
        if override_lines:
            user_msg += "\n\nHARD OVERRIDES (must apply these exactly):\n" + "\n".join(override_lines)

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": mod_prompt},
                {"role": "user", "content": user_msg}
            ],
            "temperature": 0.7,
            "max_tokens": 16384,
            "response_format": {"type": "json_object"}
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.API_URL, data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI API error ({e.code}): {body[:200]}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Network error: {e.reason}")

        try:
            text = result["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Unexpected OpenAI response format: {e}")

        pattern = _extract_json(text)
        return validate(pattern)


class ClaudeProvider:
    """Anthropic Claude API provider."""

    API_URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key
        self.model = model

    def _call(self, system_prompt: str, user_msg: str) -> str:
        """Send a message to Claude and return the text response."""
        payload = {
            "model": self.model,
            "max_tokens": 16384,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_msg}]
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.API_URL, data=data,
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01"
            }, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            logger.error("Claude API HTTP %d: %s", e.code, body[:500])
            raise RuntimeError(f"Claude API error ({e.code}): {body[:200]}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Network error: {e.reason}")

        try:
            return result["content"][0]["text"]
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Unexpected Claude response format: {e}")

    def generate(self, user_prompt: str, mode: str = "melodic") -> dict:
        sys_prompt, _ = _get_prompts(mode)
        validate = _get_validator(mode)
        text = self._call(sys_prompt, user_prompt)
        return validate(_extract_json(text))

    def generate_modification(self, original_pattern: dict,
                              modification_prompt: str,
                              overrides: dict = None,
                              mode: str = "melodic") -> dict:
        _, mod_prompt = _get_prompts(mode)
        validate = _get_validator(mode)
        override_lines = []
        if overrides:
            for key, val in overrides.items():
                if val:
                    override_lines.append(f"- {key}: {val}")
        user_msg = f"""EXISTING PATTERN:
{json.dumps(original_pattern, indent=2)}

MODIFICATION REQUEST:
{modification_prompt}"""
        if override_lines:
            user_msg += "\n\nHARD OVERRIDES (must apply these exactly):\n" + "\n".join(override_lines)
        text = self._call(mod_prompt, user_msg)
        return validate(_extract_json(text))


def create_provider(config: dict):
    """Factory: create the appropriate LLM provider from config."""
    provider_name = config.get("llm_provider", "gemini").lower()
    return create_provider_by_name(provider_name, config)


def create_provider_by_name(name: str, config: dict):
    """Create a specific LLM provider by name, regardless of config default."""
    name = name.lower().strip()

    if name == "openai":
        api_key = config.get("openai_api_key", "")
        if not api_key:
            raise ValueError("OpenAI API key is not configured. Set it in config.json or the Settings panel.")
        model = config.get("openai_model", "gpt-4o-mini")
        return OpenAIProvider(api_key, model)
    elif name == "claude":
        api_key = config.get("claude_api_key", "")
        if not api_key:
            raise ValueError("Claude API key is not configured. Set it in config.json or the Settings panel.")
        model = config.get("claude_model", "claude-sonnet-4-20250514")
        return ClaudeProvider(api_key, model)
    else:
        api_key = config.get("gemini_api_key", "")
        if not api_key:
            raise ValueError("Gemini API key is not configured. Set it in config.json or the Settings panel.")
        model = config.get("gemini_model", "gemini-2.5-flash")
        return GeminiProvider(api_key, model)


def get_available_providers(config: dict) -> list:
    """Return list of provider names that have API keys configured."""
    available = []
    if config.get("gemini_api_key"):
        available.append("gemini")
    if config.get("openai_api_key"):
        available.append("openai")
    if config.get("claude_api_key"):
        available.append("claude")
    return available

