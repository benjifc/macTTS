# MacTTS

A local REST API that turns macOS's built-in speech engine into an HTTP
service. MacTTS wraps the native `say` command so any app, script, or
automation can generate speech audio from text over HTTP — no cloud, no API
keys, no per-character billing.

It ships with a menu bar app for start/stop and one-click self-updates, and
exposes an **OpenAI-compatible** endpoint so it can be dropped into any tool
that supports a custom `baseUrl`.

## Features

- **Native macOS voices** — uses the system `say` command and every voice
  installed on your Mac (English, Spanish, Japanese, and dozens more).
- **Simple REST API** — `POST /tts` returns an audio file for a given text.
- **OpenAI-compatible API** — `POST /v1/audio/speech` and `GET /v1/models`
  work as a drop-in replacement for the OpenAI TTS API.
- **Multiple output formats** — AIFF, WAV, MP3, Opus, AAC, FLAC, and PCM.
- **Menu bar app** — live status, version display, start/stop, one-click
  updates, and a shortcut to the interactive docs.
- **Self-updating** — checks GitHub for new releases and updates in place,
  preserving your virtual environment and logs.
- **Local by default** — the API binds to `127.0.0.1` (loopback) only.
- **Interactive docs** — auto-generated Swagger UI at `/docs`.

## Stack

| Layer      | Technology                                        |
| ---------- | ------------------------------------------------- |
| API        | [FastAPI](https://fastapi.tiangolo.com/) + [Uvicorn](https://www.uvicorn.org/) |
| Menu bar   | [rumps](https://github.com/jaredks/rumps) + [pyobjc](https://pyobjc.readthedocs.io/) |
| TTS engine | macOS `say`                                       |
| Conversion | `afconvert` (WAV) and `ffmpeg` (MP3/Opus/AAC/FLAC/PCM) |
| Service    | `launchd` (LaunchAgents)                          |

## Requirements

- macOS 13 (Ventura) or later
- Python 3.10+
- [`ffmpeg`](https://ffmpeg.org/) — only required for MP3, Opus, AAC, FLAC,
  and PCM output (`brew install ffmpeg`). AIFF and WAV work without it.

## Installation

```bash
curl -fsSL https://raw.githubusercontent.com/benjifc/macTTS/main/install.sh | bash
```

The installer:

1. Downloads MacTTS to `~/.local/share/mactts/`.
2. Creates a Python virtual environment and installs the dependencies.
3. Registers two LaunchAgents (the API and the menu bar app).
4. Starts the service automatically and on every login.

Once installed, the service runs at `http://127.0.0.1:8000` and the
interactive documentation is available at
[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

## Menu bar app

A small icon lives in the macOS menu bar:

| Icon                                            | Meaning          |
| ----------------------------------------------- | ---------------- |
| ![active](assets/menubar_active.png) active     | Service running  |
| ![muted](assets/menubar_muted.png) muted        | Service stopped  |

Clicking it opens a menu with the service status, installed version,
start/stop controls, a **Check for Updates** action (compares against GitHub
and updates with one click), and a shortcut to the API docs.

## API

Base URL: `http://127.0.0.1:8000`

| Method | Endpoint             | Description                                    |
| ------ | -------------------- | ---------------------------------------------- |
| GET    | `/health`            | Health check.                                  |
| GET    | `/version`           | Installed version.                             |
| GET    | `/voices`            | List every voice available on the system.      |
| POST   | `/tts`               | Synthesize text to audio (AIFF or WAV).        |
| POST   | `/v1/audio/speech`   | OpenAI-compatible speech synthesis.            |
| GET    | `/v1/models`         | OpenAI-compatible model list.                  |

### `GET /health`

```bash
curl http://127.0.0.1:8000/health
# {"status": "ok"}
```

### `GET /version`

```bash
curl http://127.0.0.1:8000/version
# {"version": "2.0.0"}
```

### `GET /voices`

Lists every voice installed on the system.

```bash
curl http://127.0.0.1:8000/voices
```

```json
[
  { "name": "Paulina",  "locale": "es_MX", "sample": "Hola, me llamo Paulina y soy una voz mexicana." },
  { "name": "Samantha", "locale": "en_US", "sample": "Hello, my name is Samantha. I am an American-English voice." }
]
```

### `POST /tts`

Synthesizes text to an audio file.

| Field    | Type    | Required | Default  | Description                          |
| -------- | ------- | -------- | -------- | ------------------------------------ |
| `text`   | string  | yes      | —        | Text to synthesize (1–10,000 chars). |
| `voice`  | string  | no       | system   | Voice name (see `GET /voices`).      |
| `rate`   | integer | no       | `220`    | Words per minute (1–700).            |
| `format` | string  | no       | `"aiff"` | `"aiff"` or `"wav"`.                 |

```bash
# Basic synthesis (default voice, AIFF)
curl -X POST http://127.0.0.1:8000/tts \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world"}' \
  -o output.aiff

# Specific voice, WAV
curl -X POST http://127.0.0.1:8000/tts \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world", "voice": "Samantha", "format": "wav"}' \
  -o output.wav

# Custom rate
curl -X POST http://127.0.0.1:8000/tts \
  -H "Content-Type: application/json" \
  -d '{"text": "Fast text", "voice": "Paulina", "rate": 300, "format": "wav"}' \
  -o fast.wav
```

Returns an audio file (`audio/aiff` or `audio/wav`).

## OpenAI-compatible API

MacTTS exposes endpoints that mirror the
[OpenAI TTS API](https://platform.openai.com/docs/api-reference/audio/createSpeech),
so it works as a drop-in replacement in any application that accepts a custom
`baseUrl` (LiteLLM, OpenClaw, and similar).

### `POST /v1/audio/speech`

| Field             | Type   | Required | Default    | Description                                            |
| ----------------- | ------ | -------- | ---------- | ------------------------------------------------------ |
| `model`           | string | yes      | `"tts-1"`  | Accepted but ignored — always uses macOS `say`.        |
| `input`           | string | yes      | —          | Text to synthesize (1–10,000 chars).                   |
| `voice`           | string | yes      | `"Mónica"` | macOS voice name (see `GET /voices`).                  |
| `response_format` | string | no       | `"mp3"`    | `mp3`, `opus`, `aac`, `flac`, `wav`, or `pcm`.         |
| `speed`           | float  | no       | `1.0`      | Speech speed 0.25–4.0 (`1.0` ≈ 220 WPM).               |

> `voice` takes a macOS voice name directly. Call `GET /voices` to see what's
> installed (for example `"Samantha"`, `"Mónica"`, `"Paulina"`, `"Daniel"`,
> `"Kyoko"`).

```bash
# Default voice
curl -X POST http://127.0.0.1:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"model": "tts-1", "input": "Hello world", "voice": "Mónica"}' \
  -o output.mp3

# WAV output
curl -X POST http://127.0.0.1:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"model": "tts-1", "input": "Hello world", "voice": "Mónica", "response_format": "wav"}' \
  -o output.wav

# Faster speech
curl -X POST http://127.0.0.1:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"model": "tts-1", "input": "Fast text", "voice": "Paulina", "speed": 1.5}' \
  -o fast.mp3
```

Returns an audio file in the requested format with the matching `Content-Type`.

### `GET /v1/models`

```bash
curl http://127.0.0.1:8000/v1/models
```

```json
{
  "object": "list",
  "data": [
    { "id": "tts-1",    "object": "model", "created": 1699000000, "owned_by": "mactts" },
    { "id": "tts-1-hd", "object": "model", "created": 1699000000, "owned_by": "mactts" }
  ]
}
```

## OpenClaw integration

Because of the OpenAI compatibility, MacTTS can act as a TTS provider for
[OpenClaw](https://www.getopenclaw.ai/). Add the following to your
`openclaw.json`:

```json
{
  "messages": {
    "tts": {
      "auto": "inbound",
      "mode": "final",
      "provider": "openai",
      "maxTextLength": 4000,
      "timeoutMs": 30000,
      "openai": {
        "baseUrl": "http://<YOUR_IP>:8000/v1",
        "apiKey": "not-needed",
        "model": "mactts",
        "voice": "Mónica"
      }
    }
  }
}
```

> Replace `<YOUR_IP>` with your Mac's local IP (for example `192.168.1.103`),
> or use `127.0.0.1` if OpenClaw runs on the same machine.
>
> To reach MacTTS from other devices on your network, the service must listen
> on `0.0.0.0` instead of `127.0.0.1`. Run it manually (see
> [Development](#development)) or edit the LaunchAgent's `--host` argument.

## Updating

**From the menu bar:** click the icon → **Check for Updates**. If a new
version is available, an update option appears.

**From the terminal:**

```bash
curl -fsSL https://raw.githubusercontent.com/benjifc/macTTS/main/install.sh | bash -s -- --update
```

The update process compares the local version against GitHub, stops the
services, downloads the new code (preserving logs and the virtual
environment), refreshes dependencies, regenerates the LaunchAgents, and
restarts everything.

## Uninstalling

```bash
curl -fsSL https://raw.githubusercontent.com/benjifc/macTTS/main/install.sh | bash -s -- --uninstall
```

This removes the install directory (`~/.local/share/mactts/`), both
LaunchAgents (`com.mactts.service` and `com.mactts.menubar`), and the menu bar
icon. A standalone `uninstall.sh` is also included in the repository.

## Development

```bash
git clone https://github.com/benjifc/macTTS.git
cd macTTS
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# API (http://127.0.0.1:8000, with hot reload)
python main.py

# Menu bar app (in a second terminal)
python menubar.py
```

### Project structure

```
macTTS/
├── main.py                    # REST API (FastAPI + Uvicorn)
├── menubar.py                 # Menu bar app (rumps)
├── install.sh                 # Installer / updater / uninstaller
├── uninstall.sh               # Standalone uninstaller
├── requirements.txt           # Python dependencies
├── VERSION                    # Current version (semver)
├── com.mactts.service.plist   # Reference LaunchAgent (for development)
├── assets/                    # Menu bar icons
└── README.md
```

### Architecture

```
┌──────────────────────┐     ┌──────────────────────────────┐
│  Menu Bar (rumps)    │────▶│  API (FastAPI)               │
│  menubar.py          │     │  main.py                     │
│                      │     │                              │
│  - Health check /5s  │     │  GET  /health                │
│  - Start / Stop      │     │  GET  /version               │
│  - Update check      │     │  GET  /voices                │
│  - Open API docs     │     │  POST /tts                   │
└──────────────────────┘     │                              │
                             │  OpenAI-compatible:          │
┌──────────────────────┐     │  POST /v1/audio/speech       │
│  Apps / OpenClaw     │────▶│  GET  /v1/models             │
│  (provider: openai)  │     └───────────────┬──────────────┘
└──────────────────────┘                     │
                                             ▼
                                  ┌──────────────────────┐
                                  │  macOS `say`         │
                                  │  + afconvert         │
                                  │  + ffmpeg            │
                                  └──────────────────────┘
```

- The menu bar and the API run as independent processes managed by `launchd`.
- The API listens only on `127.0.0.1` (loopback) by default.
- CORS is enabled for integration with local web applications.

### Releasing a new version

1. Edit `VERSION` with the new semver value (for example `2.1.0`).
2. Commit and push to `main`.
3. Users update from the menu bar or with `--update`.

## License

Released under the [MIT License](LICENSE). Copyright © 2026
Benjamin Fernandez Carrasco.
