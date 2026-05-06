// ============================================================
// C@sp3r: the MIDI Phantom Composer Ghost Writer — VST3 Plugin
// Reads AI-generated pattern files and outputs MIDI events.
//
// (c) 2026 s0wingseason / Calvin D. Roberts
// ============================================================

use nih_plug::prelude::*;
use std::fs;
use std::path::PathBuf;
use std::sync::Arc;

/// A single note event in the pattern
#[derive(Clone, Debug)]
struct PatternEvent {
    beat: f64,
    note: u8,
    velocity: f32,
    duration: f64,
}

/// Active note that needs a note-off
#[derive(Clone, Debug)]
struct ActiveNote {
    note: u8,
    channel: u8,
    off_at_beat: f64,
}

/// The main plugin struct
struct CasperMidi {
    params: Arc<CasperParams>,
    /// Loaded pattern events
    events: Vec<PatternEvent>,
    /// Currently sounding notes awaiting note-off
    active_notes: Vec<ActiveNote>,
    /// Loop length in beats
    loop_len: f64,
    /// BPM from pattern file (informational)
    pattern_bpm: f64,
    /// Key root from pattern file
    pattern_key: i32,
    /// Whether a pattern is loaded
    pattern_loaded: bool,
    /// Last beat position to detect wraps
    last_beat: f64,
    /// Pattern file modification time for hot-reload
    last_file_mod: u64,
    /// Sample counter for periodic file checks
    poll_counter: u64,
    /// Samples between file checks (~250ms at 44100)
    poll_interval: u64,
}

/// Plugin parameters exposed to the DAW
#[derive(Params)]
struct CasperParams {
    #[id = "velocity"]
    velocity_scale: FloatParam,

    #[id = "octave"]
    octave_offset: IntParam,

    #[id = "gate"]
    gate_pct: FloatParam,

    #[id = "transpose"]
    transpose: IntParam,

    #[id = "swing"]
    swing_pct: FloatParam,

    #[id = "channel"]
    midi_channel: IntParam,

    #[id = "loop"]
    loop_enabled: BoolParam,
}

impl Default for CasperParams {
    fn default() -> Self {
        Self {
            velocity_scale: FloatParam::new(
                "Velocity Scale",
                1.0,
                FloatRange::Linear { min: 0.0, max: 2.0 },
            )
            .with_unit(" %")
            .with_value_to_string(formatters::v2s_f32_percentage(0))
            .with_string_to_value(formatters::s2v_f32_percentage()),

            octave_offset: IntParam::new("Octave Offset", 0, IntRange::Linear { min: -3, max: 3 }),

            gate_pct: FloatParam::new(
                "Gate Length",
                1.0,
                FloatRange::Linear { min: 0.1, max: 2.0 },
            )
            .with_unit(" %")
            .with_value_to_string(formatters::v2s_f32_percentage(0))
            .with_string_to_value(formatters::s2v_f32_percentage()),

            transpose: IntParam::new(
                "Transpose",
                0,
                IntRange::Linear { min: -24, max: 24 },
            )
            .with_unit(" st"),

            swing_pct: FloatParam::new(
                "Swing",
                0.0,
                FloatRange::Linear {
                    min: -0.5,
                    max: 0.5,
                },
            )
            .with_unit(" %")
            .with_value_to_string(formatters::v2s_f32_percentage(0))
            .with_string_to_value(formatters::s2v_f32_percentage()),

            midi_channel: IntParam::new("MIDI Channel", 1, IntRange::Linear { min: 1, max: 16 }),

            loop_enabled: BoolParam::new("Loop", true),
        }
    }
}

impl Default for CasperMidi {
    fn default() -> Self {
        Self {
            params: Arc::new(CasperParams::default()),
            events: Vec::new(),
            active_notes: Vec::new(),
            loop_len: 4.0,
            pattern_bpm: 120.0,
            pattern_key: 0,
            pattern_loaded: false,
            last_beat: -1.0,
            last_file_mod: 0,
            poll_counter: 0,
            poll_interval: 11025, // ~250ms at 44.1kHz
        }
    }
}

impl CasperMidi {
    /// Find the pattern data file. Searches:
    /// 1. Next to the plugin DLL
    /// 2. REAPER Data directory (%APPDATA%/REAPER/Data/)
    /// 3. Current working directory
    fn find_pattern_file() -> Option<PathBuf> {
        let filename = "AI_Arpeggio_pattern_data.txt";

        // Check REAPER Data directory
        if let Ok(appdata) = std::env::var("APPDATA") {
            let reaper_path = PathBuf::from(&appdata)
                .join("REAPER")
                .join("Data")
                .join(filename);
            if reaper_path.exists() {
                return Some(reaper_path);
            }
        }

        // Check current directory
        let cwd = PathBuf::from(filename);
        if cwd.exists() {
            return Some(cwd);
        }

        None
    }

    /// Get file modification timestamp (seconds since epoch)
    fn file_mod_time(path: &PathBuf) -> u64 {
        fs::metadata(path)
            .and_then(|m| m.modified())
            .ok()
            .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
            .map(|d| d.as_secs())
            .unwrap_or(0)
    }

    /// Load pattern data from the file
    fn load_pattern(&mut self) {
        let path = match Self::find_pattern_file() {
            Some(p) => p,
            None => return,
        };

        let mod_time = Self::file_mod_time(&path);
        if mod_time == self.last_file_mod && self.pattern_loaded {
            return; // File hasn't changed
        }

        let content = match fs::read_to_string(&path) {
            Ok(c) => c,
            Err(_) => return,
        };

        let mut lines = content.lines();

        // Parse header: num_events loop_length bpm key [type]
        let header = match lines.next() {
            Some(h) => h,
            None => return,
        };

        let parts: Vec<f64> = header
            .split_whitespace()
            .filter_map(|s| s.parse().ok())
            .collect();

        if parts.len() < 4 {
            return;
        }

        let num_events = parts[0] as usize;
        self.loop_len = parts[1].max(0.25);
        self.pattern_bpm = parts[2];
        self.pattern_key = parts[3] as i32;

        // Parse events: beat note velocity duration
        let mut events = Vec::with_capacity(num_events);
        for line in lines.take(num_events) {
            let vals: Vec<f64> = line
                .split_whitespace()
                .filter_map(|s| s.parse().ok())
                .collect();

            if vals.len() >= 4 {
                events.push(PatternEvent {
                    beat: vals[0],
                    note: (vals[1] as u8).clamp(0, 127),
                    velocity: (vals[2] as f32 / 127.0).clamp(0.0, 1.0),
                    duration: vals[3].max(0.01),
                });
            }
        }

        self.events = events;
        self.pattern_loaded = !self.events.is_empty();
        self.last_file_mod = mod_time;
        self.active_notes.clear();
    }

    /// Send note-off for all active notes
    fn all_notes_off(&mut self, context: &mut impl ProcessContext<Self>) {
        let ch = (self.params.midi_channel.value() - 1).clamp(0, 15) as u8;
        for note in self.active_notes.drain(..) {
            context.send_event(NoteEvent::NoteOff {
                timing: 0,
                voice_id: None,
                channel: ch,
                note: note.note,
                velocity: 0.0,
            });
        }
    }
}

impl Plugin for CasperMidi {
    const NAME: &'static str = "C@sp3r MIDI Phantom";
    const VENDOR: &'static str = "s0wingseason";
    const URL: &'static str = "https://github.com/s0wingseason";
    const EMAIL: &'static str = "";

    const VERSION: &'static str = env!("CARGO_PKG_VERSION");

    // This is a MIDI effect — no audio I/O
    const AUDIO_IO_LAYOUTS: &'static [AudioIOLayout] = &[];

    // We output MIDI
    const MIDI_INPUT: MidiConfig = MidiConfig::None;
    const MIDI_OUTPUT: MidiConfig = MidiConfig::MidiCCs;

    type SysExMessage = ();
    type BackgroundTask = ();

    fn params(&self) -> Arc<dyn Params> {
        self.params.clone()
    }

    fn initialize(
        &mut self,
        _audio_io_layout: &AudioIOLayout,
        buffer_config: &BufferConfig,
        _context: &mut impl InitContext<Self>,
    ) -> bool {
        // Set poll interval based on actual sample rate (~250ms)
        self.poll_interval = (buffer_config.sample_rate as u64) / 4;
        self.load_pattern();
        true
    }

    fn reset(&mut self) {
        self.last_beat = -1.0;
        self.active_notes.clear();
    }

    fn process(
        &mut self,
        _buffer: &mut Buffer,
        _aux: &mut AuxiliaryBuffers,
        context: &mut impl ProcessContext<Self>,
    ) -> ProcessStatus {
        // Periodic file poll
        self.poll_counter += context.transport().tempo.unwrap_or(120.0) as u64;
        if self.poll_counter >= self.poll_interval {
            self.poll_counter = 0;
            self.load_pattern();
        }

        if !self.pattern_loaded {
            return ProcessStatus::Normal;
        }

        let transport = context.transport();
        let playing = transport.playing;
        let tempo = transport.tempo.unwrap_or(120.0);

        // If not playing, kill all notes
        if !playing {
            if !self.active_notes.is_empty() {
                self.all_notes_off(context);
            }
            self.last_beat = -1.0;
            return ProcessStatus::Normal;
        }

        // Get current beat position
        let cur_beat_raw = match transport.pos_beats() {
            Some(b) => b,
            None => return ProcessStatus::Normal,
        };

        let loop_on = self.params.loop_enabled.value();
        let cur_beat = if loop_on {
            cur_beat_raw % self.loop_len
        } else {
            cur_beat_raw
        };

        // Calculate block duration in beats
        let sample_rate = transport.sample_rate;
        let block_beats = _buffer.samples() as f64 * tempo / (sample_rate as f64 * 60.0);
        let block_end = cur_beat + block_beats;

        let ch = (self.params.midi_channel.value() - 1).clamp(0, 15) as u8;
        let vel_scale = self.params.velocity_scale.value();
        let oct_offset = self.params.octave_offset.value();
        let transpose = self.params.transpose.value();
        let gate = self.params.gate_pct.value();
        let swing = self.params.swing_pct.value();

        // Detect transport restart / loop wrap
        if self.last_beat > cur_beat + 0.01 {
            self.all_notes_off(context);
        }

        // Send note-offs for expired notes
        let mut i = 0;
        while i < self.active_notes.len() {
            let mut off_beat = self.active_notes[i].off_at_beat;
            if loop_on {
                off_beat = off_beat % self.loop_len;
            }
            if off_beat <= cur_beat || (self.last_beat > cur_beat && off_beat > self.last_beat) {
                let note = self.active_notes.remove(i);
                context.send_event(NoteEvent::NoteOff {
                    timing: 0,
                    voice_id: None,
                    channel: ch,
                    note: note.note,
                    velocity: 0.0,
                });
            } else {
                i += 1;
            }
        }

        // Trigger new notes in this block
        for ev in &self.events {
            // Apply swing to even-numbered eighth notes
            let mut beat = ev.beat;
            let eighth = (beat * 2.0).floor();
            if eighth as i64 % 2 == 1 {
                beat += swing * 0.5;
            }

            // Check if this event falls in the current block
            let in_block = if block_end > self.loop_len && loop_on {
                // Wrapped block
                beat >= cur_beat || beat < (block_end % self.loop_len)
            } else {
                beat >= cur_beat && beat < block_end
            };

            if !in_block {
                continue;
            }

            // Calculate final note with transposition
            let raw_note = ev.note as i32 + (oct_offset * 12) + transpose;
            let note = raw_note.clamp(0, 127) as u8;

            // Calculate velocity
            let vel = (ev.velocity * vel_scale).clamp(0.0, 1.0);

            // Calculate timing within the block (sample offset)
            let beat_offset = if beat >= cur_beat {
                beat - cur_beat
            } else {
                (self.loop_len - cur_beat) + beat
            };
            let sample_offset =
                (beat_offset * 60.0 * sample_rate as f64 / tempo) as u32;
            let timing = sample_offset.min(_buffer.samples() as u32 - 1);

            // Send note-on
            context.send_event(NoteEvent::NoteOn {
                timing,
                voice_id: None,
                channel: ch,
                note,
                velocity: vel,
            });

            // Schedule note-off
            let off_beat = ev.beat + ev.duration * gate as f64;
            self.active_notes.push(ActiveNote {
                note,
                channel: ch,
                off_at_beat: off_beat,
            });
        }

        self.last_beat = cur_beat;
        ProcessStatus::Normal
    }
}

impl ClapPlugin for CasperMidi {
    const CLAP_ID: &'static str = "com.s0wingseason.casper-midi-phantom";
    const CLAP_DESCRIPTION: Option<&'static str> =
        Some("AI-powered MIDI pattern player — Ghost Writer for your DAW");
    const CLAP_MANUAL_URL: Option<&'static str> = None;
    const CLAP_SUPPORT_URL: Option<&'static str> = None;
    const CLAP_FEATURES: &'static [ClapFeature] = &[
        ClapFeature::NoteEffect,
        ClapFeature::Utility,
    ];
}

impl Vst3Plugin for CasperMidi {
    const VST3_CLASS_ID: [u8; 16] = *b"CsprMIDIPhantom!";
    const VST3_SUBCATEGORIES: &'static [Vst3SubCategory] = &[
        Vst3SubCategory::Instrument,
        Vst3SubCategory::Generator,
    ];
}

nih_export_clap!(CasperMidi);
nih_export_vst3!(CasperMidi);
