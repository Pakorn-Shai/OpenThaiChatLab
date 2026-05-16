import os

from flask import current_app

from ..constants import ASR_MIME_BY_EXT, ASR_MODEL, AUDIO_EXTS, AUDIO_MIMES
from .files import get_upload_size
from .typhoon_client import get_client


def validate_asr_upload(file_obj, mime, filename):
    ext = os.path.splitext(filename or "")[1].lower()
    if mime not in AUDIO_MIMES and ext not in AUDIO_EXTS:
        return "ASR รองรับเฉพาะไฟล์เสียง .wav, .mp3, .flac, .ogg และ .opus เท่านั้น"

    size = get_upload_size(file_obj)
    max_bytes = current_app.config["MAX_ASR_FILE_BYTES"]
    if size > max_bytes:
        return f"ไฟล์เสียงต้องมีขนาดไม่เกิน {max_bytes // (1024 * 1024)}MB"
    file_obj.stream.seek(0)
    return None


def normalize_asr_mime(filename, fallback_mime):
    ext = os.path.splitext(filename or "")[1].lower()
    return ASR_MIME_BY_EXT.get(ext, fallback_mime)


def transcribe_with_asr_api(filename, stream, mime, response_format=None, api_key=None):
    stream.seek(0)
    kwargs = {
        "model": ASR_MODEL,
        "file": (filename, stream, mime),
    }
    if response_format:
        kwargs["response_format"] = response_format
    return get_client(api_key).audio.transcriptions.create(**kwargs)
