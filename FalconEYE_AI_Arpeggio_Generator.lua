--[[
  FalconEYE AI Arpeggio Generator — REAPER ReaImGui Script
  Provides an in-REAPER GUI for the AI Arpeggio Generator backend.
  Communicates with the Flask server via HTTP on localhost:8765.
  
  Requirements:
    - ReaImGui (cfillion) — install via ReaPack
    - Backend server must be running (build_and_run.bat or the .exe)
    
  (c) 2026 FalconEYE Software Dev
]]

-- ============================================================
-- Dependency Check
-- ============================================================
if not reaper.ImGui_CreateContext then
    reaper.MB(
        "This script requires ReaImGui.\n\n" ..
        "Install via ReaPack:\n" ..
        "  1. Extensions > ReaPack > Browse packages\n" ..
        "  2. Search 'ReaImGui'\n" ..
        "  3. Right-click > Install\n" ..
        "  4. Click Apply, then restart REAPER",
        "FalconEYE AI Arpeggio — Missing Dependency", 0
    )
    return
end

-- ============================================================
-- HTTP Layer — tries LuaSocket first, falls back to curl
-- ============================================================
local http_method = "none"  -- "luasocket" or "curl" or "none"

-- Try Mavriq-Lua-Batteries for LuaSocket
local http, ltn12
local batteries_path = reaper.GetResourcePath() .. "/Scripts/Mavriq ReaScript Repository/Various/Mavriq-Lua-Batteries/batteries_header.lua"
if reaper.file_exists(batteries_path) then
    dofile(batteries_path)
    local ok1, h = pcall(require, "socket.http")
    local ok2, l = pcall(require, "ltn12")
    if ok1 and ok2 then
        http = h
        ltn12 = l
        http.TIMEOUT = 3
        http_method = "luasocket"
    end
end

-- Fallback: check if curl is available (built into Windows 10+)
if http_method == "none" then
    local test = io.popen("curl --version 2>nul")
    if test then
        local output = test:read("*a")
        test:close()
        if output and output:find("curl") then
            http_method = "curl"
        end
    end
end

if http_method == "none" then
    reaper.MB(
        "No HTTP method available.\n\n" ..
        "This script needs either:\n" ..
        "  • Mavriq-Lua-Batteries (install via ReaPack)\n" ..
        "  • curl (built into Windows 10+)\n\n" ..
        "Please install one of these and try again.",
        "FalconEYE AI Arpeggio — HTTP Error", 0
    )
    return
end

-- Load JSON parser
local script_path = debug.getinfo(1, "S").source:match("@?(.*[\\/])")
package.path = package.path .. ";" .. script_path .. "?.lua"
local json_ok, json = pcall(require, "dkjson")
if not json_ok then
    local alt_path = reaper.GetResourcePath() .. "/Scripts/FalconEYE/"
    package.path = package.path .. ";" .. alt_path .. "?.lua"
    json_ok, json = pcall(require, "dkjson")
end
if not json_ok then
    reaper.MB("Could not load dkjson.lua JSON library.\nMake sure dkjson.lua is in the same folder as this script.",
        "FalconEYE AI Arpeggio — Error", 0)
    return
end

-- ============================================================
-- HTTP Functions
-- ============================================================
local API_BASE = "http://127.0.0.1:8765"

local function curl_escape(s)
    return s:gsub("\\", "\\\\"):gsub('"', '\\"'):gsub("\n", "\\n")
end

local function api_get(path)
    if http_method == "luasocket" then
        local resp_body = {}
        local ok, code = http.request{
            url = API_BASE .. path,
            sink = ltn12.sink.table(resp_body),
            headers = {["Accept"] = "application/json"},
        }
        if ok and code == 200 then
            return json.decode(table.concat(resp_body)), nil
        end
        return nil, "HTTP " .. tostring(code)
    elseif http_method == "curl" then
        local cmd = 'curl -s -m 3 "' .. API_BASE .. path .. '"'
        local handle = io.popen(cmd)
        if not handle then return nil, "curl failed" end
        local result = handle:read("*a")
        handle:close()
        if result and #result > 0 then
            local data, _, err = json.decode(result)
            if data then return data, nil end
            return nil, err or "JSON parse error"
        end
        return nil, "empty response"
    end
    return nil, "no HTTP method"
end

local function api_post(path, data)
    local req_body = json.encode(data)
    if http_method == "luasocket" then
        local resp_body = {}
        local ok, code = http.request{
            url = API_BASE .. path,
            method = "POST",
            source = ltn12.source.string(req_body),
            sink = ltn12.sink.table(resp_body),
            headers = {
                ["Content-Type"] = "application/json",
                ["Content-Length"] = tostring(#req_body),
                ["Accept"] = "application/json",
            },
        }
        if ok and code == 200 then
            return json.decode(table.concat(resp_body)), nil
        end
        return nil, "HTTP " .. tostring(code)
    elseif http_method == "curl" then
        -- Write request body to temp file to avoid shell escaping issues
        local tmp = os.tmpname()
        local f = io.open(tmp, "w")
        if f then f:write(req_body); f:close() end
        local cmd = 'curl -s -m 5 -X POST -H "Content-Type: application/json" -d @"' .. tmp .. '" "' .. API_BASE .. path .. '"'
        local handle = io.popen(cmd)
        if not handle then os.remove(tmp); return nil, "curl failed" end
        local result = handle:read("*a")
        handle:close()
        os.remove(tmp)
        if result and #result > 0 then
            local resp, _, err = json.decode(result)
            if resp then return resp, nil end
            return nil, err or "JSON parse error"
        end
        return nil, "empty response"
    end
    return nil, "no HTTP method"
end

local function api_delete(path)
    if http_method == "luasocket" then
        local resp_body = {}
        local ok, code = http.request{
            url = API_BASE .. path,
            method = "DELETE",
            sink = ltn12.sink.table(resp_body),
            headers = {["Accept"] = "application/json"},
        }
        if ok and code == 200 then
            return json.decode(table.concat(resp_body)), nil
        end
        return nil, "HTTP " .. tostring(code)
    elseif http_method == "curl" then
        local cmd = 'curl -s -m 3 -X DELETE "' .. API_BASE .. path .. '"'
        local handle = io.popen(cmd)
        if not handle then return nil, "curl failed" end
        local result = handle:read("*a")
        handle:close()
        if result and #result > 0 then
            local resp, _, err = json.decode(result)
            if resp then return resp, nil end
        end
        return nil, "delete failed"
    end
    return nil, "no HTTP method"
end

-- ============================================================
-- ReaImGui Setup
-- ============================================================
local ctx = reaper.ImGui_CreateContext("FalconEYE AI Arpeggio Generator")
local FONT = reaper.ImGui_CreateFont("Inter")
reaper.ImGui_Attach(ctx, FONT)

local SZ = 14
local SZ_SMALL = 12
local SZ_BOLD = 15
local SZ_TITLE = 20

-- Colors
local COL_BG        = 0x0A0A10FF
local COL_PANEL     = 0x12121CDD
local COL_ACCENT    = 0xA855F7FF
local COL_ACCENT_DIM= 0xA855F766
local COL_GREEN     = 0x34D399FF
local COL_AMBER     = 0xF59E0BFF
local COL_RED       = 0xEF4444FF
local COL_TEXT      = 0xE8E6F0FF
local COL_TEXT_DIM  = 0x9590ADFF
local COL_TEXT_MUTED= 0x5C5777FF
local COL_BORDER    = 0x505082AA
local COL_INPUT_BG  = 0x141423EE
local COL_BTN_BG    = 0x191928BB
local COL_INDIGO    = 0x6366F1FF

-- ============================================================
-- State
-- ============================================================
local state = {
    -- Connection
    server_connected = false,
    last_check = 0,
    http_method_name = http_method,
    -- Tab: "compose" or "library"
    active_tab = "compose",
    -- Mode: "melodic", "drums", "chords"
    gen_mode = "melodic",
    gen_mode_idx = 0, -- 0=melodic, 1=drums, 2=chords
    -- Status
    status = "idle",
    status_msg = "Ready",
    -- Compose
    prompt = "",
    key_idx = 0,
    scale_idx = 0,
    time_sig_idx = 0,
    bars_idx = 2,
    subdiv_idx = 0,
    octave_idx = 0,
    -- Current pattern
    pattern = nil,
    pattern_raw = nil,
    -- Modify
    modify_open = false,
    modify_prompt = "",
    mod_bpm = "",
    mod_bars_idx = 0,
    mod_key_idx = 0,
    mod_scale_idx = 0,
    -- Library
    library = {},
    lib_categories = {"All"},
    lib_cat_idx = 0,
    lib_fav_only = false,
    lib_needs_refresh = true,
    lib_selected_id = nil,
    lib_selected_pattern = nil,
    last_poll = 0,
}

-- Lookup tables
local KEYS = {"Auto","C","C#","D","Eb","E","F","F#","G","Ab","A","Bb","B"}
local KEY_VALUES = {"","C","C#","D","Eb","E","F","F#","G","Ab","A","Bb","B"}
local SCALES = {"Auto","Major","Minor","Min Penta","Maj Penta","Dorian","Phrygian","Lydian","Mixolydian","Harm Min","Blues"}
local SCALE_VALUES = {"","major","minor","minor pentatonic","major pentatonic","dorian","phrygian","lydian","mixolydian","harmonic minor","blues"}
local TIME_SIGS = {"Auto","4/4","3/4","6/8","5/4","7/8"}
local TIME_SIG_VALUES = {"","4/4","3/4","6/8","5/4","7/8"}
local BARS = {"Auto","1","2","4","8"}
local BAR_VALUES = {"","1","2","4","8"}
local SUBDIVS = {"Auto","Quarter","8th","16th","Triplets"}
local SUBDIV_VALUES = {"","quarter notes","eighth notes","sixteenth notes","triplets"}
local OCTAVES = {"Auto","1 Oct","2 Oct","3 Oct"}
local OCTAVE_VALUES = {"","1 octave","2 octaves","3 octaves"}

local STYLES = {
    {group="Trap & Hip-Hop", items={"Trap","Rage","Cloud Rap","Drill","Plugg","Phonk","Boom Bap"}},
    {group="Hyperpop & Digicore", items={"Hyperpop","Digicore","PC Music","Nightcore","Glitchcore"}},
    {group="Indie & Emo", items={"Midwest Emo","Indie Rock","Indie Pop","Shoegaze","Emo Rap","Math Rock"}},
    {group="Electronic", items={"Synthwave","New Wave","Lo-Fi","Vaporwave","Future Bass","Dark Ambient"}},
    {group="Fundamentals", items={"Ascending","Descending","Broken Chord","Trance Gate","Random"}},
}
local STYLE_PROMPTS = {
    ["Trap"]="dark trap arpeggio with 808 feel, minor key, eerie bell-like tones",
    ["Rage"]="rage beat arpeggio, distorted aggressive synth lead, fast chaotic notes, minor key",
    ["Cloud Rap"]="cloud rap arpeggio, dreamy ethereal floating synth, reverb-drenched, spacey",
    ["Drill"]="drill arpeggio, dark sliding melody, menacing minor key, staccato hits",
    ["Plugg"]="plugg beat arpeggio, bouncy plucky melody, playful and catchy",
    ["Phonk"]="phonk arpeggio, dark memphis cowbell melody, distorted and gritty",
    ["Boom Bap"]="boom bap melodic arpeggio, jazzy sampled feel, warm with swing",
    ["Hyperpop"]="hyperpop arpeggio, glitchy pitch-shifted, aggressive bright tones, fast chaotic",
    ["Digicore"]="digicore arpeggio, digital ethereal glitchy melody, breakcore-influenced, emotional",
    ["PC Music"]="PC music style arpeggio, bubbly hyper-synthetic, pitch-bent pop melody",
    ["Nightcore"]="nightcore-style fast arpeggio, bright euphoric, rapid ascending runs",
    ["Glitchcore"]="glitchcore arpeggio, stuttered broken melodic fragments, distorted bitcrushed",
    ["Midwest Emo"]="midwest emo arpeggio, twinkly clean guitar-like, mathy, emotional minor key",
    ["Indie Rock"]="indie rock arpeggio, jangly bright open chords, clean tone, upbeat",
    ["Indie Pop"]="indie pop arpeggio, sparkling synth melody, dreamy and catchy, major key",
    ["Shoegaze"]="shoegaze arpeggio, wall of sound layered melody, lush reverb, dreamy",
    ["Emo Rap"]="emo rap melodic arpeggio, sad guitar-like tones, emotional descending",
    ["Math Rock"]="math rock arpeggio, complex tapping-style, odd meters, technical",
    ["Synthwave"]="synthwave retro 80s arpeggio, nostalgic analog synth, driving pulse",
    ["New Wave"]="new wave arpeggio, post-punk angular synth melody, dark minimal",
    ["Lo-Fi"]="lo-fi gentle arpeggio, warm detuned Rhodes feel, jazzy and mellow",
    ["Vaporwave"]="vaporwave arpeggio, slowed-down dreamy chopped melody, nostalgic hazy",
    ["Future Bass"]="future bass arpeggio, bright supersaw chord plucks, uplifting euphoric",
    ["Dark Ambient"]="dark ambient arpeggio, sparse atmospheric, reverb, haunting drones",
    ["Ascending"]="ascending arpeggio, smooth legato",
    ["Descending"]="descending arpeggio, staccato",
    ["Broken Chord"]="random/broken chord pattern, syncopated",
    ["Trance Gate"]="trance gate arpeggio, driving rhythmic",
    ["Random"]="generative random note pattern, aleatoric",
}

local GEN_MODES = {"melodic", "drums", "chords"}
local GEN_MODE_LABELS = {"Melodic Arpeggio", "Drum Loop", "Chord Progression"}

local DRUM_STYLES = {
    {group="Trap & Hip-Hop", items={"Trap","Rage","Drill","Plugg","Phonk","Boom Bap","Cloud Rap"}},
    {group="Hyperpop", items={"Hyperpop","Digicore","Breakcore"}},
    {group="Indie & Emo", items={"Midwest Emo","Indie Rock","Indie Pop","Pop Punk"}},
    {group="Electronic", items={"Future Bass","House","DnB","Lo-Fi","Synthwave","New Wave"}},
    {group="Other", items={"Rock","Funk","Shuffle","Half-Time"}},
}
local DRUM_PROMPTS = {
    ["Trap"]="trap drum pattern with rapid hi-hat rolls and 808 kick, bouncy",
    ["Rage"]="rage beat drums, aggressive distorted 808, fast hi-hat rolls, chaotic",
    ["Drill"]="drill music drum pattern with sliding hi-hats, hard 808 kick",
    ["Plugg"]="plugg beat drums, soft bouncy kick pattern, minimal hi-hats",
    ["Phonk"]="phonk drum pattern, dark memphis percussion, cowbell, distorted",
    ["Boom Bap"]="boom bap hip-hop drums with swing, classic 90s feel",
    ["Cloud Rap"]="cloud rap drums, sparse minimal kick and snare, soft spacey",
    ["Hyperpop"]="hyperpop drum pattern, distorted glitchy percussion, pitch-shifted snares",
    ["Digicore"]="digicore drums, breakcore-influenced glitchy beats, emotional fast",
    ["Breakcore"]="breakcore drum pattern, chopped amen breaks, stuttered chaotic",
    ["Midwest Emo"]="midwest emo drum pattern, dynamic fills, mathy odd time signatures",
    ["Indie Rock"]="indie rock drum beat, driving energetic, tight snare and toms",
    ["Indie Pop"]="indie pop drum beat, light bouncy groove, consistent hi-hats",
    ["Pop Punk"]="pop punk drum pattern, fast driving beat with crashes, energetic",
    ["Future Bass"]="future bass drums, sidechained kick with snappy snare, bright",
    ["House"]="house music four-on-the-floor with open hi-hats",
    ["DnB"]="drum and bass breakbeat, fast and syncopated",
    ["Lo-Fi"]="lo-fi hip-hop drums, gentle swing, warm feel",
    ["Synthwave"]="synthwave drum machine, retro 80s Roland-style, gated reverb",
    ["New Wave"]="new wave drums, minimal post-punk percussion, angular",
    ["Rock"]="standard rock drum beat, driving kick and snare",
    ["Funk"]="funk drum groove with ghost notes on snare",
    ["Shuffle"]="shuffle drum beat, triplet feel with swung hi-hats",
    ["Half-Time"]="half-time drum beat, spacious and heavy, trap-influenced",
}

local CHORD_STYLES = {
    {group="Trap & Hip-Hop", items={"Trap","Drill","Cloud Rap","Emo Rap","Phonk"}},
    {group="Hyperpop & Electronic", items={"Hyperpop","EDM","Future Bass","Synthwave","Lo-Fi"}},
    {group="Indie & Emo", items={"Midwest Emo","Indie Rock","Indie Pop","Shoegaze"}},
    {group="R&B & Soul", items={"Neo-Soul","R&B","Trap Soul","Gospel"}},
    {group="Jazz & Classical", items={"Jazz ii-V-I","Cinematic","Modal","12-Bar Blues"}},
}
local CHORD_PROMPTS = {
    ["Trap"]="trap chord progression, dark minor voicings, 808 bass-ready",
    ["Drill"]="drill chord progression, dark and menacing minor chords, sparse",
    ["Cloud Rap"]="cloud rap chord progression, dreamy ethereal pads, lush",
    ["Emo Rap"]="emo rap chord progression, sad piano-driven minor chords",
    ["Phonk"]="phonk chord progression, dark memphis-style, minor key",
    ["Hyperpop"]="hyperpop chords, bright chaotic, unexpected key changes",
    ["EDM"]="EDM chord progression, anthemic and uplifting",
    ["Future Bass"]="future bass chords, lush supersaws, major 7ths, euphoric",
    ["Synthwave"]="synthwave retro chord progression, nostalgic pads",
    ["Lo-Fi"]="lo-fi hip-hop chords with 7ths, warm and mellow",
    ["Midwest Emo"]="midwest emo chords, twinkly open voicings, emotional",
    ["Indie Rock"]="indie rock chord progression, jangly open chords",
    ["Indie Pop"]="indie pop chord progression, sparkling and dreamy",
    ["Shoegaze"]="shoegaze chords, layered wall of sound, reverbed",
    ["Neo-Soul"]="neo-soul chord progression with rich 9ths and 13ths",
    ["R&B"]="R&B chord progression with smooth voice leading",
    ["Trap Soul"]="trap soul chords, dark minor with chromatic movement",
    ["Gospel"]="gospel chord progression with chromatic passing chords",
    ["Jazz ii-V-I"]="jazz ii-V-I chord progression with 7th extensions",
    ["Cinematic"]="cinematic epic chord progression, dramatic",
    ["Modal"]="modal interchange chord progression",
    ["12-Bar Blues"]="blues chord progression, classic 12-bar with dominant 7ths",
}

-- ============================================================
-- Server Communication
-- ============================================================
local function check_server()
    local now = reaper.time_precise()
    if now - state.last_check < 3 then return end
    state.last_check = now
    local result, err = api_get("/api/status")
    if result then
        state.server_connected = true
        if state.status == "generating" then
            state.status = result.status or "idle"
            state.status_msg = result.message or "Ready"
            if result.status == "done" and result.pattern then
                state.pattern = result.pattern
                state.status = "done"
                -- Fetch raw pattern for modify
                if result.pattern.library_id then
                    local full = api_get("/api/library/" .. result.pattern.library_id)
                    if full and full.pattern then
                        state.pattern_raw = full.pattern
                    end
                end
                state.lib_needs_refresh = true
            end
        end
    else
        state.server_connected = false
    end
end

local function generate()
    if state.prompt == "" then
        state.status_msg = "Please enter a prompt"
        return
    end
    local mode = GEN_MODES[state.gen_mode_idx + 1] or "melodic"
    local params = {
        prompt = state.prompt,
        mode = mode,
        time_sig = TIME_SIG_VALUES[state.time_sig_idx + 1],
        bars = BAR_VALUES[state.bars_idx + 1],
        subdivision = SUBDIV_VALUES[state.subdiv_idx + 1],
        auto_save = true,
    }
    -- Melodic/chord only params
    if mode ~= "drums" then
        params.key = KEY_VALUES[state.key_idx + 1]
        params.scale = SCALE_VALUES[state.scale_idx + 1]
        params.octave_range = OCTAVE_VALUES[state.octave_idx + 1]
    end
    local result, err = api_post("/api/generate", params)
    if result and not result.error then
        state.status = "generating"
        state.status_msg = "AI is composing your pattern..."
    else
        state.status = "error"
        state.status_msg = result and result.error or (err or "Failed to connect")
    end
end

local function modify_pattern()
    if not state.pattern_raw and not state.pattern then
        state.status_msg = "No pattern to modify"
        return
    end
    local overrides = {}
    if state.mod_bpm ~= "" then overrides.bpm = state.mod_bpm end
    if state.mod_bars_idx > 0 then overrides.bars = BAR_VALUES[state.mod_bars_idx + 1] end
    if state.mod_key_idx > 0 then overrides.key = KEY_VALUES[state.mod_key_idx + 1] end
    if state.mod_scale_idx > 0 then overrides.scale = SCALE_VALUES[state.mod_scale_idx + 1] end

    local result, err = api_post("/api/modify", {
        original_pattern = state.pattern_raw or state.pattern,
        modification_prompt = state.modify_prompt,
        overrides = overrides,
        auto_save = true,
    })
    if result and not result.error then
        state.status = "generating"
        state.status_msg = "AI is modifying your pattern..."
    else
        state.status = "error"
        state.status_msg = result and result.error or (err or "Failed to connect")
    end
end

local function load_library()
    local cat = "All"
    if state.lib_cat_idx > 0 and state.lib_categories[state.lib_cat_idx + 1] then
        cat = state.lib_categories[state.lib_cat_idx + 1]
    end
    local url = "/api/library/list?category=" .. cat .. "&favorites=" .. tostring(state.lib_fav_only)
    local result, err = api_get(url)
    if result then
        state.library = result.patterns or {}
        if result.categories then
            state.lib_categories = {"All"}
            for _, c in ipairs(result.categories) do
                table.insert(state.lib_categories, c)
            end
        end
    end
    state.lib_needs_refresh = false
end

-- ============================================================
-- ImGui Helpers
-- ============================================================
local function combo_items(label, current, items)
    local items_str = table.concat(items, "\0") .. "\0"
    local changed, new_val = reaper.ImGui_Combo(ctx, label, current, items_str)
    return changed, new_val
end

local function push_theme()
    reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_WindowBg(), COL_BG)
    reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_ChildBg(), COL_PANEL)
    reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_FrameBg(), COL_INPUT_BG)
    reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_FrameBgHovered(), 0x1E1E33FF)
    reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_Button(), COL_BTN_BG)
    reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_ButtonHovered(), 0x2A2A44FF)
    reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_ButtonActive(), COL_ACCENT_DIM)
    reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_Header(), 0x2A2A44FF)
    reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_HeaderHovered(), COL_ACCENT_DIM)
    reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_Tab(), COL_BTN_BG)
    reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_TabHovered(), COL_ACCENT_DIM)
    reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_TabSelected(), COL_ACCENT)
    reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_Border(), COL_BORDER)
    reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_Text(), COL_TEXT)
    reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_CheckMark(), COL_ACCENT)
    reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_TableHeaderBg(), 0x1A1A2EFF)
    reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_TableBorderLight(), COL_BORDER)
    reaper.ImGui_PushStyleVar(ctx, reaper.ImGui_StyleVar_WindowRounding(), 8)
    reaper.ImGui_PushStyleVar(ctx, reaper.ImGui_StyleVar_FrameRounding(), 6)
    reaper.ImGui_PushStyleVar(ctx, reaper.ImGui_StyleVar_ChildRounding(), 8)
    reaper.ImGui_PushStyleVar(ctx, reaper.ImGui_StyleVar_WindowPadding(), 12, 12)
end

local function pop_theme()
    reaper.ImGui_PopStyleVar(ctx, 4)
    reaper.ImGui_PopStyleColor(ctx, 17)
end

-- ============================================================
-- Draw: Status Bar
-- ============================================================
local function draw_status_bar()
    reaper.ImGui_PushFont(ctx, FONT, SZ_SMALL)
    if state.server_connected then
        reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_Text(), COL_GREEN)
        reaper.ImGui_Text(ctx, "● Connected (" .. state.http_method_name .. ")")
    else
        reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_Text(), COL_RED)
        reaper.ImGui_Text(ctx, "● Disconnected — start backend (build_and_run.bat)")
    end
    reaper.ImGui_PopStyleColor(ctx)

    reaper.ImGui_SameLine(ctx)
    local col = COL_TEXT_MUTED
    if state.status == "generating" then col = COL_AMBER
    elseif state.status == "done" then col = COL_GREEN
    elseif state.status == "error" then col = COL_RED
    end
    reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_Text(), col)
    reaper.ImGui_Text(ctx, "  " .. state.status_msg)
    reaper.ImGui_PopStyleColor(ctx)
    reaper.ImGui_PopFont(ctx)
end

-- ============================================================
-- Draw: Piano Roll (DrawList-based)
-- ============================================================
local function draw_piano_roll(pattern, width, height)
    if not pattern then return end
    local events = pattern.events or {}
    local loop_len = pattern.loop_length_beats or 4
    if #events == 0 then return end

    local cx, cy = reaper.ImGui_GetCursorScreenPos(ctx)
    local draw_list = reaper.ImGui_GetWindowDrawList(ctx)

    -- Background
    reaper.ImGui_DrawList_AddRectFilled(draw_list, cx, cy, cx + width, cy + height, 0x0A0A14FF, 6)

    -- Note range
    local min_note, max_note = 127, 0
    for _, e in ipairs(events) do
        if e.note < min_note then min_note = e.note end
        if e.note > max_note then max_note = e.note end
    end
    local note_range = math.max(max_note - min_note + 1, 1)

    -- Grid
    for b = 1, loop_len - 1 do
        local gx = cx + (b / loop_len) * width
        reaper.ImGui_DrawList_AddLine(draw_list, gx, cy, gx, cy + height, 0x30305044, 1)
    end

    -- Notes
    local pad = 4
    for _, e in ipairs(events) do
        local nx = cx + (e.beat / loop_len) * width
        local nw = math.max((e.duration / loop_len) * width, 3)
        local ny = cy + height - pad - ((e.note - min_note) / note_range) * (height - pad * 2)
        local nh = math.max(math.min(height / note_range, 10), 3)
        local vel_r = (e.velocity or 100) / 127
        local alpha = math.floor(vel_r * 200 + 55)
        reaper.ImGui_DrawList_AddRectFilled(draw_list, nx, ny - nh/2, nx + nw, ny + nh/2, 0x7C3AED00 + alpha, 2)
    end

    -- Border
    reaper.ImGui_DrawList_AddRect(draw_list, cx, cy, cx + width, cy + height, COL_BORDER, 6)

    reaper.ImGui_Dummy(ctx, width, height)
end

-- ============================================================
-- Draw: Compose Tab
-- ============================================================
local function draw_compose_tab()
    -- Prompt
    reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_Text(), COL_TEXT_DIM)
    reaper.ImGui_Text(ctx, "DESCRIBE YOUR ARPEGGIO")
    reaper.ImGui_PopStyleColor(ctx)

    -- Mode toggle (Melodic / Drums / Chords)
    reaper.ImGui_PushItemWidth(ctx, -1)
    local mode_changed, new_mode = combo_items("Mode##gen", state.gen_mode_idx, GEN_MODE_LABELS)
    if mode_changed then state.gen_mode_idx = new_mode end
    reaper.ImGui_PopItemWidth(ctx)
    local cur_mode = GEN_MODES[state.gen_mode_idx + 1] or "melodic"
    local is_drums = cur_mode == "drums"

    reaper.ImGui_PushItemWidth(ctx, -1)
    local changed
    changed, state.prompt = reaper.ImGui_InputTextMultiline(ctx, "##prompt", state.prompt, -1, 60)
    reaper.ImGui_PopItemWidth(ctx)

    -- Param combos
    reaper.ImGui_PushItemWidth(ctx, 90)
    if not is_drums then
        changed, state.key_idx = combo_items("Key", state.key_idx, KEYS)
        reaper.ImGui_SameLine(ctx)
        changed, state.scale_idx = combo_items("Scale", state.scale_idx, SCALES)
        reaper.ImGui_SameLine(ctx)
    end
    changed, state.time_sig_idx = combo_items("TimeSig", state.time_sig_idx, TIME_SIGS)

    changed, state.bars_idx = combo_items("Bars", state.bars_idx, BARS)
    reaper.ImGui_SameLine(ctx)
    changed, state.subdiv_idx = combo_items("Subdiv", state.subdiv_idx, SUBDIVS)
    if not is_drums then
        reaper.ImGui_SameLine(ctx)
        changed, state.octave_idx = combo_items("Octave", state.octave_idx, OCTAVES)
    end
    reaper.ImGui_PopItemWidth(ctx)

    -- Quick Styles
    reaper.ImGui_Spacing(ctx)
    reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_Text(), COL_TEXT_DIM)
    reaper.ImGui_Text(ctx, "QUICK STYLES")
    reaper.ImGui_PopStyleColor(ctx)

    reaper.ImGui_PushFont(ctx, FONT, SZ_SMALL)
    -- Select styles based on mode
    local style_groups = STYLES
    local style_prompts = STYLE_PROMPTS
    if cur_mode == "drums" then style_groups = DRUM_STYLES; style_prompts = DRUM_PROMPTS
    elseif cur_mode == "chords" then style_groups = CHORD_STYLES; style_prompts = CHORD_PROMPTS end
    for _, group in ipairs(style_groups) do
        reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_Text(), 0x6366F1AA)
        reaper.ImGui_Text(ctx, group.group)
        reaper.ImGui_PopStyleColor(ctx)
        for i, name in ipairs(group.items) do
            if i > 1 then reaper.ImGui_SameLine(ctx) end
            if reaper.ImGui_SmallButton(ctx, name) then
                if state.prompt == "" then
                    state.prompt = style_prompts[name] or name:lower()
                end
            end
        end
    end
    reaper.ImGui_PopFont(ctx)

    -- Generate button
    reaper.ImGui_Spacing(ctx)
    reaper.ImGui_Spacing(ctx)

    local gen_disabled = state.status == "generating"
    if gen_disabled then
        reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_Button(), 0x6366F1AA)
    else
        reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_Button(), COL_ACCENT)
        reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_ButtonHovered(), 0xB975F7FF)
    end

    local btn_label = gen_disabled and "Composing..." or "Generate Pattern"
    if reaper.ImGui_Button(ctx, btn_label, -1, 32) and not gen_disabled then
        generate()
    end
    reaper.ImGui_PopStyleColor(ctx, gen_disabled and 1 or 2)

    -- Pattern preview (if we have one)
    if state.pattern then
        reaper.ImGui_Spacing(ctx)
        reaper.ImGui_Separator(ctx)
        reaper.ImGui_Spacing(ctx)

        local p = state.pattern
        reaper.ImGui_PushFont(ctx, FONT, SZ_BOLD)
        reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_Text(), COL_ACCENT)
        reaper.ImGui_Text(ctx, p.pattern_name or "AI Pattern")
        reaper.ImGui_PopStyleColor(ctx)
        reaper.ImGui_PopFont(ctx)

        reaper.ImGui_PushFont(ctx, FONT, SZ_SMALL)
        reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_Text(), COL_TEXT_DIM)
        reaper.ImGui_Text(ctx, string.format(
            "%s events  |  %s beats  |  %s  |  %s  |  BPM %s",
            p.num_events or "?", p.loop_length_beats or "?",
            p.time_sig or "4/4", p.scale_name or "?", p.bpm_suggestion or "?"
        ))
        reaper.ImGui_PopStyleColor(ctx)
        reaper.ImGui_PopFont(ctx)

        -- Piano roll
        reaper.ImGui_Spacing(ctx)
        local avail_w = reaper.ImGui_GetContentRegionAvail(ctx)
        draw_piano_roll(p, avail_w, 100)

        -- REAPER hint
        reaper.ImGui_Spacing(ctx)
        reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_Text(), COL_GREEN)
        reaper.ImGui_PushFont(ctx, FONT, SZ_SMALL)
        reaper.ImGui_Text(ctx, "Pattern saved! Click Reload Pattern on the JSFX, then press Play.")
        reaper.ImGui_PopFont(ctx)
        reaper.ImGui_PopStyleColor(ctx)

        -- Modify section
        reaper.ImGui_Spacing(ctx)
        reaper.ImGui_Separator(ctx)

        reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_Button(), 0xF59E0B33)
        reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_ButtonHovered(), 0xF59E0B55)
        reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_Text(), COL_AMBER)
        if reaper.ImGui_Button(ctx, "Modify This Beat", -1, 26) then
            state.modify_open = not state.modify_open
        end
        reaper.ImGui_PopStyleColor(ctx, 3)

        if state.modify_open then
            reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_Text(), COL_TEXT_DIM)
            reaper.ImGui_Text(ctx, "WHAT TO CHANGE")
            reaper.ImGui_PopStyleColor(ctx)

            reaper.ImGui_PushItemWidth(ctx, -1)
            changed, state.modify_prompt = reaper.ImGui_InputTextMultiline(ctx, "##mod_prompt", state.modify_prompt, -1, 40)
            reaper.ImGui_PopItemWidth(ctx)

            reaper.ImGui_PushItemWidth(ctx, 80)
            changed, state.mod_bpm = reaper.ImGui_InputText(ctx, "BPM##mod", state.mod_bpm)
            reaper.ImGui_SameLine(ctx)
            changed, state.mod_bars_idx = combo_items("Bars##mod", state.mod_bars_idx, BARS)
            reaper.ImGui_SameLine(ctx)
            changed, state.mod_key_idx = combo_items("Key##mod", state.mod_key_idx, KEYS)
            reaper.ImGui_SameLine(ctx)
            changed, state.mod_scale_idx = combo_items("Scale##mod", state.mod_scale_idx, SCALES)
            reaper.ImGui_PopItemWidth(ctx)

            reaper.ImGui_Spacing(ctx)
            reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_Button(), 0xD97706FF)
            reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_ButtonHovered(), 0xF59E0BFF)
            reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_Text(), 0x1A1A2EFF)
            local mod_disabled = state.status == "generating"
            local mod_label = mod_disabled and "Modifying..." or "Apply Changes"
            if reaper.ImGui_Button(ctx, mod_label, -1, 28) and not mod_disabled then
                modify_pattern()
            end
            reaper.ImGui_PopStyleColor(ctx, 3)
        end
    end
end

-- ============================================================
-- Draw: Library Tab (Full Pattern Browser)
-- ============================================================
local function draw_library_tab()
    -- Filters row
    reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_Text(), COL_TEXT_DIM)
    reaper.ImGui_Text(ctx, "PATTERN LIBRARY")
    reaper.ImGui_PopStyleColor(ctx)

    reaper.ImGui_PushItemWidth(ctx, 150)
    local cat_changed, new_cat = combo_items("Category##lib", state.lib_cat_idx, state.lib_categories)
    if cat_changed then state.lib_cat_idx = new_cat; state.lib_needs_refresh = true end
    reaper.ImGui_PopItemWidth(ctx)

    reaper.ImGui_SameLine(ctx)
    local fav_changed, new_fav = reaper.ImGui_Checkbox(ctx, "Favorites Only", state.lib_fav_only)
    if fav_changed then state.lib_fav_only = new_fav; state.lib_needs_refresh = true end

    reaper.ImGui_SameLine(ctx)
    if reaper.ImGui_SmallButton(ctx, "Refresh") then
        state.lib_needs_refresh = true
    end

    -- Load library if needed
    if state.lib_needs_refresh and state.server_connected then
        load_library()
    end

    reaper.ImGui_Spacing(ctx)
    reaper.ImGui_Separator(ctx)
    reaper.ImGui_Spacing(ctx)

    if #state.library == 0 then
        reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_Text(), COL_TEXT_MUTED)
        reaper.ImGui_Text(ctx, "No patterns found. Generate some patterns first!")
        reaper.ImGui_PopStyleColor(ctx)
        return
    end

    -- Pattern list with details
    local avail_w = reaper.ImGui_GetContentRegionAvail(ctx)

    for idx, p in ipairs(state.library) do
        local is_selected = (state.lib_selected_id == p.id)

        -- Card-like container
        reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_ChildBg(),
            is_selected and 0x2A2A44FF or 0x14141CCC)
        reaper.ImGui_PushStyleVar(ctx, reaper.ImGui_StyleVar_ChildRounding(), 8)

        local card_flags = 0
        -- Compat: ImGui_ChildFlags_Border was added in newer ReaImGui, use boolean fallback
        if reaper.ImGui_ChildFlags_Border then
            card_flags = reaper.ImGui_ChildFlags_Border()
        end

        local child_ok
        if card_flags ~= 0 then
            child_ok = reaper.ImGui_BeginChild(ctx, "lib_card_" .. p.id, -1, 0, card_flags, reaper.ImGui_WindowFlags_AutoResize())
        else
            -- Older ReaImGui: border is the 5th bool parameter
            child_ok = reaper.ImGui_BeginChild(ctx, "lib_card_" .. p.id, -1, 0, true)
        end
        if child_ok then
            -- Row 1: Name + Favorite
            reaper.ImGui_PushFont(ctx, FONT, SZ_BOLD)
            reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_Text(), is_selected and COL_ACCENT or COL_TEXT)
            reaper.ImGui_Text(ctx, p.name or "Unnamed Pattern")
            reaper.ImGui_PopStyleColor(ctx)
            reaper.ImGui_PopFont(ctx)

            reaper.ImGui_SameLine(ctx, avail_w - 30)
            local fav_label = p.favorite and "★" or "☆"
            reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_Text(), p.favorite and COL_AMBER or COL_TEXT_MUTED)
            if reaper.ImGui_SmallButton(ctx, fav_label .. "##fav_" .. p.id) then
                api_post("/api/library/" .. p.id .. "/favorite", {})
                state.lib_needs_refresh = true
            end
            reaper.ImGui_PopStyleColor(ctx)

            -- Row 2: Metadata tags
            reaper.ImGui_PushFont(ctx, FONT, SZ_SMALL)
            reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_Text(), COL_INDIGO)
            local meta = string.format("%s events  |  %sb  |  %s  |  %s  |  BPM %s",
                p.num_events or "?",
                p.loop_length_beats or "?",
                p.time_sig or "4/4",
                p.scale_name or "?",
                p.bpm_suggestion or "?"
            )
            reaper.ImGui_Text(ctx, meta)
            reaper.ImGui_PopStyleColor(ctx)

            -- Category badge
            if p.category and p.category ~= "Uncategorized" then
                reaper.ImGui_SameLine(ctx)
                reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_Text(), COL_ACCENT)
                reaper.ImGui_Text(ctx, " [" .. p.category .. "]")
                reaper.ImGui_PopStyleColor(ctx)
            end

            -- Prompt display
            if p.prompt and p.prompt ~= "" then
                reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_Text(), COL_TEXT_MUTED)
                local display_prompt = p.prompt
                if #display_prompt > 80 then
                    display_prompt = display_prompt:sub(1, 77) .. "..."
                end
                reaper.ImGui_Text(ctx, display_prompt)
                reaper.ImGui_PopStyleColor(ctx)
            end
            reaper.ImGui_PopFont(ctx)

            -- Row 3: Action buttons
            reaper.ImGui_Spacing(ctx)
            reaper.ImGui_PushFont(ctx, FONT, SZ_SMALL)

            -- Load to REAPER button (primary)
            reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_Button(), 0xA855F733)
            reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_ButtonHovered(), 0xA855F766)
            reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_Text(), COL_ACCENT)
            if reaper.ImGui_SmallButton(ctx, "Load to REAPER##" .. p.id) then
                local result = api_post("/api/library/" .. p.id .. "/load", {})
                if result and result.pattern then
                    state.pattern = result.pattern
                    state.status = "done"
                    state.status_msg = "Loaded: " .. (result.pattern.pattern_name or "Pattern")
                    local full = api_get("/api/library/" .. p.id)
                    if full and full.pattern then
                        state.pattern_raw = full.pattern
                    end
                    state.lib_selected_id = p.id
                end
            end
            reaper.ImGui_PopStyleColor(ctx, 3)

            -- Preview (expand) button
            reaper.ImGui_SameLine(ctx)
            if reaper.ImGui_SmallButton(ctx, "Preview##" .. p.id) then
                state.lib_selected_id = (state.lib_selected_id == p.id) and nil or p.id
                if state.lib_selected_id == p.id then
                    local full = api_get("/api/library/" .. p.id)
                    if full and full.pattern then
                        state.lib_selected_pattern = full.pattern
                    end
                end
            end

            -- Delete button
            reaper.ImGui_SameLine(ctx)
            reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_ButtonHovered(), 0xEF444466)
            if reaper.ImGui_SmallButton(ctx, "Delete##" .. p.id) then
                api_delete("/api/library/" .. p.id)
                state.lib_needs_refresh = true
                if state.lib_selected_id == p.id then
                    state.lib_selected_id = nil
                    state.lib_selected_pattern = nil
                end
            end
            reaper.ImGui_PopStyleColor(ctx)

            reaper.ImGui_PopFont(ctx)

            -- Expanded preview (piano roll)
            if is_selected and state.lib_selected_pattern then
                reaper.ImGui_Spacing(ctx)
                draw_piano_roll(state.lib_selected_pattern, avail_w - 30, 80)
            end

            reaper.ImGui_EndChild(ctx)
        end

        reaper.ImGui_PopStyleVar(ctx)
        reaper.ImGui_PopStyleColor(ctx)
        reaper.ImGui_Spacing(ctx)
    end

    -- Summary
    reaper.ImGui_Spacing(ctx)
    reaper.ImGui_PushFont(ctx, FONT, SZ_SMALL)
    reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_Text(), COL_TEXT_MUTED)
    reaper.ImGui_Text(ctx, string.format("%d patterns", #state.library))
    reaper.ImGui_PopStyleColor(ctx)
    reaper.ImGui_PopFont(ctx)
end

-- ============================================================
-- Main Loop
-- ============================================================
local function loop()
    check_server()

    -- Polling during generation
    if state.status == "generating" then
        local now = reaper.time_precise()
        if now - state.last_poll > 1 then
            state.last_poll = now
            local result = api_get("/api/status")
            if result then
                state.status_msg = result.message or state.status_msg
                if result.status == "done" then
                    state.status = "done"
                    if result.pattern then
                        state.pattern = result.pattern
                        if result.pattern.library_id then
                            local full = api_get("/api/library/" .. result.pattern.library_id)
                            if full and full.pattern then
                                state.pattern_raw = full.pattern
                            end
                        end
                    end
                    state.lib_needs_refresh = true
                elseif result.status == "error" then
                    state.status = "error"
                end
            end
        end
    end

    push_theme()
    reaper.ImGui_PushFont(ctx, FONT, SZ)

    local visible, open = reaper.ImGui_Begin(ctx, "FalconEYE AI Arpeggio Generator", true,
        reaper.ImGui_WindowFlags_NoCollapse())

    if visible then
        -- Title bar
        reaper.ImGui_PushFont(ctx, FONT, SZ_TITLE)
        reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_Text(), COL_ACCENT)
        reaper.ImGui_Text(ctx, "FalconEYE")
        reaper.ImGui_PopStyleColor(ctx)
        reaper.ImGui_PopFont(ctx)
        reaper.ImGui_SameLine(ctx)
        reaper.ImGui_PushFont(ctx, FONT, SZ_SMALL)
        reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_Text(), COL_TEXT_MUTED)
        reaper.ImGui_Text(ctx, "AI ARPEGGIO GENERATOR")
        reaper.ImGui_PopStyleColor(ctx)
        reaper.ImGui_PopFont(ctx)

        -- Status bar
        draw_status_bar()
        reaper.ImGui_Spacing(ctx)

        -- Tab buttons (manual tab bar for max compatibility)
        local tab_w = 120
        local compose_active = state.active_tab == "compose"
        local library_active = state.active_tab == "library"

        reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_Button(),
            compose_active and COL_ACCENT or COL_BTN_BG)
        reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_Text(),
            compose_active and 0xFFFFFFFF or COL_TEXT_DIM)
        if reaper.ImGui_Button(ctx, "Compose", tab_w, 24) then
            state.active_tab = "compose"
        end
        reaper.ImGui_PopStyleColor(ctx, 2)

        reaper.ImGui_SameLine(ctx)

        reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_Button(),
            library_active and COL_ACCENT or COL_BTN_BG)
        reaper.ImGui_PushStyleColor(ctx, reaper.ImGui_Col_Text(),
            library_active and 0xFFFFFFFF or COL_TEXT_DIM)
        if reaper.ImGui_Button(ctx, "Pattern Library", tab_w, 24) then
            state.active_tab = "library"
            state.lib_needs_refresh = true
        end
        reaper.ImGui_PopStyleColor(ctx, 2)

        reaper.ImGui_Spacing(ctx)
        reaper.ImGui_Separator(ctx)
        reaper.ImGui_Spacing(ctx)

        -- Tab content
        if state.active_tab == "compose" then
            draw_compose_tab()
        else
            draw_library_tab()
        end

        reaper.ImGui_End(ctx)
    end

    reaper.ImGui_PopFont(ctx)
    pop_theme()

    if open then
        reaper.defer(loop)
    end
end

-- ============================================================
-- Launch
-- ============================================================
reaper.defer(loop)
