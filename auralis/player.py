"""mpv JSON IPC controller.

Spawns a headless mpv instance and talks to it over a local IPC endpoint:
named pipe on Windows, unix socket elsewhere.
"""

import json
import os
import socket
import subprocess
import sys
import threading
import time

IS_WINDOWS = sys.platform == "win32"
PIPE_NAME = r"\\.\pipe\auralis"
SOCKET_PATH = os.path.join(
    os.environ.get("TMPDIR") or os.environ.get("TEMP") or "/tmp", "auralis-mpv.sock"
)


class MpvError(RuntimeError):
    pass


class MpvPlayer:
    def __init__(self, volume=70):
        self._proc = None
        self._sock = None
        self._lock = threading.Lock()
        self._request_id = 0
        self._volume = volume

    # -- lifecycle ---------------------------------------------------------

    def start(self):
        if IS_WINDOWS:
            endpoint = PIPE_NAME
        else:
            if os.path.exists(SOCKET_PATH):
                os.unlink(SOCKET_PATH)
            endpoint = SOCKET_PATH

        cmd = [
            "mpv",
            "--no-video",
            "--no-terminal",
            "--really-quiet",
            "--idle=yes",
            f"--input-ipc-server={endpoint}",
            f"--volume={self._volume}",
        ]
        if IS_WINDOWS:
            self._proc = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            self._proc = subprocess.Popen(cmd)

        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                self._connect(endpoint)
                self._request(["get_property", "pause"])
                return
            except OSError:
                time.sleep(0.1)
        raise MpvError("Could not connect to mpv IPC endpoint")

    def quit(self):
        try:
            self._request(["quit"])
        except OSError:
            pass
        if self._proc:
            try:
                self._proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._close()

    # -- transport ---------------------------------------------------------

    def _connect(self, endpoint):
        if IS_WINDOWS:
            import win32file
            import win32pipe

            handle = win32file.CreateFile(
                endpoint,
                win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                0,
                None,
                win32pipe.OPEN_EXISTING,
                0,
                None,
            )
            self._sock = ("win32", handle)
        else:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(endpoint)
            self._sock = ("unix", sock)

    def _close(self):
        if not self._sock:
            return
        kind, obj = self._sock
        try:
            if kind == "win32":
                import win32file

                win32file.CloseHandle(obj)
            else:
                obj.close()
        except OSError:
            pass
        self._sock = None

    def _raw_write(self, data: bytes):
        kind, obj = self._sock
        if kind == "win32":
            import win32file

            win32file.WriteFile(obj, data)
        else:
            obj.sendall(data)

    def _raw_read(self, bufsize=4096) -> bytes:
        kind, obj = self._sock
        if kind == "win32":
            import win32file

            _, data = win32file.ReadFile(obj, bufsize)
            return bytes(data)
        return obj.recv(bufsize)

    def _request(self, command, timeout=5.0):
        with self._lock:
            if not self._sock:
                raise MpvError("IPC not connected")
            self._request_id += 1
            rid = self._request_id
            payload = json.dumps({"command": command, "request_id": rid}).encode() + b"\n"
            self._raw_write(payload)

            deadline = time.time() + timeout
            buffer = b""
            while time.time() < deadline:
                try:
                    buffer += self._raw_read()
                except OSError as exc:
                    raise MpvError(f"IPC read failed: {exc}") from exc
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    if not line.strip():
                        continue
                    try:
                        msg = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if msg.get("request_id") != rid:
                        continue
                    if "error" in msg and msg["error"] != "success":
                        raise MpvError(f"{command[0]}: {msg['error']}")
                    return msg.get("data")
            raise MpvError(f"IPC timeout for {command[0]}")

    # -- public API --------------------------------------------------------

    def load(self, url, replace=True):
        mode = "replace" if replace else "append-play"
        self._request(["loadfile", url, mode])

    def append(self, url):
        self._request(["loadfile", url, "append"])

    def pause(self, value=True):
        self._request(["set_property", "pause", bool(value)])

    def toggle_pause(self):
        paused = self.get_property("pause", False)
        self.pause(not paused)

    def stop(self):
        self._request(["stop"])

    def next(self):
        self._request(["playlist-next", "force"])

    def prev(self):
        self._request(["playlist-prev", "force"])

    def seek(self, seconds):
        self._request(["seek", seconds, "relative"])

    def set_volume(self, volume):
        self._volume = max(0, min(150, int(volume)))
        self._request(["set_property", "volume", self._volume])

    def get_property(self, name, default=None):
        try:
            value = self._request(["get_property", name], timeout=2.0)
            return default if value is None else value
        except MpvError:
            return default

    @property
    def is_playing(self):
        if not self._sock:
            return False
        return not self.get_property("pause", True) and self.get_property(
            "playlist-pos", -1
        ) >= 0

    @property
    def media_title(self):
        return self.get_property("media-title", "") or ""

    @property
    def playlist_count(self):
        return self.get_property("playlist-count", 0) or 0
