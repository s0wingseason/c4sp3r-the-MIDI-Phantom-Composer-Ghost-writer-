-- ============================================================
-- C@sp3r MIDI Import — ReaScript for REAPER
-- Imports the latest AI-generated MIDI file as a new item
-- on the selected track at the edit cursor position.
--
-- Usage:
--   1. Click "Insert into REAPER" in the C@sp3r web UI
--   2. Run this script in REAPER (Actions > Show Action List)
--   3. The MIDI file appears as a new item on the selected track
--
-- You can assign this to a keyboard shortcut or toolbar button.
--
-- (c) 2026 s0wingseason / Calvin D. Roberts
-- ============================================================

local function get_appdata()
  return os.getenv("APPDATA") or ""
end

local function get_reaper_data_path()
  local appdata = get_appdata()
  if appdata == "" then return nil end
  return appdata .. "\\REAPER\\Data"
end

local function read_file(path)
  local f = io.open(path, "r")
  if not f then return nil end
  local content = f:read("*a")
  f:close()
  return content
end

local function file_exists(path)
  local f = io.open(path, "r")
  if f then f:close() return true end
  return false
end

-- Main import function
local function import_midi()
  local data_path = get_reaper_data_path()
  if not data_path then
    reaper.ShowMessageBox(
      "Could not find REAPER Data directory.\n\n" ..
      "Make sure REAPER is installed and %APPDATA%\\REAPER\\Data exists.",
      "C@sp3r MIDI Import", 0)
    return
  end

  -- Read the marker file to find the latest exported MIDI
  local marker_path = data_path .. "\\AI_latest_midi_export.txt"
  local midi_path = read_file(marker_path)

  if not midi_path then
    -- Fallback: look for any .mid file in Data directory
    reaper.ShowMessageBox(
      "No MIDI export found.\n\n" ..
      "Click 'Insert into REAPER' in the C@sp3r web UI first,\n" ..
      "then run this script.",
      "C@sp3r MIDI Import", 0)
    return
  end

  -- Trim whitespace
  midi_path = midi_path:match("^%s*(.-)%s*$")

  if not file_exists(midi_path) then
    reaper.ShowMessageBox(
      "MIDI file not found:\n" .. midi_path .. "\n\n" ..
      "The file may have been moved or deleted.\n" ..
      "Try exporting again from the C@sp3r web UI.",
      "C@sp3r MIDI Import", 0)
    return
  end

  -- Get the selected track (or create one)
  local track = reaper.GetSelectedTrack(0, 0)
  if not track then
    -- No track selected — create a new one
    reaper.InsertTrackAtIndex(reaper.CountTracks(0), true)
    track = reaper.GetTrack(0, reaper.CountTracks(0) - 1)
    reaper.GetSetMediaTrackInfo_String(track, "P_NAME", "C@sp3r MIDI", true)
  end

  -- Get cursor position
  local cursor_pos = reaper.GetCursorPosition()

  -- Begin undo block
  reaper.Undo_BeginBlock()

  -- Insert the MIDI file as a new media item
  local item = reaper.CreateNewMIDIItemInProj(track, cursor_pos, cursor_pos + 4, false)

  if item then
    -- Delete the empty item and use InsertMedia instead for proper MIDI import
    reaper.DeleteTrackMediaItem(track, item)
  end

  -- Select only the target track
  reaper.SetOnlyTrackSelected(track)
  reaper.SetEditCurPos(cursor_pos, false, false)

  -- Insert the MIDI file using REAPER's built-in media insertion
  -- Mode 0 = insert at cursor on selected track
  local result = reaper.InsertMedia(midi_path, 0)

  if result == 0 then
    -- InsertMedia failed, try alternative method
    reaper.ShowMessageBox(
      "Could not insert MIDI file. Trying alternative method...",
      "C@sp3r MIDI Import", 0)
    -- Use command to insert media
    reaper.InsertMedia(midi_path, 1)
  end

  reaper.Undo_EndBlock("C@sp3r: Import MIDI Pattern", -1)

  -- Update the UI
  reaper.UpdateArrange()
  reaper.TrackList_AdjustWindows(false)

  -- Get the filename for the status message
  local filename = midi_path:match("([^\\]+)$") or midi_path
  reaper.ShowConsoleMsg("C@sp3r: Imported " .. filename .. " at " ..
    string.format("%.2f", cursor_pos) .. "s\n")
end

-- Run it
import_midi()
