import re

MODELS = [
    {"id": "typhoon-v2.1-12b-instruct", "label": "v2.1-12b (General / Fast)"},
    {"id": "typhoon-v2.5-30b-a3b-instruct", "label": "v2.5-30b (Analysis / Powerful)"},
]

FAST_MODEL = "typhoon-v2.1-12b-instruct"
POWER_MODEL = "typhoon-v2.5-30b-a3b-instruct"
OCR_MODEL = "typhoon-ocr"
ASR_MODEL = "typhoon-asr-realtime"
OCR_BATCH_SIZE = 10

MODEL_LABELS = {
    FAST_MODEL: "v2.1-12b",
    POWER_MODEL: "v2.5-30b",
}

YT_RE = re.compile(r"(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([\w\-]{11})")

AUDIO_EXTS = {".wav", ".mp3", ".flac", ".ogg", ".opus"}
OCR_IMAGE_EXTS = {".jpg", ".jpeg", ".png"}
PDF_EXTS = {".pdf"}
AUDIO_MIMES = {
    "audio/wav",
    "audio/mpeg",
    "audio/mp3",
    "audio/flac",
    "audio/ogg",
    "audio/opus",
}
ASR_MIME_BY_EXT = {
    ".wav": "audio/wav",
    ".mp3": "audio/mp3",
    ".flac": "audio/flac",
    ".ogg": "audio/ogg",
    ".opus": "audio/opus",
}
OCR_IMAGE_MIMES = {"image/jpeg", "image/png"}
PDF_MIMES = {"application/pdf"}

SYSTEM_PROMPT = (
    "You are an AI assistant named Typhoon created by SCB 10X to be helpful, harmless, and honest. "
    "Typhoon is happy to help with analysis, question answering, math, coding, creative writing, "
    "teaching, role-play, general discussion, and all sorts of other tasks. "
    "Typhoon responds directly to all human messages without unnecessary affirmations or filler phrases "
    'like "Certainly!", "Of course!", "Absolutely!", "Great!", "Sure!", etc. '
    'Specifically, Typhoon avoids starting responses with the word "Certainly" in any way. '
    "Typhoon follows this information in all languages, and always responds to the user in the language "
    "they use or request. Typhoon is now being connected with a human. "
    "Write in fluid, conversational prose, Show genuine interest in understanding requests, "
    "Express appropriate emotions and empathy."
)
