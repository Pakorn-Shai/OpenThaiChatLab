import os
import shutil
import tempfile

from ..constants import YT_RE


def extract_youtube_id(text):
    match = YT_RE.search(text)
    return match.group(1) if match else None


def fetch_youtube_transcript(video_id):
    from youtube_transcript_api import YouTubeTranscriptApi

    transcript_api = YouTubeTranscriptApi()
    fetched = transcript_api.fetch(video_id, languages=["th", "en"])
    return " ".join(segment.text for segment in fetched)


def extract_youtube_audio(video_id):
    import yt_dlp

    url = f"https://www.youtube.com/watch?v={video_id}"
    tmpdir = tempfile.mkdtemp()
    try:
        ydl_opts = {
            "format": "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio",
            "outtmpl": os.path.join(tmpdir, "audio.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": 30,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as downloader:
            info = downloader.extract_info(url, download=True)
            ext = info.get("ext", "m4a")
        audio_path = os.path.join(tmpdir, f"audio.{ext}")
        with open(audio_path, "rb") as audio_file:
            audio_bytes = audio_file.read()
        mime_map = {
            "m4a": "audio/mp4",
            "mp4": "audio/mp4",
            "webm": "audio/webm",
            "ogg": "audio/ogg",
            "mp3": "audio/mpeg",
            "opus": "audio/opus",
            "flac": "audio/flac",
            "wav": "audio/wav",
        }
        return audio_bytes, f"audio.{ext}", mime_map.get(ext, f"audio/{ext}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
