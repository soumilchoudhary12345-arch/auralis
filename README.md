# Auralis 🌌

**Featherweight YouTube music player that lives in your Windows system tray.**

No Electron. No browser window. No 500 MB RAM tax. Auralis is a free, open-source
music player built on a headless [mpv](https://mpv.io) daemon and
[yt-dlp](https://github.com/yt-dlp/yt-dlp) search — inspired by
[OmaOpus](https://github.com/MaenExists/omaopus) for Omarchy, ported to Windows.

## Features

- **Tray-native** — a music-note icon in your system tray; the UI only appears when you ask for it
- **Instant search** — type a query, get YouTube results in under a second, double-click to play
- **Queue** — press `Q` on a search result to queue it; playback continues back-to-back
- **Headless daemon** — audio keeps playing while every window stays closed; mpv does the heavy lifting
- **Persistent state** — queue, favorites-ready state file, and volume saved between launches
- **Free & open source** — MIT licensed, no accounts, no telemetry

## Requirements

| Dependency | Why |
|---|---|
| [mpv](https://mpv.io) | audio engine (must be on `PATH`) |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | YouTube search & stream resolution |
| Python 3.10+ | runtime |

### Install dependencies (Windows)

```powershell
winget install mpv.mpv
winget install yt-dlp.yt-dlp
pip install -r requirements.txt
```

## Run

```powershell
python -m auralis
```

- **Double-click / Enter** on a search result → play now
- **Q** → add to queue
- Tray menu: Search, Play/Pause, Next, Stop, Quit

## How it works

```
┌────────────┐   JSON IPC (named pipe)   ┌──────────┐   network   ┌─────────┐
│  Tray UI   │ ◄──────────────────────► │ mpv daemon │ ◄─────────► │ YouTube │
│ (pystray + │                          │ (no video) │             │         │
│  tkinter)  │      yt-dlp search       └──────────┘             └─────────┘
└────────────┘ ◄──────────────────────────────┘
```

1. Auralis spawns `mpv --no-video --input-ipc-server=\\.\pipe\auralis`
2. Search queries run `yt-dlp --flat-playlist ytsearchN:` — metadata only, nothing downloads
3. Selected tracks are fed to mpv via `loadfile`; state is persisted to `%APPDATA%\auralis\state.json`

## Building a standalone .exe (optional)

```powershell
pip install pyinstaller
powershell -File scripts/build.ps1
```

Output lands in `dist/Auralis.exe` (one-file, windowed). Ship `mpv.exe` and
`yt-dlp.exe` alongside it or require them on PATH.

## Cost

**₹0.** Everything is free software; no hosting, no API keys, no subscriptions.

## License

[MIT](LICENSE) — do whatever, credit appreciated.

## Credits

- Inspired by [OmaOpus](https://github.com/MaenExists/omaopus) (Omarchy plugin)
- Powered by [mpv](https://mpv.io) and [yt-dlp](https://github.com/yt-dlp/yt-dlp)
