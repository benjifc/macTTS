# MacTTS

REST API para Text-to-Speech nativa de macOS con icono en la barra de menu y actualizaciones automaticas.

MacTTS expone el motor de sintesis de voz de macOS (`say`) como una API REST moderna, permitiendo a cualquier aplicacion generar audio a partir de texto via HTTP.

## Instalacion

```bash
curl -fsSL https://raw.githubusercontent.com/benjifc/macTTS/main/install.sh | bash
```

Esto:
- Descarga MacTTS en `~/.local/share/mactts/`
- Crea un entorno virtual Python con las dependencias
- Registra dos LaunchAgents (API + barra de menu)
- Inicia el servicio automaticamente

### Requisitos

- macOS 13+ (Ventura o superior)
- Python 3.10+

## Uso

Una vez instalado, el servicio corre en `http://127.0.0.1:8000`. La documentacion interactiva esta en [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

### Barra de menu

Un icono aparece en la barra de menu de macOS:

| Icono | Significado |
|-------|-------------|
| 🔊 | Servicio activo |
| 🔇 | Servicio detenido |

Al hacer click se muestra un menu con:
- **Estado** del servicio (activo/detenido)
- **Version** instalada
- **Iniciar / Detener** servicio
- **Buscar Actualizaciones** (compara con GitHub y actualiza con un click)
- **Abrir API Docs** (abre la documentacion Swagger en el navegador)
- **Salir**

## API

### `GET /health`

Health check del servicio.

```bash
curl http://127.0.0.1:8000/health
```

```json
{"status": "ok"}
```

### `GET /version`

Version instalada.

```bash
curl http://127.0.0.1:8000/version
```

```json
{"version": "1.0.0"}
```

### `GET /voices`

Lista todas las voces disponibles en el sistema.

```bash
curl http://127.0.0.1:8000/voices
```

```json
[
  {
    "name": "Paulina",
    "locale": "es_MX",
    "sample": "Hola, me llamo Paulina y soy una voz mexicana."
  },
  {
    "name": "Samantha",
    "locale": "en_US",
    "sample": "Hello, my name is Samantha. I am an American-English voice."
  }
]
```

### `POST /tts`

Sintetiza texto a audio.

**Parametros (JSON body):**

| Campo | Tipo | Requerido | Descripcion |
|-------|------|-----------|-------------|
| `text` | string | Si | Texto a sintetizar (1-10,000 caracteres) |
| `voice` | string | No | Nombre de la voz (ver `GET /voices`) |
| `rate` | integer | No | Velocidad en palabras por minuto (1-700) |
| `format` | string | No | `"aiff"` (default) o `"wav"` |

**Ejemplos:**

```bash
# Sintesis basica (voz por defecto, formato AIFF)
curl -X POST http://127.0.0.1:8000/tts \
  -H "Content-Type: application/json" \
  -d '{"text": "Hola mundo"}' \
  -o salida.aiff

# Voz especifica en formato WAV
curl -X POST http://127.0.0.1:8000/tts \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world", "voice": "Samantha", "format": "wav"}' \
  -o salida.wav

# Con velocidad personalizada
curl -X POST http://127.0.0.1:8000/tts \
  -H "Content-Type: application/json" \
  -d '{"text": "Texto rapido", "voice": "Paulina", "rate": 300, "format": "wav"}' \
  -o rapido.wav
```

**Respuesta:** archivo de audio (`audio/aiff` o `audio/wav`).

---

## API compatible con OpenAI

MacTTS expone endpoints 100% compatibles con la [API de TTS de OpenAI](https://platform.openai.com/docs/api-reference/audio/createSpeech), lo que permite usarlo como drop-in replacement en cualquier aplicacion que soporte un `baseUrl` personalizado (OpenClaw, LiteLLM, etc.).

### `POST /v1/audio/speech`

Genera audio a partir de texto. Compatible con el formato de OpenAI.

**Parametros (JSON body):**

| Campo | Tipo | Requerido | Default | Descripcion |
|-------|------|-----------|---------|-------------|
| `model` | string | Si | `"tts-1"` | Modelo TTS (aceptado pero ignorado, siempre usa `say` de macOS) |
| `input` | string | Si | — | Texto a sintetizar (1-10,000 caracteres) |
| `voice` | string | Si | `"Samantha"` | Nombre de voz macOS (ver `GET /voices`) |
| `response_format` | string | No | `"mp3"` | Formato: `mp3`, `opus`, `aac`, `flac`, `wav`, `pcm` |
| `speed` | float | No | `1.0` | Velocidad (0.25 - 4.0, donde 1.0 = ~175 WPM) |

> Usa directamente los nombres de voz de macOS (`say`). Consulta `GET /voices` para ver todas las disponibles en tu sistema (ej: `"Samantha"`, `"Mónica"`, `"Paulina"`, `"Daniel"`, `"Kyoko"`).

**Ejemplos:**

```bash
# Voz por defecto (Samantha)
curl -X POST http://127.0.0.1:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"model": "tts-1", "input": "Hello world", "voice": "Samantha"}' \
  -o salida.mp3

# Voz en español
curl -X POST http://127.0.0.1:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"model": "tts-1", "input": "Hola mundo", "voice": "Mónica", "response_format": "wav"}' \
  -o salida.wav

# Con velocidad personalizada
curl -X POST http://127.0.0.1:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"model": "tts-1", "input": "Texto rapido", "voice": "Paulina", "speed": 1.5}' \
  -o rapido.mp3
```

**Respuesta:** archivo de audio en el formato solicitado con el `Content-Type` correspondiente.

### `GET /v1/models`

Lista los modelos TTS disponibles (compatible con OpenAI).

```bash
curl http://127.0.0.1:8000/v1/models
```

```json
{
  "object": "list",
  "data": [
    {"id": "tts-1", "object": "model", "created": 1699000000, "owned_by": "mactts"},
    {"id": "tts-1-hd", "object": "model", "created": 1699000000, "owned_by": "mactts"}
  ]
}
```

---

## Integracion con OpenClaw

MacTTS se puede usar como proveedor de TTS en [OpenClaw](https://www.getopenclaw.ai/) gracias a la compatibilidad con la API de OpenAI. Anade lo siguiente a tu `openclaw.json`:

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
        "baseUrl": "http://<TU_IP>:8000/v1",
        "apiKey": "not-needed",
        "model": "mactts",
        "voice": "Mónica"
      }
    }
  }
}
```

> **Nota:** Sustituye `<TU_IP>` por la IP local de tu Mac (ej: `192.168.1.103`). Si OpenClaw corre en la misma maquina, puedes usar `127.0.0.1`.

> **Importante:** Para que MacTTS sea accesible desde otros dispositivos de tu red local, el servicio debe escuchar en `0.0.0.0` en vez de `127.0.0.1`. Consulta la seccion de [Desarrollo](#desarrollo) para ejecutarlo manualmente, o modifica el LaunchAgent para cambiar el host.

## Actualizacion

### Desde la barra de menu

Click en el icono 🔊 → **Buscar Actualizaciones**. Si hay una nueva version disponible, aparecera la opcion para actualizar con un click.

### Desde terminal

```bash
curl -fsSL https://raw.githubusercontent.com/benjifc/macTTS/main/install.sh | bash -s -- --update
```

El proceso de actualizacion:
1. Compara la version local con la publicada en GitHub
2. Si hay una nueva version, detiene los servicios
3. Descarga el nuevo codigo (preservando logs y entorno virtual)
4. Actualiza dependencias
5. Regenera los LaunchAgents
6. Reinicia todo automaticamente

## Desinstalacion

```bash
curl -fsSL https://raw.githubusercontent.com/benjifc/macTTS/main/install.sh | bash -s -- --uninstall
```

Esto elimina:
- El directorio de instalacion (`~/.local/share/mactts/`)
- Los LaunchAgents (`com.mactts.service` y `com.mactts.menubar`)
- El icono de la barra de menu

## Desarrollo

### Ejecutar localmente

```bash
git clone https://github.com/benjifc/macTTS.git
cd macTTS
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# API
python main.py

# Barra de menu (en otra terminal)
python menubar.py
```

La API se ejecuta en `http://127.0.0.1:8000` con hot-reload habilitado.

### Estructura del proyecto

```
macTTS/
├── main.py                    # API REST (FastAPI + Uvicorn)
├── menubar.py                 # App de barra de menu (rumps)
├── install.sh                 # Instalador / actualizador / desinstalador
├── requirements.txt           # Dependencias Python
├── VERSION                    # Version actual (semver)
├── com.mactts.service.plist   # LaunchAgent de referencia (desarrollo)
└── README.md
```

### Publicar una nueva version

1. Edita el archivo `VERSION` con la nueva version (ej: `1.1.0`)
2. Haz commit y push a `main`
3. Los usuarios actualizan desde el menu bar o con `--update`

## Arquitectura

```
┌─────────────────────┐     ┌────────────────────────────┐
│   Menu Bar (rumps)   │────▶│   API (FastAPI)             │
│   menubar.py         │     │   main.py                   │
│                      │     │                              │
│  - Health check /5s  │     │  GET  /health                │
│  - Start/Stop        │     │  GET  /version               │
│  - Update check      │     │  GET  /voices                │
│  - Open docs         │     │  POST /tts                   │
└─────────────────────┘     │                              │
                             │  OpenAI-compatible:          │
┌─────────────────────┐     │  POST /v1/audio/speech       │
│  OpenClaw / Apps     │────▶│  GET  /v1/models             │
│  (provider: openai)  │     └──────────────┬───────────────┘
└─────────────────────┘                     │
                                             ▼
                                   ┌──────────────────┐
                                   │   macOS `say`     │
                                   │   + afconvert     │
                                   │   + ffmpeg        │
                                   └──────────────────┘
```

- **Menu Bar** y **API** corren como procesos independientes gestionados por `launchd`
- La API escucha solo en `127.0.0.1` (loopback) por seguridad
- CORS habilitado para integracion con aplicaciones web locales

## Licencia

MIT
