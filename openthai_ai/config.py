import os

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

if load_dotenv:
    load_dotenv()


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name, default):
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


class Config:
    APP_NAME = "Open Thai AI"
    BASE_URL = os.getenv("TYPHOON_BASE_URL", "https://api.opentyphoon.ai/v1")
    TYPHOON_API_KEY = (os.getenv("TYPHOON_API_KEY") or os.getenv("API_KEY", "")).strip()

    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = env_int("PORT", 5000)
    DEBUG = env_bool("FLASK_DEBUG", False)

    MAX_CONTENT_LENGTH = env_int("MAX_UPLOAD_BYTES", 30 * 1024 * 1024)
    MAX_ASR_FILE_BYTES = env_int("MAX_ASR_FILE_BYTES", 25 * 1024 * 1024)
    MAX_OCR_FILE_BYTES = env_int("MAX_OCR_FILE_BYTES", 10 * 1024 * 1024)
    OCR_BATCH_SIZE = env_int("OCR_BATCH_SIZE", 5)
    OCR_BATCH_WAIT_SECONDS = env_int("OCR_BATCH_WAIT_SECONDS", 3)

    CHAT_TEMPERATURE = float(os.getenv("CHAT_TEMPERATURE", "0.6"))
    CHAT_TOP_P = float(os.getenv("CHAT_TOP_P", "0.6"))
    CHAT_MAX_COMPLETION_TOKENS = env_int("CHAT_MAX_COMPLETION_TOKENS", 2048)
