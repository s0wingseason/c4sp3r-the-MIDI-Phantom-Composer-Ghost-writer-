# Changelog

All notable changes to C@sp3r: the MIDI Phantom Composer Ghost Writer.

## [1.00] — 2026-05-06

### 🎉 Initial Public Release

#### New Features
- **Full Arrangement Mode** — Generate coordinated Drums + Bass + Chords + Melody from a single prompt
- **Complexity Slider** (1–10) — Control pattern density from simple to intricate
- **Humanization Control** (0–100%) — From quantized precision to loose, expressive timing
- **Style Blending** — Select 2 styles and blend with a percentage slider
- **Chord Preset Library** — 30+ one-click chord progression presets (Pop I-V-vi-IV, Jazz ii-V-I, Andalusian, Canon in D, etc.)
- **Multi-Track MIDI Export** — Type 1 MIDI files for arrangements (4 tracks, proper GM mapping)
- **Generation Reports** — Detailed text report saved alongside every generation
- **Arrangement Mini Piano Rolls** — Color-coded multi-track visualization in the results panel
- **JSFX Auto-Polling** — Plugin automatically detects new patterns without manual reload

#### Core Features (from pre-release development)
- Multi-provider AI generation (Google Gemini, OpenAI GPT, Anthropic Claude)
- Multi-iteration generation with carousel browsing
- 4 generation modes: Melodic Arpeggio, Drum Loop, Chord Progression, Full Arrangement
- REAPER JSFX plugin with Generator & Arpeggiator modes
- ReaImGui Lua GUI for in-DAW control
- Real-time MIDI preview via Windows GS Wavetable Synth
- Pattern library with save, categorize, favorite, rename
- Pattern modification ("Make it darker", "Add more syncopation")
- Dark glassmorphism UI with Inter font
- Console log viewer (backtick `` ` `` toggle)
- One-click build_and_run.bat / uninstall.bat scripts

#### Rebranding
- Renamed from "FalconEYE AI Arpeggio Generator" to "C@sp3r: the MIDI Phantom Composer Ghost Writer"
- Updated all credits to s0wingseason / Calvin D. Roberts
