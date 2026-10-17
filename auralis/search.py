"""YouTube search via yt-dlp flat extraction (no download)."""

import json
import shutil
import subprocess
from dataclasses import dataclass, asdict


@dataclass
class Track:
    video_id: str
    title: str
    duration: int
    channel: str

    @property
    def url(self):
        return f"https://www.youtube.com/watch?v={self.video_id}"

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(
            video_id=d["video_id"],
            title=d.get("title", "Unknown"),
            duration=int(d.get("duration") or 0),
            channel=d.get("channel", ""),
        )


def _fmt_duration(seconds: int) -> str:
    if seconds <= 0:
        return "--:--"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def format_duration(seconds: int) -> str:
    return _fmt_duration(seconds)


def yt_dlp_available() -> bool:
    return shutil.which("yt-dlp") is not None


def search(query: str, limit: int = 8):
    """Return a list of Track for a YouTube search query."""
    if not yt_dlp_available():
        raise RuntimeError("yt-dlp not found on PATH")

    cmd = [
        "yt-dlp",
        "--flat-playlist",
        "--dump-json",
        "--no-warnings",
        "--playlist-end",
        str(limit),
        f"ytsearch{limit}:{query}",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip().splitlines()[-1] if proc.stderr else "search failed")

    tracks = []
    for line in proc.stdout.splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        vid = entry.get("id")
        if not vid:
            continue
        tracks.append(
            Track(
                video_id=vid,
                title=entry.get("title") or "Untitled",
                duration=int(entry.get("duration") or 0),
                channel=entry.get("channel") or entry.get("uploader") or "",
            )
        )
    return tracks
