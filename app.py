import os
import re
import html
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import Response, JSONResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

import azure.cognitiveservices.speech as speechsdk


# ---------------------------
# Config
# ---------------------------
load_dotenv()

AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY")
AZURE_SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION")  # e.g. "eastus"

if not AZURE_SPEECH_KEY or not AZURE_SPEECH_REGION:
    raise RuntimeError("Missing AZURE_SPEECH_KEY or AZURE_SPEECH_REGION in .env")


# ---------------------------
# Helpers
# ---------------------------
def sanitize_text_for_ssml(text: str) -> str:
    """
    Escape XML special chars and strip illegal control chars that can break SSML.
    """
    # Remove ASCII control chars except tab/newline/carriage return
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", text)
    # Escape XML entities
    return html.escape(text, quote=False)

def build_ssml(text: str, voice: str, rate: str) -> str:
    safe_text = sanitize_text_for_ssml(text)
    # rate format examples: "0%", "+10%", "-10%"
    return f"""
<speak version="1.0" xml:lang="en-US">
  <voice name="{voice}">
    <prosody rate="{rate}">{safe_text}</prosody>
  </voice>
</speak>
""".strip()

def synthesize_mp3_from_ssml(ssml: str) -> bytes:
    """
    Synthesize SSML and return MP3 bytes in-memory.
    """
    speech_config = speechsdk.SpeechConfig(
        subscription=AZURE_SPEECH_KEY,
        region=AZURE_SPEECH_REGION
    )

    # Force MP3 output format (good default)
    speech_config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Audio16Khz128KBitRateMonoMp3
    )

    # IMPORTANT: audio_config=None returns audio in result.audio_data (in-memory)
    synthesizer = speechsdk.SpeechSynthesizer(
        speech_config=speech_config,
        audio_config=None
    )

    result = synthesizer.speak_ssml_async(ssml).get()

    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        return result.audio_data or b""

    # Failure path with useful details
    details = getattr(result, "cancellation_details", None)
    msg = "TTS failed"
    if details:
        # reason is an enum; error_details is string
        err = getattr(details, "error_details", None)
        if err:
            msg += f": {err}"
        else:
            msg += f": {getattr(details, 'reason', 'Unknown')}"
    raise HTTPException(status_code=500, detail=msg)


# ---------------------------
# API Models
# ---------------------------
class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    voice: str = Field("en-US-JennyNeural")
    rate: str = Field("0%")  # "0%", "+10%", "-10%"


# ---------------------------
# FastAPI app
# ---------------------------
app = FastAPI(title="SupaAI TTS", version="1.0.0")


@app.get("/")
def home():
    return JSONResponse(
        {
            "service": "SupaAI TTS",
            "endpoints": {
                "health": "/health",
                "tts_post": "POST /tts  (json: {text, voice, rate})",
                "tts_get": "GET /tts?text=...&voice=...&rate=...",
            },
            "region": AZURE_SPEECH_REGION,
        }
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/tts")
def tts_post(req: TTSRequest):
    ssml = build_ssml(req.text, req.voice, req.rate)
    mp3_bytes = synthesize_mp3_from_ssml(ssml)

    if not mp3_bytes:
        raise HTTPException(status_code=500, detail="TTS returned empty audio")

    return Response(
        content=mp3_bytes,
        media_type="audio/mpeg",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": 'inline; filename="speech.mp3"',
        },
    )


# Optional: GET endpoint for quick testing (not recommended for long text)
@app.get("/tts")
def tts_get(
    text: str = Query(..., min_length=1, max_length=5000),
    voice: str = Query("en-US-JennyNeural"),
    rate: str = Query("0%"),
):
    ssml = build_ssml(text, voice, rate)
    mp3_bytes = synthesize_mp3_from_ssml(ssml)

    if not mp3_bytes:
        raise HTTPException(status_code=500, detail="TTS returned empty audio")

    return Response(
        content=mp3_bytes,
        media_type="audio/mpeg",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": 'inline; filename="speech.mp3"',
        },
    )

