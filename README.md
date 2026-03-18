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
┌─────────────────────┐     ┌──────────────────────┐
│   Menu Bar (rumps)   │────▶│   API (FastAPI)       │
│   menubar.py         │     │   main.py             │
│                      │     │                        │
│  - Health check /5s  │     │  GET  /health          │
│  - Start/Stop        │     │  GET  /version         │
│  - Update check      │     │  GET  /voices          │
│  - Open docs         │     │  POST /tts             │
└─────────────────────┘     └──────────┬───────────┘
                                        │
                                        ▼
                              ┌──────────────────┐
                              │   macOS `say`     │
                              │   + `afconvert`   │
                              └──────────────────┘
```

- **Menu Bar** y **API** corren como procesos independientes gestionados por `launchd`
- La API escucha solo en `127.0.0.1` (loopback) por seguridad
- CORS habilitado para integracion con aplicaciones web locales

## Licencia

MIT
