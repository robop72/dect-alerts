import logging
import os

logger = logging.getLogger(__name__)

AUDIO_DIR = "audio"
os.makedirs(AUDIO_DIR, exist_ok=True)

LOCATION_VOICES = {
    "AU": "en-au",
    "NA": "en-us",
    "UK": "en-gb",
}

# pydub requires audioop which was removed in Python 3.13+; import lazily so the
# app still starts even if conversion is unavailable (Twilio <Say> covers demo mode).
try:
    from pydub import AudioSegment as _AudioSegment
    _PYDUB_AVAILABLE = True
except Exception:
    _PYDUB_AVAILABLE = False
    logger.warning("pydub unavailable (Python 3.13+ removed audioop) — MP3→WAV conversion disabled; Twilio <Say> will be used instead")


def generate_alert_audio(alert_type: str, room_number: str, location: str, alert_id: int) -> str | None:
    """Generate a telephony-ready WAV. Returns path or None if unavailable."""
    try:
        from gtts import gTTS
    except ImportError:
        logger.warning("gTTS not installed — skipping TTS generation")
        return None

    lang = LOCATION_VOICES.get(location.upper(), "en-us")
    message = f"{alert_type} in Room {room_number}. Press 1 to acknowledge."
    mp3_path = os.path.join(AUDIO_DIR, f"alert_{alert_id}.mp3")
    wav_path = os.path.join(AUDIO_DIR, f"alert_{alert_id}.wav")

    try:
        tts = gTTS(text=message, lang=lang)
        tts.save(mp3_path)
    except Exception as e:
        logger.error(f"gTTS failed: {e}")
        return None

    if not _PYDUB_AVAILABLE:
        logger.info(f"MP3 saved to {mp3_path} (no WAV conversion — pydub unavailable)")
        return mp3_path

    try:
        sound = _AudioSegment.from_mp3(mp3_path)
        sound = sound.set_frame_rate(8000).set_channels(1)
        sound.export(wav_path, format="wav")
        logger.info(f"Audio generated: {wav_path}")
        return wav_path
    except Exception as e:
        logger.error(f"pydub conversion failed: {e}")
        return mp3_path
