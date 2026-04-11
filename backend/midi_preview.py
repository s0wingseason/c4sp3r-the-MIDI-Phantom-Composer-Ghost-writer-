"""
MIDI Preview — Plays pattern data through Windows' built-in MIDI synthesizer.
Uses the Windows Multimedia API (winmm.dll) directly via ctypes for zero
additional dependencies. Targets the Microsoft GS Wavetable Synth.

(c) 2026 FalconEYE Software Dev
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
        """Kill all sounding notes on a channel."""
        if self._handle:
            # CC 123 = All Notes Off
            msg = _midi_msg(0xB0 | (channel & 0x0F), 123, 0)
            winmm.midiOutShortMsg(self._handle, msg)
            # Also reset
            winmm.midiOutReset(self._handle)

    def play(self, pattern_data: dict, bpm: float = 120.0,
             channel: int = 0, program: int = 0, loop: bool = False) -> bool:
        """
        Start playing a pattern in the background.

        Args:
            pattern_data: Pattern dict with 'events' and 'loop_length_beats'
            bpm: Tempo in beats per minute
            channel: MIDI channel (0-15)
            program: GM program number (0=Piano, 4=E.Piano, 25=Steel Guitar, etc.)
            loop: Whether to loop the pattern
        Returns:
            True if playback started successfully
        """
        # Auto-detect drum patterns → force GM percussion channel 9 (channel 10 in 1-indexed)
        is_drums = pattern_data.get("type") == "drums"
        if is_drums:
            channel = 9  # GM percussion channel
            program = 0  # No program change needed for channel 10

        with self._lock:
            # Stop any existing playback
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
            self._all_notes_off()
            self._close()
            self.is_playing = False
            self.playback_position = 0.0

    def _playback_worker(self, pattern_data: dict, bpm: float,
                         channel: int, program: int, loop: bool,
                         is_drums: bool = False):
        """Background thread that sequences and plays MIDI events."""
        try:
            events = pattern_data.get("events", [])
            loop_len = float(pattern_data.get("loop_length_beats", 4))

            if not events:
                logger.warning("No events to play")
                return

            # Set instrument (skip for drums — channel 10 is always percussion)
            if not is_drums:
                self._send_program_change(channel, program)
            time.sleep(0.05)

            # Pre-calculate timing
            beat_duration = 60.0 / bpm  # seconds per beat

            # Sort events by beat time
            sorted_events = sorted(events, key=lambda e: float(e.get("beat", 0)))

            # Build a timeline of note-on and note-off events
            timeline = []
            for evt in sorted_events:
                beat = float(evt.get("beat", 0))
                note = int(evt.get("note", 60))
                vel = int(evt.get("velocity", 100))
                dur = float(evt.get("duration", 0.25))

                # Clamp
                note = max(0, min(127, note))
                vel = max(1, min(127, vel))

                timeline.append(("on", beat, note, vel))
                timeline.append(("off", beat + dur, note, 0))

            # Sort by time
            timeline.sort(key=lambda t: t[1])

            while not self._stop_event.is_set():
                start_time = time.perf_counter()

                for event_type, beat_pos, note, vel in timeline:
                    if self._stop_event.is_set():
                        break

                    # Wait until the right moment
                    target_time = start_time + beat_pos * beat_duration
                    now = time.perf_counter()
                    wait = target_time - now
                    if wait > 0:
                        # Use small sleep increments to allow responsive stopping
                        while wait > 0 and not self._stop_event.is_set():
                            time.sleep(min(wait, 0.01))
                            wait = target_time - time.perf_counter()

                    if self._stop_event.is_set():
                        break

                    # Update position for UI
                    self.playback_position = beat_pos % loop_len

                    # Send MIDI
                    if event_type == "on":
                        self._send_note_on(channel, note, vel)
                    else:
                        self._send_note_off(channel, note)

                # Wait for final note-offs to complete
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
                self._all_notes_off()
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
