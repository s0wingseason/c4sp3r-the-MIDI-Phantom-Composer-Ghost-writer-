"""
MIDI File Exporter — Pure Python Standard MIDI File (SMF) writer.
Converts pattern data to Type 0 .mid files with no external dependencies.

(c) 2026 FalconEYE Software Dev
"""

import logging
import os
import struct
from typing import List

logger = logging.getLogger(__name__)

# MIDI status bytes
NOTE_ON = 0x90
NOTE_OFF = 0x80
PROGRAM_CHANGE = 0xC0
META_EVENT = 0xFF
META_TEMPO = 0x51
META_TIME_SIG = 0x58
META_TRACK_NAME = 0x03
META_END_OF_TRACK = 0x2F


def _write_variable_length(value: int) -> bytes:
    """Encode an integer as MIDI variable-length quantity (VLQ)."""
    if value < 0:
        value = 0
    result = []
    result.append(value & 0x7F)
    value >>= 7
    while value > 0:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    result.reverse()
    return bytes(result)


def _make_tempo_event(bpm: float) -> bytes:
    """Create a MIDI meta tempo event (microseconds per quarter note)."""
    uspqn = int(60_000_000 / bpm)
    return (
        _write_variable_length(0) +  # delta time = 0
        bytes([META_EVENT, META_TEMPO, 0x03]) +
        struct.pack(">I", uspqn)[1:]  # 3 bytes big-endian
    )


def _make_time_sig_event(num: int = 4, den: int = 4) -> bytes:
    """Create a MIDI meta time signature event."""
    # Denominator is expressed as power of 2 (4 = 2^2 = 2)
    den_pow = 0
    d = den
    while d > 1:
        d >>= 1
        den_pow += 1
    return (
        _write_variable_length(0) +
        bytes([META_EVENT, META_TIME_SIG, 0x04, num, den_pow, 24, 8])
    )


def _make_track_name_event(name: str) -> bytes:
    """Create a MIDI meta track name event."""
    name_bytes = name.encode("ascii", errors="replace")[:127]
    return (
        _write_variable_length(0) +
        bytes([META_EVENT, META_TRACK_NAME]) +
        _write_variable_length(len(name_bytes)) +
        name_bytes
    )


def _make_program_change(channel: int, program: int) -> bytes:
    """Create a program change event at delta time 0."""
    return (
        _write_variable_length(0) +
        bytes([PROGRAM_CHANGE | (channel & 0x0F), program & 0x7F])
    )


def _make_end_of_track() -> bytes:
    """Create a MIDI end-of-track meta event."""
    return _write_variable_length(0) + bytes([META_EVENT, META_END_OF_TRACK, 0x00])


def pattern_to_midi(pattern_data: dict, ppqn: int = 480) -> bytes:
    """
    Convert a pattern dict to a Standard MIDI File (Type 0, single track).

    Args:
        pattern_data: Pattern dict with 'events', 'loop_length_beats', etc.
        ppqn: Pulses (ticks) per quarter note. 480 is standard.

    Returns:
        Complete MIDI file as bytes.
    """
    events = pattern_data.get("events", [])
    bpm = float(pattern_data.get("bpm_suggestion", 120))
    loop_len = float(pattern_data.get("loop_length_beats", 4))
    pattern_type = pattern_data.get("type", "melodic")
    pattern_name = pattern_data.get("pattern_name", "AI Pattern")
    time_num = int(pattern_data.get("time_signature_num", 4))
    time_den = int(pattern_data.get("time_signature_den", 4))

    is_drums = pattern_type == "drums"
    channel = 9 if is_drums else 0  # GM drums on channel 10 (0-indexed: 9)

    # Build list of absolute-tick MIDI events: (tick, status, data1, data2)
    midi_events = []

    for evt in events:
        beat = float(evt.get("beat", 0))
        note = int(evt.get("note", 60))
        vel = int(evt.get("velocity", 100))
        dur = float(evt.get("duration", 0.25))

        note = max(0, min(127, note))
        vel = max(1, min(127, vel))

        on_tick = int(beat * ppqn)
        off_tick = int((beat + dur) * ppqn)

        midi_events.append((on_tick, NOTE_ON | channel, note, vel))
        midi_events.append((off_tick, NOTE_OFF | channel, note, 0))

    # Sort by tick, then note-off before note-on at same tick
    midi_events.sort(key=lambda e: (e[0], 0 if (e[1] & 0xF0) == NOTE_OFF else 1, e[2]))

    # Build track data
    track_data = bytearray()

    # Track name
    track_data += _make_track_name_event(pattern_name)

    # Time signature
    track_data += _make_time_sig_event(time_num, time_den)

    # Tempo
    track_data += _make_tempo_event(bpm)

    # Program change (skip for drums — channel 10 is always GM percussion)
    if not is_drums:
        track_data += _make_program_change(channel, 0)  # Piano default

    # MIDI note events with delta times
    prev_tick = 0
    for tick, status, data1, data2 in midi_events:
        delta = max(0, tick - prev_tick)
        track_data += _write_variable_length(delta)
        track_data += bytes([status, data1 & 0x7F, data2 & 0x7F])
        prev_tick = tick

    # End of track
    track_data += _make_end_of_track()

    # Build complete MIDI file
    # Header: MThd, length=6, format=0, tracks=1, ppqn
    header = b"MThd" + struct.pack(">IHhH", 6, 0, 1, ppqn)

    # Track chunk: MTrk + length + data
    track_chunk = b"MTrk" + struct.pack(">I", len(track_data)) + bytes(track_data)

    return header + track_chunk


def export_midi_file(pattern_data: dict, output_path: str) -> str:
    """
    Export pattern data as a standard MIDI file.

    Args:
        pattern_data: Full pattern dict from LLM
        output_path: Path to write the .mid file

    Returns:
        The output file path
    """
    midi_bytes = pattern_to_midi(pattern_data)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "wb") as f:
        f.write(midi_bytes)

    pattern_type = pattern_data.get("type", "melodic")
    num_events = len(pattern_data.get("events", []))
    logger.info("MIDI exported (%s): %d events → %s", pattern_type, num_events, output_path)
    return output_path
