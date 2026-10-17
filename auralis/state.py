"""Persistent state: queue, favorites, settings."""

import json
import os
import sys
from .search import Track

APP_NAME = "auralis"


def state_dir() -> str:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        path = os.path.join(base, APP_NAME)
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
        path = os.path.join(base, APP_NAME)
    os.makedirs(path, exist_ok=True)
    return path


class State:
    def __init__(self):
        self.path = os.path.join(state_dir(), "state.json")
        self.queue: list[Track] = []
        self.favorites: list[Track] = []
        self.volume: int = 70
        self._load()

    def _load(self):
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return
        self.queue = [Track.from_dict(t) for t in data.get("queue", [])]
        self.favorites = [Track.from_dict(t) for t in data.get("favorites", [])]
        self.volume = int(data.get("volume", 70))

    def save(self):
        data = {
            "queue": [t.to_dict() for t in self.queue],
            "favorites": [t.to_dict() for t in self.favorites],
            "volume": self.volume,
        }
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, self.path)

    def toggle_favorite(self, track: Track) -> bool:
        """Returns True if track is now a favorite."""
        for i, t in enumerate(self.favorites):
            if t.video_id == track.video_id:
                del self.favorites[i]
                self.save()
                return False
        self.favorites.insert(0, track)
        self.save()
        return True

    def is_favorite(self, track: Track) -> bool:
        return any(t.video_id == track.video_id for t in self.favorites)
