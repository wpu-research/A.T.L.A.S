"""
Client for audio2lipsync FastAPI service (github.com/aaryansachdeva/unreal-audio2lipsync).
Falls back to RMS amplitude → jawOpen animation if service is not running.
"""
import base64, io, struct, wave
import numpy as np
import requests

LIPSYNC_URL  = "http://localhost:8765"
SAMPLE_RATE  = 24000  # Gemini Live output rate
_TIMEOUT     = 120.0  # CPU HuBERT inference can take several seconds for long turns

def _pcm_to_wav_b64(pcm_bytes: bytes) -> str:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm_bytes)
    return base64.b64encode(buf.getvalue()).decode()

def is_available() -> bool:
    try:
        return requests.get(f"{LIPSYNC_URL}/health", timeout=2.0).status_code == 200
    except Exception:
        return False

def get_blendshapes(pcm_bytes: bytes) -> dict | None:
    """POST PCM to service → {audio_b64, blendshapes, n_frames, fps} or None on failure."""
    try:
        r = requests.post(
            f"{LIPSYNC_URL}/generate",
            json={"audio_base64": _pcm_to_wav_b64(pcm_bytes), "fps": 60, "gain": 1.2},
            timeout=_TIMEOUT,
        )
        if r.status_code != 200:
            return None
        d = r.json()
        return {
            "audio_b64": d.get("audio_base64", _pcm_to_wav_b64(pcm_bytes)),
            "blendshapes": d.get("arkit_raw", {}),
            "n_frames": d.get("n_frames", 0),
            "fps": 60,
            "generation_ms": d.get("generation_ms", 0.0),
        }
    except Exception as e:
        print(f"[LipSync] ⚠️  {e}")
        return None

def amplitude_fallback(pcm_bytes: bytes) -> dict:
    """RMS amplitude → jawOpen/mouthOpen curves. No service needed."""
    samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    spf     = SAMPLE_RATE // 60            # samples per frame at 60fps
    n       = len(samples) // spf
    jaw     = []
    for i in range(n):
        rms = float(np.sqrt(np.mean(samples[i*spf:(i+1)*spf] ** 2)))
        jaw.append(min(1.0, rms * 5.0))
    return {
        "audio_b64": _pcm_to_wav_b64(pcm_bytes),
        "blendshapes": {
            "jawOpen":      jaw,
            "mouthOpen":    [v * 0.65 for v in jaw],
            "mouthFunnel":  [v * 0.18 for v in jaw],
        },
        "n_frames": n,
        "fps": 60,
    }
