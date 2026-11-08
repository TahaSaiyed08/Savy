"""ElevenLabs speech-to-text proxy. The browser never sees the API key."""
import os

import httpx

MOCK_TRANSCRIPT = "add a 4 L jug of 2% milk"


class SpeechServiceError(Exception):
    """ElevenLabs failed, or answered with something that isn't a transcript."""


def transcribe(audio: bytes, filename: str, content_type: str) -> str:
    key = os.getenv("ELEVENLABS_API_KEY")
    if not key:
        return MOCK_TRANSCRIPT
    try:
        r = httpx.post(
            "https://api.elevenlabs.io/v1/speech-to-text",
            headers={"xi-api-key": key},
            data={"model_id": os.getenv("ELEVENLABS_STT_MODEL", "scribe_v1"), "language_code": "en"},
            files={"file": (filename, audio, content_type)},
            timeout=20,
        )
        r.raise_for_status()
        text = r.json()["text"]  # ValueError on bad JSON, KeyError/TypeError on the wrong shape
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as e:
        raise SpeechServiceError(f"{type(e).__name__}: {e}") from e
    if not isinstance(text, str):
        raise SpeechServiceError(f"transcript is {type(text).__name__}, not a string")
    return text
