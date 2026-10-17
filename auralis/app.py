"""Auralis app: tray icon + search window glue."""

import threading
import tkinter as tk
from tkinter import ttk, messagebox

from . import APP_NAME, __version__
from .player import MpvPlayer, MpvError
from .search import search, format_duration, Track
from .state import State

try:
    import pystray
    from PIL import Image, ImageDraw
    HAVE_TRAY = True
except ImportError:
    HAVE_TRAY = False


def _make_icon_image(color="#7c5cff"):
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([2, 2, 62, 62], fill=color)
    # simple note glyph
    d.ellipse([18, 36, 30, 48], fill="white")
    d.rectangle([28, 20, 32, 42], fill="white")
    d.polygon([(28, 20), (44, 16), (44, 24), (28, 28)], fill="white")
    return img


class Auralis:
    def __init__(self):
        self.state = State()
        self.player = MpvPlayer(volume=self.state.volume)
        self._tray = None
        self._search_win = None

    # -- playback ----------------------------------------------------------

    def play_track(self, track: Track, clear_queue=False):
        if clear_queue:
            self.state.queue = []
        self.state.save()
        try:
            self.player.load(track.url, replace=True)
        except MpvError as e:
            self._notify("Playback error", str(e))

    def queue_track(self, track: Track):
        self.state.queue.append(track)
        self.state.save()
        if not self.player.is_playing:
            self.play_next()

    def play_next(self):
        if self.state.queue:
            track = self.state.queue.pop(0)
            self.state.save()
            self.play_track(track)

    def toggle_play(self):
        try:
            self.player.toggle_pause()
        except MpvError:
            if self.state.queue:
                self.play_next()

    def stop(self):
        try:
            self.player.stop()
        except MpvError:
            pass

    # -- search UI (runs in its own thread with its own Tk loop) -----------

    def open_search(self):
        if self._search_win is not None:
            try:
                self._search_win.lift()
                return
            except tk.TclError:
                self._search_win = None
        threading.Thread(target=self._search_thread, daemon=True).start()

    def _search_thread(self):
        root = tk.Tk()
        root.title(f"{APP_NAME} — Search")
        root.geometry("520x420")
        root.configure(bg="#12121a")
        self._search_win = root

        style = ttk.Style(root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TEntry", fieldbackground="#1e1e2a", foreground="#eee")
        style.configure("TButton", background="#7c5cff", foreground="white")

        frame = ttk.Frame(root, padding=10)
        frame.pack(fill="both", expand=True)

        entry = ttk.Entry(frame)
        entry.pack(fill="x", pady=(0, 8))
        entry.focus_set()

        listbox = tk.Listbox(
            frame, bg="#1e1e2a", fg="#ddd", selectbackground="#7c5cff",
            highlightthickness=0, font=("Consolas", 10)
        )
        listbox.pack(fill="both", expand=True)

        status = ttk.Label(frame, text="Type a query, press Enter")
        status.pack(anchor="w", pady=(6, 0))

        results: list[Track] = []

        def do_search(_event=None):
            q = entry.get().strip()
            if not q:
                return
            status.config(text="Searching…")
            listbox.delete(0, "end")
            root.update_idletasks()
            threading.Thread(target=lambda: _run_search(q), daemon=True).start()

        def _run_search(q):
            try:
                found = search(q)
            except Exception as e:
                found = []
                root.after(0, lambda: status.config(text=f"Error: {e}"))
                return
            root.after(0, lambda: _show(found))

        def _show(found):
            nonlocal results
            results = found
            listbox.delete(0, "end")
            for t in found:
                listbox.insert(
                    "end", f"{format_duration(t.duration):>7}  {t.title}  — {t.channel}"
                )
            status.config(text=f"{len(found)} results — double-click to play, Q to queue")

        def play_selected(_event=None):
            sel = listbox.curselection()
            if not sel:
                return
            self.play_track(results[sel[0]])
            status.config(text=f"▶ {results[sel[0]].title}")

        def queue_selected(_event=None):
            sel = listbox.curselection()
            if not sel:
                return
            self.queue_track(results[sel[0]])
            status.config(text=f"queued: {results[sel[0]].title}")

        entry.bind("<Return>", do_search)
        listbox.bind("<Double-Button-1>", play_selected)
        listbox.bind("<q>", queue_selected)
        listbox.bind("<Q>", queue_selected)

        btns = ttk.Frame(frame)
        btns.pack(fill="x", pady=(8, 0))
        ttk.Button(btns, text="Play", command=play_selected).pack(side="left")
        ttk.Button(btns, text="Queue", command=queue_selected).pack(side="left", padx=6)
        ttk.Button(btns, text="Close", command=root.destroy).pack(side="right")

        root.mainloop()
        self._search_win = None

    # -- tray --------------------------------------------------------------

    def _tray_menu(self):
        tracks = " · ".join(t.title for t in self.state.favorites[:5]) or "none"
        return pystray.Menu(
            pystray.MenuItem("Search music…", self._tray_action("search"), default=True),
            pystray.MenuItem("Play/Pause", self._tray_action("toggle")),
            pystray.MenuItem("Next", self._tray_action("next")),
            pystray.MenuItem("Stop", self._tray_action("stop")),
            pystray.MenuItem(f"Favorites: {tracks}", None, enabled=False),
            pystray.MenuItem("Quit", self._tray_action("quit")),
        )

    def _tray_action(self, name):
        def handler(icon, item):
            if name == "search":
                self.open_search()
            elif name == "toggle":
                self.toggle_play()
            elif name == "next":
                self.play_next()
            elif name == "stop":
                self.stop()
            elif name == "quit":
                self.shutdown(icon)
        return handler

    def _refresh_tray(self, icon):
        playing = self.player.is_playing
        title = self.player.media_title or APP_NAME
        icon.title = f"{APP_NAME} — {title}" if playing else APP_NAME
        icon.icon = _make_icon_image("#22c55e" if playing else "#7c5cff")

    def _notify(self, title, message):
        if self._tray:
            self._tray.notify(message, title)

    def shutdown(self, icon=None):
        try:
            self.player.quit()
        except MpvError:
            pass
        self.state.save()
        if icon:
            icon.stop()

    def run(self):
        self.player.start()
        if not HAVE_TRAY:
            print("pystray/Pillow not installed — running headless search UI only")
            self.open_search()
            threading.Event().wait()
            return
        self._tray = pystray.Icon(
            APP_NAME, _make_icon_image(), APP_NAME, menu=self._tray_menu()
        )
        threading.Thread(target=self._tray.run, daemon=True).start()
        # periodically refresh tooltip/icon state
        while True:
            try:
                self._refresh_tray(self._tray)
            except Exception:
                pass
            threading.Event().wait(2)
