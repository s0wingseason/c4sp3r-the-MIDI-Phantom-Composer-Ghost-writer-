# C@sp3r: the MIDI Phantom Composer Ghost Writer 👻🎹

**AI-powered MIDI generation for any DAW** — Generate melodies, drum loops, chord progressions, and full multi-track arrangements from natural language prompts.

> *v1.00 — by [s0wingseason](https://github.com/s0wingseason)*

---

## ✨ Features

### 🧠 AI-Powered Generation
- **4 Generation Modes**: Melodic Arpeggio, Drum Loop, Chord Progression, and **Full Arrangement** (Drums + Bass + Chords + Melody)
- **Multi-Provider AI**: Simultaneously query Google Gemini, OpenAI GPT, and Anthropic Claude
- **Multi-Iteration**: Generate multiple variations per provider for maximum creative options
- **Carousel UI**: Browse all results and pick your favorite

### 🎛️ Creative Controls
- **Complexity Slider** (1–10): Control pattern density from sparse to intricate
- **Humanization Slider** (0–100%): From perfectly quantized to loose, expressive timing
- **Style Blending**: Select 2 styles and blend them with a percentage slider (e.g., "60% Trap + 40% Lo-Fi")
- **Chord Preset Library**: 30+ one-click presets — Pop I-V-vi-IV, Jazz ii-V-I, Andalusian, Canon in D, and more
- **Musical Parameters**: Key, scale, time signature, bars, subdivision, octave range

### 🎹 REAPER Integration
- **JSFX Plugin**: Plays patterns in real-time inside REAPER — Generator & Arpeggiator modes
- **Auto-Reload**: JSFX detects new patterns automatically (no manual reload needed)
- **Lua GUI** (ReaImGui): Full in-DAW interface for generation without leaving REAPER
- **Swing, Gate, Transpose, Velocity** controls in the JSFX

### 🔌 VST3 Plugin *(Build Option)*
- Build a standalone VST3 `.dll` plugin for use in **any DAW** (FL Studio, Ableton, Cubase, Logic, etc.)
- Cross-platform via nih-plug (Rust)

### 🎵 Export & Preview
- **MIDI File Export**: Standard `.mid` files (Type 0 single-track, Type 1 multi-track for arrangements)
- **Real-Time Preview**: Built-in MIDI player via Windows GS Wavetable Synth
- **Pattern Library**: Save, categorize, favorite, rename, and manage all generated patterns
- **Generation Reports**: Detailed `.txt` report saved with every generation

### 💎 Premium UI
- Dark glassmorphism theme with vibrant accent colors
- Multi-track piano roll visualization for arrangements
- Real-time console log viewer (press backtick `` ` `` to toggle)
- Fully responsive design

---

## 🚀 Quick Start

### Prerequisites
- **Python 3.10+**
- **REAPER** (for JSFX/Lua integration — optional for standalone use)
- At least one AI API key: [Google Gemini](https://aistudio.google.com/), [OpenAI](https://platform.openai.com/), or [Anthropic Claude](https://console.anthropic.com/)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/s0wingseason/Casper-MIDI-Phantom-Composer.git
   cd Casper-MIDI-Phantom-Composer
   ```

2. **Double-click `build_and_run.bat`**
   - Automatically creates a Python virtual environment
   - Installs all dependencies
   - Copies the JSFX plugin to your REAPER Effects folder
   - Launches the web UI at `http://localhost:5000`

3. **Configure your API key(s)**
   - Click the ⚙️ gear icon in the app header
   - Paste your API key(s) and click Save

4. **Start generating!**
   - Type a prompt, select your mode, and hit Generate
   - In REAPER, insert the JSFX plugin on a track — patterns auto-load

### Uninstall
Double-click `uninstall.bat` to remove the virtual environment and installed dependencies.

---

## 📁 Project Structure

```
├── backend/
│   ├── server.py              # Flask backend — API routes, generation orchestration
│   ├── llm_engine.py          # AI provider integration (Gemini, OpenAI, Claude)
│   ├── midi_export.py         # MIDI file writer (Type 0 + Type 1 multi-track)
│   ├── midi_preview.py        # Real-time MIDI preview via Windows MIDI
│   ├── pattern_library.py     # Pattern save/load/categorize
│   ├── pattern_writer.py      # JSFX pattern file format writer
│   └── static/
│       ├── index.html          # Web UI
│       ├── style.css           # Dark glassmorphism theme
│       └── app.js              # Frontend logic
├── vst/                        # VST3 plugin source (nih-plug / Rust)
├── FalconEYE_AI_Arpeggio.jsfx # REAPER JSFX plugin
├── FalconEYE_AI_Arpeggio_Generator.lua  # REAPER Lua GUI
├── config.example.json         # Example configuration
├── build_and_run.bat           # One-click install + launch (Windows)
├── uninstall.bat               # One-click cleanup
├── CHANGELOG.md                # Version history
└── README.md                   # This file
```

---

## 🎼 Generation Modes

| Mode | Description | Tracks |
|------|-------------|--------|
| **Melodic Arpeggio** | Single melodic pattern — arpeggios, lead lines, basslines | 1 |
| **Drum Loop** | GM percussion pattern with kick, snare, hi-hat, etc. | 1 |
| **Chord Progression** | Multi-note chord voicings with voice leading | 1 |
| **Full Arrangement** 🏆 | Coordinated Drums + Bass + Chords + Melody | 4 |

---

## ⚙️ Configuration

All settings are managed through the app's Settings modal (⚙️). The `config.json` file stores:

- API keys (Gemini, OpenAI, Claude)
- Default LLM provider
- Model names per provider
- Server host/port
- Default providers for multi-generation

See `config.example.json` for the template.

> ⚠️ Never commit `config.json` to version control — it contains your API keys.

---

## 🔧 Building the VST3 Plugin

```bash
# Install Rust (one-time)
build_vst.bat

# Or manually:
cd vst
cargo build --release
# Output: target/release/casper_midi.dll
```

Copy the `.dll` to your DAW's VST3 folder.

---

## 📜 Credits

**C@sp3r: the MIDI Phantom Composer Ghost Writer**
Created by **Calvin D. Roberts** ([s0wingseason](https://github.com/s0wingseason))

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
