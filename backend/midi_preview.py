"""
MIDI Preview — Plays pattern data through Windows' built-in MIDI synthesizer.
Uses the Windows Multimedia API (winmm.dll) directly via ctypes for zero
additional dependencies. Targets the Microsoft GS Wavetable Synth.

(c) 2026 s0wingseason / Calvin D. Roberts
"""

import ctypes
import ctypes.wintypes
import logging
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Windows Multimedia API bindings
# ---------------------------------------------------------------------------
winmm = ctypes.windll.winmm

CALLBACK_NULL = 0x00000000
MIDI_MAPPER = -1  # Uses the default MIDI output device

# Function prototypes
winmm.midiOutOpen.argtypes = [
    ctypes.POINTER(ctypes.wintypes.HANDLE),  # lphmo
    ctypes.c_uint,                            # uDeviceID
    ctypes.c_ulong,                           # dwCallback
    ctypes.c_ulong,                           # dwCallbackInstance
    ctypes.c_ulong,                           # dwFlags
]
winmm.midiOutOpen.restype = ctypes.c_uint

winmm.midiOutClose.argtypes = [ctypes.wintypes.HANDLE]
winmm.midiOutClose.restype = ctypes.c_uint

winmm.midiOutShortMsg.argtypes = [ctypes.wintypes.HANDLE, ctypes.c_ulong]
winmm.midiOutShortMsg.restype = ctypes.c_uint

winmm.midiOutReset.argtypes = [ctypes.wintypes.HANDLE]
winmm.midiOutReset.restype = ctypes.c_uint

winmm.midiOutGetNumDevs.argtypes = []
winmm.midiOutGetNumDevs.restype = ctypes.c_uint


def _midi_msg(status: int, data1: int, data2: int) -> int:
    """Pack a MIDI short message for winmm (little-endian DWORD)."""
    return status | (data1 << 8) | (data2 << 16)


NOTE_ON = 0x90
NOTE_OFF = 0x80
PROGRAM_CHANGE = 0xC0


class MidiPreviewPlayer:
    """
    Plays MIDI patterns through the Windows default MIDI synthesizer.
    Runs playback in a background thread with stop/cancel support.
    """

    def __init__(self):
        self._handle: Optional[ctypes.wintypes.HANDLE] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self.is_playing = False
        self.playback_position = 0.0  # Current beat position
        self.total_beats = 0.0

    def _open(self) -> bool:
        """Open the default MIDI output device."""
        if self._handle is not None:
            return True

        handle = ctypes.wintypes.HANDLE()
        # Use MIDI_MAPPER (0xFFFFFFFF as unsigned) for default device
        result = winmm.midiOutOpen(
            ctypes.byref(handle),
            0xFFFFFFFF,  # MIDI_MAPPER
            0, 0,
            CALLBACK_NULL
        )

        if result != 0:
            logger.error("Failed to open MIDI output device (error %d)", result)
            num_devs = winmm.midiOutGetNumDevs()
            logger.info("Number of MIDI output devices: %d", num_devs)
            return False

        self._handle = handle
        logger.info("MIDI output device opened successfully")
        return True

    def _close(self):
        """Close the MIDI output device."""
        if self._handle is not None:
            winmm.midiOutReset(self._handle)
            winmm.midiOutClose(self._handle)
            self._handle = None
            logger.info("MIDI output device closed")

    def _send_note_on(self, channel: int, note: int, velocity: int):
        """Send a Note On message."""
        if self._handle:
            msg = _midi_msg(NOTE_ON | (channel & 0x0F), note & 0x7F, velocity & 0x7F)
            winmm.midiOutShortMsg(self._handle, msg)

    def _send_note_off(self, channel: int, note: int):
        """Send a Note Off message."""
        if self._handle:
            msg = _midi_msg(NOTE_OFF | (channel & 0x0F), note & 0x7F, 0)
            winmm.midiOutShortMsg(self._handle, msg)

    def _send_program_change(self, channel: int, program: int):
        """Send a Program Change message."""
        if self._handle:
            msg = _midi_msg(PROGRAM_CHANGE | (channel & 0x0F), program & 0x7F, 0)
            winmm.midiOutShortMsg(self._handle, msg)

    def _all_notes_off(self, channel: int = 0):
        """Kill all sounding notes on a channel (or all channels if channel=-1)."""
        if self._handle:
            if channel < 0:
                for ch in range(16):
                    msg = _midi_msg(0xB0 | ch, 123, 0)
                    winmm.midiOutShortMsg(self._handle, msg)
            else:
                msg = _midi_msg(0xB0 | (channel & 0x0F), 123, 0)
                winmm.midiOutShortMsg(self._handle, msg)
            winmm.midiOutReset(self._handle)

    def play(self, pattern_data: dict, bpm: float = 120.0,
             channel: int = 0, program: int = 0, loop: bool = False) -> bool:
        """
        Start playing a single-track pattern in the background.

        Args:
            pattern_data: Pattern dict with 'events' and 'loop_length_beats'
            bpm: Tempo in beats per minute
            channel: MIDI channel (0-15)
            program: GM program number (0=Piano, 4=E.Piano, etc.)
            loop: Whether to loop the pattern
        Returns:
            True if playback started successfully
        """
        # Auto-detect: if arrangement with tracks, delegate to play_arrangement
        if pattern_data.get("type") == "arrangement" and pattern_data.get("tracks"):
            return self.play_arrangement(pattern_data, bpm=bpm, loop=loop)

        # Auto-detect drum patterns → force GM percussion channel 9
        is_drums = pattern_data.get("type") == "drums"
        if is_drums:
            channel = 9
            program = 0

        with self._lock:
            if self.is_playing:
                self.stop()
                time.sleep(0.1)

            if not self._open():
                return False

            self._stop_event.clear()
            self.is_playing = True
            self.playback_position = 0.0
            self.total_beats = float(pattern_data.get("loop_length_beats", 4))

            self._thread = threading.Thread(
                target=self._playback_worker,
                args=(pattern_data, bpm, channel, program, loop, is_drums),
                daemon=True
            )
            self._thread.start()
            return True

    def stop(self):
        """Stop playback."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        with self._lock:
            self._all_notes_off(channel=-1)
            self._close()
            self.is_playing = False
            self.playback_position = 0.0

    def _playback_worker(self, pattern_data: dict, bpm: float,
                         channel: int, program: int, loop: bool,
                         is_drums: bool = False):
        """Background thread that sequences and plays single-track MIDI events."""
        try:
            events = pattern_data.get("events", [])
            loop_len = float(pattern_data.get("loop_length_beats", 4))

            if not events:
                logger.warning("No events to play")
                return

            if not is_drums:
                self._send_program_change(channel, program)
            time.sleep(0.05)

            beat_duration = 60.0 / bpm
            sorted_events = sorted(events, key=lambda e: float(e.get("beat", 0)))

            timeline = []
            for evt in sorted_events:
                beat = float(evt.get("beat", 0))
                note = max(0, min(127, int(evt.get("note", 60))))
                vel = max(1, min(127, int(evt.get("velocity", 100))))
                dur = float(evt.get("duration", 0.25))
                timeline.append(("on", beat, note, vel))
                timeline.append(("off", beat + dur, note, 0))

            timeline.sort(key=lambda t: t[1])

            while not self._stop_event.is_set():
                start_time = time.perf_counter()

                for event_type, beat_pos, note, vel in timeline:
                    if self._stop_event.is_set():
                        break
                    target_time = start_time + beat_pos * beat_duration
                    now = time.perf_counter()
                    wait = target_time - now
                    if wait > 0:
                        while wait > 0 and not self._stop_event.is_set():
                            time.sleep(min(wait, 0.01))
                            wait = target_time - time.perf_counter()
                    if self._stop_event.is_set():
                        break
                    self.playback_position = beat_pos % loop_len
                    if event_type == "on":
                        self._send_note_on(channel, note, vel)
                    else:
                        self._send_note_off(channel, note)

                if not self._stop_event.is_set() and timeline:
                    last_time = timeline[-1][1]
                    remaining = (start_time + last_time * beat_duration) - time.perf_counter()
                    if remaining > 0:
                        self._stop_event.wait(remaining)

                if not loop or self._stop_event.is_set():
                    break

        except Exception as e:
            logger.error("Playback error: %s", str(e))
        finally:
            with self._lock:
                self._all_notes_off(channel=-1)
                self._close()
                self.is_playing = False

    # Default GM programs for arrangement tracks
    TRACK_PROGRAMS = {
        "drums":  (9,  0),    # Channel 10 (GM percussion), no program change needed
        "bass":   (1,  33),   # Channel 2, Fingered Bass
        "chords": (2,  4),    # Channel 3, Electric Piano 1
        "melody": (3,  80),   # Channel 4, Lead 1 (Square)
    }

    def play_arrangement(self, pattern_data: dict, bpm: float = 120.0,
                         solo_tracks: list = None, loop: bool = False,
                         programs: dict = None) -> bool:
        """
        Play a multi-track arrangement through the Windows MIDI synth.

        Args:
            pattern_data: Pattern dict with 'tracks' containing named sub-tracks
            bpm: Tempo in BPM
            solo_tracks: List of track names to play (e.g. ['drums', 'bass']).
                         If None or empty, plays all tracks.
            loop: Whether to loop
            programs: Optional dict of {track_name: gm_program_number} overrides
        Returns:
            True if playback started successfully
        """
        with self._lock:
            if self.is_playing:
                self.stop()
                time.sleep(0.1)

            if not self._open():
                return False

            self._stop_event.clear()
            self.is_playing = True
            self.playback_position = 0.0
            self.total_beats = float(pattern_data.get("loop_length_beats", 4))

            self._thread = threading.Thread(
                target=self._arrangement_worker,
                args=(pattern_data, bpm, solo_tracks, loop, programs),
                daemon=True
            )
            self._thread.start()
            return True

    def _arrangement_worker(self, pattern_data: dict, bpm: float,
                            solo_tracks: list, loop: bool,
                            programs: dict = None):
        """Background thread for multi-track arrangement playback."""
        try:
            tracks = pattern_data.get("tracks", {})
            loop_len = float(pattern_data.get("loop_length_beats", 4))

            if not tracks:
                logger.warning("No tracks to play")
                return

            # Determine which tracks to play
            active_tracks = solo_tracks if solo_tracks else list(tracks.keys())

            # Set up programs for each channel
            for track_name in active_tracks:
                if track_name not in tracks:
                    continue
                ch, default_prog = self.TRACK_PROGRAMS.get(track_name, (0, 0))
                prog = (programs or {}).get(track_name, default_prog)
                if track_name != "drums":  # Don't send program change to drum channel
                    self._send_program_change(ch, prog)
            time.sleep(0.05)

            # Build unified timeline from all active tracks
            beat_duration = 60.0 / bpm
            timeline = []

            for track_name in active_tracks:
                track = tracks.get(track_name, {})
                events = track.get("events", [])
                ch, _ = self.TRACK_PROGRAMS.get(track_name, (0, 0))

                for evt in events:
                    beat = float(evt.get("beat", 0))
                    note = max(0, min(127, int(evt.get("note", 60))))
                    vel = max(1, min(127, int(evt.get("velocity", 100))))
                    dur = float(evt.get("duration", 0.25))

                    timeline.append(("on", beat, note, vel, ch))
                    timeline.append(("off", beat + dur, note, 0, ch))

            timeline.sort(key=lambda t: t[1])

            if not timeline:
                logger.warning("No events in selected tracks")
                return

            while not self._stop_event.is_set():
                start_time = time.perf_counter()

                for event_type, beat_pos, note, vel, ch in timeline:
                    if self._stop_event.is_set():
                        break

                    target_time = start_time + beat_pos * beat_duration
                    now = time.perf_counter()
                    wait = target_time - now
                    if wait > 0:
                        while wait > 0 and not self._stop_event.is_set():
                            time.sleep(min(wait, 0.01))
                            wait = target_time - time.perf_counter()

                    if self._stop_event.is_set():
                        break

                    self.playback_position = beat_pos % loop_len

                    if event_type == "on":
                        self._send_note_on(ch, note, vel)
                    else:
                        self._send_note_off(ch, note)

                if not self._stop_event.is_set() and timeline:
                    last_time = timeline[-1][1]
                    remaining = (start_time + last_time * beat_duration) - time.perf_counter()
                    if remaining > 0:
                        self._stop_event.wait(remaining)

                if not loop or self._stop_event.is_set():
                    break

        except Exception as e:
            logger.error("Arrangement playback error: %s", str(e))
        finally:
            with self._lock:
                self._all_notes_off(channel=-1)
                self._close()
                self.is_playing = False

    def get_status(self) -> dict:
        """Return current playback status."""
        return {
            "is_playing": self.is_playing,
            "position": round(self.playback_position, 2),
            "total_beats": self.total_beats,
        }


# Singleton instance
_player = None


def get_player() -> MidiPreviewPlayer:
    """Get or create the singleton MIDI player."""
    global _player
    if _player is None:
        _player = MidiPreviewPlayer()
    return _player

