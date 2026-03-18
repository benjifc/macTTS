import asyncio
import os
import re
import tempfile
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

VERSION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "VERSION")
with open(VERSION_FILE) as _f:
    VERSION = _f.read().strip()

app = FastAPI(
    title="MacTTS",
    version=VERSION,
    description="REST API para Text-to-Speech usando el comando say de macOS",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cache de voces
_voices_cache: list[dict] | None = None


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000, description="Texto a sintetizar")
    voice: str | None = Field(None, description="Nombre de la voz (ver GET /voices)")
    rate: int | None = Field(None, ge=1, le=700, description="Palabras por minuto")
    format: Literal["aiff", "wav"] = Field("aiff", description="Formato de audio de salida")


class OpenAISpeechRequest(BaseModel):
    """Modelo compatible con POST /v1/audio/speech de OpenAI."""
    model: str = Field("tts-1", description="Modelo TTS (ignorado, usa say de macOS)")
    input: str = Field(..., min_length=1, max_length=10000, description="Texto a sintetizar")
    voice: str = Field("Mónica", description="Nombre de voz macOS (ver GET /voices)")
    response_format: Literal["mp3", "opus", "aac", "flac", "wav", "pcm"] = Field("mp3", description="Formato de audio")
    speed: float = Field(1.0, ge=0.25, le=4.0, description="Velocidad de habla (1.0 = normal)")


OPENAI_MEDIA_TYPES: dict[str, str] = {
    "mp3": "audio/mpeg",
    "opus": "audio/ogg",
    "aac": "audio/aac",
    "flac": "audio/flac",
    "wav": "audio/wav",
    "pcm": "audio/L16",
}


class VoiceInfo(BaseModel):
    name: str
    locale: str
    sample: str


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/version")
async def version():
    return {"version": VERSION}


async def _get_voices() -> list[dict]:
    global _voices_cache
    if _voices_cache is not None:
        return _voices_cache

    process = await asyncio.create_subprocess_exec(
        "say", "-v", "?",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise HTTPException(status_code=500, detail=f"Error listando voces: {stderr.decode()}")

    voices = []
    for line in stdout.decode().splitlines():
        match = re.match(r"^(.+?)\s{2,}(\S+)\s+#\s+(.+)$", line)
        if match:
            voices.append({
                "name": match.group(1).strip(),
                "locale": match.group(2),
                "sample": match.group(3),
            })
    _voices_cache = voices
    return voices


@app.get("/voices", response_model=list[VoiceInfo])
async def list_voices():
    return await _get_voices()


async def _run_say(text: str, output_path: str, voice: str | None = None, rate: int | None = None):
    cmd = ["say"]
    if voice:
        cmd.extend(["-v", voice])
    if rate:
        cmd.extend(["-r", str(rate)])
    cmd.extend(["-o", output_path])
    cmd.append(text)

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60)
    except asyncio.TimeoutError:
        process.kill()
        raise HTTPException(status_code=504, detail="La síntesis de voz excedió el tiempo límite")

    if process.returncode != 0:
        raise HTTPException(status_code=500, detail=f"Error en síntesis: {stderr.decode()}")


async def _convert_to_wav(aiff_path: str) -> str:
    """Convierte AIFF a WAV usando afconvert (legacy, usado por POST /tts)."""
    wav_path = aiff_path.replace(".aiff", ".wav")
    process = await asyncio.create_subprocess_exec(
        "afconvert", "-f", "WAVE", "-d", "LEI16", aiff_path, wav_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise HTTPException(status_code=500, detail=f"Error convirtiendo audio: {stderr.decode()}")
    os.unlink(aiff_path)
    return wav_path


async def _convert_format(aiff_path: str, target_format: str) -> str:
    """Convierte AIFF a cualquier formato soportado por OpenAI API."""
    if target_format == "aiff":
        return aiff_path

    output_path = aiff_path.replace(".aiff", f".{target_format}")

    if target_format == "wav":
        cmd = ["afconvert", "-f", "WAVE", "-d", "LEI16", aiff_path, output_path]
    else:
        # ffmpeg para mp3, opus, aac, flac, pcm
        format_args: dict[str, list[str]] = {
            "mp3": ["-codec:a", "libmp3lame", "-b:a", "192k"],
            "opus": ["-codec:a", "libopus", "-b:a", "128k"],
            "aac": ["-codec:a", "aac", "-b:a", "192k"],
            "flac": ["-codec:a", "flac"],
            "pcm": ["-f", "s16le", "-acodec", "pcm_s16le", "-ar", "24000"],
        }
        cmd = ["/opt/homebrew/bin/ffmpeg", "-y", "-i", aiff_path] + format_args[target_format] + [output_path]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise HTTPException(status_code=500, detail=f"Error convirtiendo audio: {stderr.decode()}")

    os.unlink(aiff_path)
    return output_path


# ---------------------------------------------------------------------------
# Endpoints originales (retrocompatibles)
# ---------------------------------------------------------------------------


@app.post("/tts")
async def text_to_speech(request: TTSRequest):
    # Validar voz si se especificó
    if request.voice:
        voices = await _get_voices()
        voice_names = [v["name"] for v in voices]
        if request.voice not in voice_names:
            raise HTTPException(
                status_code=400,
                detail=f"Voz '{request.voice}' no encontrada. Usa GET /voices para ver las disponibles.",
            )

    # Crear archivo temporal
    tmp = tempfile.NamedTemporaryFile(prefix="mactts_", suffix=".aiff", delete=False)
    tmp_path = tmp.name
    tmp.close()

    # Sintetizar
    await _run_say(request.text, tmp_path, request.voice, request.rate)

    # Convertir formato si es necesario
    if request.format == "wav":
        tmp_path = await _convert_to_wav(tmp_path)
        media_type = "audio/wav"
        filename = "speech.wav"
    else:
        media_type = "audio/aiff"
        filename = "speech.aiff"

    return FileResponse(
        path=tmp_path,
        media_type=media_type,
        filename=filename,
        background=BackgroundTask(os.unlink, tmp_path),
    )


# ---------------------------------------------------------------------------
# Endpoints OpenAI-compatible  (POST /v1/audio/speech, GET /v1/models)
# ---------------------------------------------------------------------------


@app.post("/v1/audio/speech")
async def openai_speech(request: OpenAISpeechRequest):
    """Endpoint compatible con OpenAI TTS API."""
    voice = request.voice

    # Convertir speed (1.0 = normal) a rate en WPM (default macOS ~175 WPM)
    rate = int(175 * request.speed) if request.speed != 1.0 else None

    # Validar que la voz existe
    voices = await _get_voices()
    voice_names = [v["name"] for v in voices]
    if voice not in voice_names:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "message": f"Voice '{request.voice}' not found. Use GET /voices for available voices.",
                    "type": "invalid_request_error",
                    "code": "voice_not_found",
                }
            },
        )

    # Sintetizar como AIFF
    tmp = tempfile.NamedTemporaryFile(prefix="mactts_oai_", suffix=".aiff", delete=False)
    tmp_path = tmp.name
    tmp.close()

    await _run_say(request.input, tmp_path, voice, rate)

    # Convertir al formato solicitado
    output_path = await _convert_format(tmp_path, request.response_format)

    return FileResponse(
        path=output_path,
        media_type=OPENAI_MEDIA_TYPES[request.response_format],
        filename=f"speech.{request.response_format}",
        background=BackgroundTask(os.unlink, output_path),
    )


@app.get("/v1/models")
async def openai_list_models():
    """Lista modelos disponibles (compatible con OpenAI API)."""
    return {
        "object": "list",
        "data": [
            {"id": "tts-1", "object": "model", "created": 1699000000, "owned_by": "mactts"},
            {"id": "tts-1-hd", "object": "model", "created": 1699000000, "owned_by": "mactts"},
        ],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
