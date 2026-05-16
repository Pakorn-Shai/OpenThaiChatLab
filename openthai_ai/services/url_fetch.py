import io
import os
import re
import urllib.request
from urllib.parse import quote, urlparse, urlunparse

_URL_RE = re.compile(r'https?://\S+', re.IGNORECASE)
_OCR_EXTS = frozenset({'.jpg', '.jpeg', '.png', '.pdf'})


class UrlFile:
    """Duck-typed file object compatible with the OCR pipeline."""

    def __init__(self, data: bytes, filename: str, content_type: str):
        self.stream = io.BytesIO(data)
        self.filename = filename
        self.content_type = content_type


def extract_ocr_url(text: str) -> str | None:
    for m in _URL_RE.finditer(text):
        url = m.group()
        path = urlparse(url).path
        ext = os.path.splitext(path)[1].lower()
        if ext in _OCR_EXTS:
            return url
    return None


def strip_url(text: str, url: str) -> str:
    return text.replace(url, '').strip()


def _encode_url(url: str) -> str:
    parsed = urlparse(url)
    encoded_path = quote(parsed.path, safe='/:@!$&\'()*+,;=')
    return urlunparse(parsed._replace(path=encoded_path))


def fetch_url_file(url: str) -> UrlFile:
    encoded = _encode_url(url)
    filename = urlparse(url).path.split('/')[-1] or 'document'
    req = urllib.request.Request(
        encoded,
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'image/*,application/pdf,*/*',
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
        ct = resp.headers.get('Content-Type', 'application/octet-stream').split(';')[0].strip()
    return UrlFile(data=data, filename=filename, content_type=ct)
