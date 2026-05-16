import os
import shutil
import tempfile

from ..constants import AUDIO_EXTS, AUDIO_MIMES, OCR_IMAGE_EXTS, OCR_IMAGE_MIMES, PDF_EXTS, PDF_MIMES


def detect_file_type(mime, filename):
    ext = os.path.splitext(filename or "")[1].lower()
    if mime in OCR_IMAGE_MIMES or mime in PDF_MIMES or ext in OCR_IMAGE_EXTS or ext in PDF_EXTS:
        return "ocr"
    if mime in AUDIO_MIMES or ext in AUDIO_EXTS:
        return "asr"
    return "unknown"


def get_upload_size(file_obj):
    pos = file_obj.stream.tell()
    file_obj.stream.seek(0, os.SEEK_END)
    size = file_obj.stream.tell()
    file_obj.stream.seek(pos)
    return size


def save_upload_to_temp(file_obj):
    suffix = os.path.splitext(file_obj.filename or "")[1].lower()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        file_obj.stream.seek(0)
        shutil.copyfileobj(file_obj.stream, tmp)
        return tmp.name
    finally:
        tmp.close()
