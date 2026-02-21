"""
Voice System for Alita
Handles Text-to-Speech (edge-tts) — completely free, realistic voices.
Speech-to-Text is handled client-side via the Web Speech API (free, built into browsers).
"""

import asyncio
import io
import re
import edge_tts

# ─── Voice Configuration ──────────────────────────────────────────
VOICES = {
    "en_in_expressive": "en-IN-NeerjaExpressiveNeural",  # Best for Hinglish
    "en_in_neerja": "en-IN-NeerjaNeural",                # Standard Indian English
    "hi_swara": "hi-IN-SwaraNeural",                      # Hindi female - warm
    "hi_madhur": "hi-IN-MadhurNeural",                    # Hindi female - soft
}

# Default: Neerja Expressive — natural Indian accent, handles Hinglish well
DEFAULT_VOICE = "en-IN-NeerjaExpressiveNeural"

# Hindi voice for pure Devanagari text
HINDI_VOICE = "hi-IN-SwaraNeural"


# ─── Emoji & Cleanup ─────────────────────────────────────────────
# Regex to match ALL emoji characters
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # Emoticons
    "\U0001F300-\U0001F5FF"  # Symbols & pictographs
    "\U0001F680-\U0001F6FF"  # Transport & map
    "\U0001F1E0-\U0001F1FF"  # Flags
    "\U00002702-\U000027B0"  # Dingbats
    "\U000024C2-\U0001F251"  # Enclosed characters
    "\U0001F900-\U0001F9FF"  # Supplemental symbols
    "\U0001FA00-\U0001FA6F"  # Chess symbols
    "\U0001FA70-\U0001FAFF"  # Symbols extended
    "\U00002600-\U000026FF"  # Misc symbols
    "\U0000FE00-\U0000FE0F"  # Variation selectors
    "\U0000200D"             # Zero-width joiner
    "\U00002B50"             # Star
    "\U0000200B-\U0000200F"  # Zero-width spaces
    "\U0000E000-\U0000F8FF"  # Private use
    "\U00010000-\U0010FFFF"  # Supplementary
    "]+",
    flags=re.UNICODE,
)


def _clean_text_for_speech(text: str) -> str:
    """
    Clean text before sending to TTS:
    - Remove ALL emojis (so TTS doesn't say 'smiling face', 'two hearts')
    - Remove markdown formatting (**, *, etc.)
    - Clean up extra whitespace
    """
    # Remove emojis
    text = EMOJI_PATTERN.sub("", text)

    # Remove markdown bold/italic
    text = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', text)

    # Remove bullet points and list markers
    text = re.sub(r'^[\s]*[-•]\s*', '', text, flags=re.MULTILINE)

    # Clean up multiple spaces and newlines
    text = re.sub(r'\s+', ' ', text).strip()

    return text


def _detect_language(text: str) -> str:
    """Detect if text is Hindi or English and pick the best voice."""
    devanagari_chars = len(re.findall(r'[\u0900-\u097F]', text))
    total_alpha = len(re.findall(r'[a-zA-Z\u0900-\u097F]', text))

    if total_alpha == 0:
        return DEFAULT_VOICE

    if devanagari_chars / total_alpha > 0.5:
        return HINDI_VOICE

    return DEFAULT_VOICE


async def text_to_speech(text: str, voice: str = None, rate: str = "+8%", max_retries: int = 3) -> bytes:
    """
    Convert text to speech audio (MP3 bytes) using edge-tts.
    - Auto-strips emojis so TTS doesn't read them
    - Auto-detects Hindi vs English for best voice
    - Rate is slightly slower (-5%) for a sweeter, smoother tone

    Returns: MP3 audio as bytes
    """
    # CRITICAL: Clean text before speaking
    clean_text = _clean_text_for_speech(text)

    if not clean_text or len(clean_text) < 2:
        return b""

    # Auto-detect best voice
    if voice is None:
        voice = _detect_language(clean_text)

    last_error = None
    for attempt in range(max_retries):
        try:
            communicate = edge_tts.Communicate(text=clean_text, voice=voice, rate=rate)

            audio_buffer = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_buffer.write(chunk["data"])

            audio_data = audio_buffer.getvalue()
            if audio_data:
                return audio_data

        except Exception as e:
            last_error = e
            wait_time = (attempt + 1) * 0.5
            print(f"⚠️ TTS attempt {attempt + 1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(wait_time)

    print(f"❌ TTS failed after {max_retries} attempts: {last_error}")
    return b""


async def list_voices(language: str = None) -> list[dict]:
    """List available voices, optionally filtered by language."""
    voices = await edge_tts.list_voices()
    if language:
        voices = [v for v in voices if v["Locale"].startswith(language)]
    return [
        {
            "name": v["ShortName"],
            "gender": v["Gender"],
            "locale": v["Locale"],
            "friendly_name": v["FriendlyName"],
        }
        for v in voices
    ]
