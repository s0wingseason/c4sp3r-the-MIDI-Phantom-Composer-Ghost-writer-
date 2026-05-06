"""
Pattern Library — Persistent storage for generated MIDI patterns.
Supports save, load, rename, categorize, favorite, and delete operations.
Patterns are stored as individual JSON files in a library directory.

(c) 2026 s0wingseason / Calvin D. Roberts
"""

import json
import logging
import os
import time
import uuid
from typing import Optional

logger = logging.getLogger(__name__)

# Default categories
DEFAULT_CATEGORIES = [
    "Uncategorized",
    "Ambient",
    "Arpeggios",
    "Bass Lines",
    "Chord Progressions",
    "Chords",
    "Drum Loops",
    "Lead",
    "Percussion",
    "Experimental",
    "Favorites",
    # Genre categories
    "Trap",
    "Drill",
    "Hyperpop",
    "Lo-Fi",
    "Indie / Emo",
    "Synthwave",
    "Rage",
    "Phonk",
    "Cloud Rap",
    "R&B / Neo-Soul",
    "Pop",
    "Rock",
    "Jazz",
    "Cinematic",
]


class PatternLibrary:
    """Manages a persistent collection of MIDI patterns as JSON files."""

    def __init__(self, library_dir: str):
        self.library_dir = library_dir
        os.makedirs(library_dir, exist_ok=True)
        self._index_path = os.path.join(library_dir, "_index.json")
        self._index = self._load_index()

    def _load_index(self) -> dict:
        """Load or create the library index."""
        if os.path.exists(self._index_path):
            try:
                with open(self._index_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                logger.warning("Corrupt index file, rebuilding...")
        return {"patterns": {}, "categories": DEFAULT_CATEGORIES}

    def _save_index(self):
        """Persist the index to disk."""
        with open(self._index_path, "w", encoding="utf-8") as f:
            json.dump(self._index, f, indent=2)

    def save_pattern(self, pattern_data: dict, prompt: str = "",
                     category: str = "Uncategorized") -> dict:
        """
        Save a generated pattern to the library.

        Args:
            pattern_data: Full pattern dict from LLM
            prompt: Original user prompt
            category: Category name

        Returns:
            Pattern metadata entry
        """
        pattern_id = str(uuid.uuid4())[:8]
        timestamp = time.time()

        # Use AI-suggested name from the pattern, or generate fallback
        name = pattern_data.get("pattern_name", "AI Pattern")
        pattern_type = pattern_data.get("type", "melodic")

        # Auto-categorize drum/chord patterns if user didn't specify
        if pattern_type == "drums" and category == "Uncategorized":
            category = "Drum Loops"
        elif pattern_type == "chords" and category == "Uncategorized":
            category = "Chord Progressions"

        entry = {
            "id": pattern_id,
            "name": name,
            "prompt": prompt[:200],
            "category": category,
            "favorite": False,
            "created_at": timestamp,
            "updated_at": timestamp,
            "type": pattern_type,
            "key_root": pattern_data.get("key_root", 60),
            "scale_name": pattern_data.get("scale_name", "chromatic"),
            "time_sig": f"{pattern_data.get('time_signature_num', 4)}/{pattern_data.get('time_signature_den', 4)}",
            "loop_length_beats": pattern_data.get("loop_length_beats", 4),
            "bpm_suggestion": pattern_data.get("bpm_suggestion", 120),
            "num_events": len(pattern_data.get("events", [])),
        }

        if pattern_type == "drums":
            entry["kit_name"] = pattern_data.get("kit_name", "Standard Kit")

        # Save pattern data to individual file
        pattern_file = os.path.join(self.library_dir, f"{pattern_id}.json")
        with open(pattern_file, "w", encoding="utf-8") as f:
            json.dump({"meta": entry, "pattern": pattern_data}, f, indent=2)

        # Update index
        self._index["patterns"][pattern_id] = entry
        self._save_index()

        logger.info("Pattern saved: %s (%s) [%s]", name, pattern_id, pattern_type)
        return entry

    def get_pattern(self, pattern_id: str) -> Optional[dict]:
        """Load full pattern data by ID."""
        pattern_file = os.path.join(self.library_dir, f"{pattern_id}.json")
        if os.path.exists(pattern_file):
            with open(pattern_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def list_patterns(self, category: Optional[str] = None,
                      favorites_only: bool = False) -> list:
        """List pattern metadata, optionally filtered."""
        patterns = list(self._index.get("patterns", {}).values())

        if category and category != "All":
            patterns = [p for p in patterns if p.get("category") == category]

        if favorites_only:
            patterns = [p for p in patterns if p.get("favorite")]

        # Sort by created_at descending (newest first)
        patterns.sort(key=lambda p: p.get("created_at", 0), reverse=True)
        return patterns

    def rename_pattern(self, pattern_id: str, new_name: str) -> bool:
        """Rename a pattern."""
        if pattern_id not in self._index["patterns"]:
            return False

        self._index["patterns"][pattern_id]["name"] = new_name
        self._index["patterns"][pattern_id]["updated_at"] = time.time()
        self._save_index()

        # Also update the individual file
        data = self.get_pattern(pattern_id)
        if data:
            data["meta"]["name"] = new_name
            pattern_file = os.path.join(self.library_dir, f"{pattern_id}.json")
            with open(pattern_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

        return True

    def set_category(self, pattern_id: str, category: str) -> bool:
        """Change a pattern's category."""
        if pattern_id not in self._index["patterns"]:
            return False

        # Auto-add new categories
        if category not in self._index["categories"]:
            self._index["categories"].append(category)

        self._index["patterns"][pattern_id]["category"] = category
        self._index["patterns"][pattern_id]["updated_at"] = time.time()
        self._save_index()
        return True

    def toggle_favorite(self, pattern_id: str) -> Optional[bool]:
        """Toggle favorite status. Returns new state or None if not found."""
        if pattern_id not in self._index["patterns"]:
            return None

        current = self._index["patterns"][pattern_id].get("favorite", False)
        self._index["patterns"][pattern_id]["favorite"] = not current
        self._index["patterns"][pattern_id]["updated_at"] = time.time()
        self._save_index()
        return not current

    def delete_pattern(self, pattern_id: str) -> bool:
        """Delete a pattern from the library."""
        if pattern_id not in self._index["patterns"]:
            return False

        # Remove file
        pattern_file = os.path.join(self.library_dir, f"{pattern_id}.json")
        if os.path.exists(pattern_file):
            os.remove(pattern_file)

        del self._index["patterns"][pattern_id]
        self._save_index()
        logger.info("Pattern deleted: %s", pattern_id)
        return True

    def get_categories(self) -> list:
        """Get all available categories."""
        return self._index.get("categories", DEFAULT_CATEGORIES)

    def add_category(self, name: str) -> bool:
        """Add a new category."""
        if name not in self._index["categories"]:
            self._index["categories"].append(name)
            self._save_index()
            return True
        return False
