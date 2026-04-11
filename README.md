# FalconEYE AI Arpeggio Generator for REAPER

AI-powered MIDI arpeggio generator that creates musical patterns from natural language prompts. Works as a standalone desktop app, in your web browser, or directly inside REAPER.

## Quick Start

### Option 1: Standalone App (Recommended)
1. Double-click **`build_and_run.bat`** — installs dependencies and launches the native window
2. Enter your [Gemini API key](https://aistudio.google.com) in Settings (free tier, one-time setup)
3. Describe your arpeggio → click **Generate Pattern**
4. In REAPER, add the `FalconEYE AI Arpeggio` JSFX to a track, click Reload, press Play

### Option 2: Standalone .exe
1. Run **`build_exe.bat`** to create `FalconEYE_AI_Arpeggio_Generator.exe`
2. Double-click the `.exe` — same UI, no Python required at runtime

### Option 3: Inside REAPER (ReaImGui)
1. Install **ReaImGui** and **Mavriq-Lua-Batteries** via ReaPack
2. Actions → Load ReaScript → select `FalconEYE_AI_Arpeggio_Generator.lua`
3. Start the backend first (via the .exe or `build_and_run.bat`)
4. The REAPER script connects to the backend automatically

## Features

- **AI-Powered Generation** — Describe arpeggios in natural language, powered by Google Gemini (free tier)
- **30+ Quick Styles** — One-click presets organized by genre: Classic, Electronic, Ambient, Rhythm, Experimental
- **Modify This Beat** — Tweak an existing pattern by describing changes or overriding BPM/key/scale/length
- **Version History** — Up to 5 versions with undo, visualized as breadcrumb dots
- **Piano Roll Preview** — Real-time visualization of generated patterns
- **MIDI Preview** — Hear patterns through your Windows MIDI synth (no extra software needed)
- **Pattern Library** — Save, rename, categorize, and favorite your generated patterns
- **REAPER Integration** — JSFX plugin reads AI patterns and outputs MIDI in real-time
- **Two Modes** — Generator (plays pattern as-is) and Arpeggiator (uses pattern rhythm with your held notes)
- **Dual Interface** — Works as a standalone desktop app AND a docked window inside REAPER

## Requirements

- **Python 3.10+** (for first run / building)
- **Gemini API Key** (free at [aistudio.google.com](https://aistudio.google.com))
- **REAPER** (for DAW integration)
- **ReaPack** with ReaImGui + Mavriq-Lua-Batteries (for in-REAPER GUI only)

## File Structure

```
├── FalconEYE_AI_Arpeggio.jsfx          # REAPER MIDI plugin
├── FalconEYE_AI_Arpeggio_Generator.lua  # REAPER ReaImGui script
├── dkjson.lua                           # JSON library for Lua
├── config.json                          # Settings (API keys, port, paths)
├── build_and_run.bat                    # Install + launch (native window)
├── build_exe.bat                        # Build standalone .exe
├── uninstall.bat                        # Clean removal
├── backend/
│   ├── server.py                        # Flask backend
│   ├── launcher.py                      # Native window launcher (PyWebView)
│   ├── llm_engine.py                    # AI provider abstraction
│   ├── pattern_writer.py                # JSFX pattern file writer
│   ├── midi_preview.py                  # Windows MIDI preview
│   ├── pattern_library.py               # Pattern storage
│   └── static/                          # Web UI (HTML/CSS/JS)
└── pattern_library/                     # Saved patterns (auto-created)
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| "Python not found" | Install from [python.org](https://python.org), check "Add to PATH" |
| "Gemini API error" | Check your API key in Settings; ensure it's a valid Gemini key |
| JSFX shows "No pattern file" | Click Reload Pattern in the JSFX after generating |
| ReaScript "Disconnected" | Start the backend first via `build_and_run.bat` or the .exe |
| No MIDI preview sound | Check Windows MIDI settings; ensure Microsoft GS Wavetable Synth is enabled |

## License

(c) 2026 FalconEYE Software Dev. All rights reserved.
