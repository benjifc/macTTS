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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
