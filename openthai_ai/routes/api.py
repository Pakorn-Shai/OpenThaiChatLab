import io
import json
import os

from flask import Blueprint, Response, current_app, jsonify, request, stream_with_context

from ..constants import FAST_MODEL, MODELS, OCR_BATCH_SIZE, POWER_MODEL, SYSTEM_PROMPT, YT_RE
from ..services.asr import normalize_asr_mime, transcribe_with_asr_api, validate_asr_upload
from ..services.chat import classify_complexity, stream_chat_completion
from ..services.files import detect_file_type
from ..services.news import (
    extract_news_request,
    fetch_news_search,
    format_news_search_context,
    is_news_query,
)
from ..services.ocr import iter_ocr_events, run_ocr
from ..services.url_fetch import UrlFile, extract_ocr_url, fetch_url_file, strip_url
from ..services.security import resolve_api_key
from ..services.sse import sse_done, sse_event
from ..services.youtube import extract_youtube_audio, extract_youtube_id, fetch_youtube_transcript

api_bp = Blueprint("api", __name__)


@api_bp.route("/models", methods=["GET"])
def get_models():
    return jsonify(MODELS)


@api_bp.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    user_messages = data.get("messages", [])
    model = data.get("model", MODELS[0]["id"])
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + user_messages

    def generate():
        try:
            api_key = resolve_api_key()
            yield from stream_chat_completion(model, messages, api_key)
        except Exception as exc:
            yield sse_event({"error": str(exc)})
        finally:
            yield sse_done()

    return _sse_response(generate())


@api_bp.route("/ocr", methods=["POST"])
def ocr():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    result = run_ocr(
        request.files["file"],
        api_key=resolve_api_key(),
        start_page=request.form.get("start_page", 1),
        page_count=request.form.get("page_count", OCR_BATCH_SIZE),
    )
    if not result["ok"]:
        return jsonify({"error": result["error"]}), 400
    return jsonify({
        "result": result["text"],
        "pages": result["pages"],
        "failed_pages": result["failed_pages"],
        "has_more": result["has_more"],
        "next_page": result.get("next_page"),
        "total_pages": result.get("total_pages"),
    })


@api_bp.route("/asr", methods=["POST"])
def asr():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file_obj = request.files["file"]
    mime = file_obj.content_type or "application/octet-stream"
    validation_error = validate_asr_upload(file_obj, mime, file_obj.filename)
    if validation_error:
        return jsonify({"error": validation_error}), 400

    timestamps = request.form.get("timestamps", "false") == "true"
    try:
        transcript = transcribe_with_asr_api(
            file_obj.filename,
            file_obj.stream,
            normalize_asr_mime(file_obj.filename, mime),
            response_format="verbose_json" if timestamps else None,
            api_key=resolve_api_key(),
        )
        if timestamps and hasattr(transcript, "words"):
            return jsonify({"text": transcript.text, "words": [w.model_dump() for w in transcript.words]})
        return jsonify({"text": transcript.text})
    except Exception as exc:
        current_app.logger.exception("ASR request failed")
        return jsonify({"error": str(exc)}), 500


@api_bp.route("/smart-chat", methods=["POST"])
def smart_chat():
    message = request.form.get("message", "").strip()
    history = _parse_history(request.form.get("history", "[]"))
    file_obj = request.files.get("file")
    model_mode = request.form.get("model_mode", "fast")
    app_mode = request.form.get("mode", "chat")

    def generate():
        try:
            api_key = resolve_api_key()
            yield from _generate_smart_chat(
                message,
                history,
                file_obj,
                api_key,
                model_mode,
                app_mode,
            )
        except Exception as exc:
            current_app.logger.exception("Smart chat request failed")
            yield sse_event({"error": str(exc)})
        finally:
            yield sse_done()

    return _sse_response(generate())


def _generate_smart_chat(
    message,
    history,
    file_obj,
    api_key,
    model_mode="fast",
    app_mode="chat",
):
    context_text = ""
    context_label = "เนื้อหาที่ดึงมา"
    has_ocr = False
    has_asr = False

    yt_id = extract_youtube_id(message)
    clean_msg = YT_RE.sub("", message).strip() if yt_id else message
    ocr_url = extract_ocr_url(message)

    if file_obj:
        mime = file_obj.content_type or "application/octet-stream"
        file_type = detect_file_type(mime, file_obj.filename)

        if file_type == "ocr":
            result = yield from _handle_ocr_upload(file_obj, api_key)
            if not result:
                return
            context_text = result["text"]
            context_label = "ข้อความจากเอกสารหรือรูปภาพ"
            has_ocr = True
        elif file_type == "asr":
            context_text = yield from _handle_asr_upload(file_obj, mime, api_key)
            if not context_text:
                return
            context_label = "ข้อความถอดเสียงจากไฟล์เสียง"
            has_asr = True
        else:
            yield sse_event({"error": "ชนิดไฟล์ไม่รองรับ"})
            return
    elif yt_id:
        context_text = yield from _handle_youtube(yt_id, api_key)
        context_label = "ข้อความจาก YouTube transcript"
        has_asr = True
    elif ocr_url:
        clean_msg = strip_url(clean_msg, ocr_url)
        context_text = yield from _handle_url_ocr(ocr_url, api_key)
        _ext = os.path.splitext(ocr_url.split('?')[0])[1].lower()
        context_label = "ข้อความจากเอกสาร PDF" if _ext == '.pdf' else "ข้อความจากรูปภาพ"
        has_ocr = True
    elif app_mode == "news" or is_news_query(message):
        news_request = extract_news_request(message)
        context_text = yield from _handle_news(news_request)
        if context_text is None:
            return
        context_label = f"ข่าวจาก Google News RSS ภาษาไทย: {news_request.label}"

    assembled = _assemble_prompt(context_label, context_text, clean_msg)
    chosen = _choose_model(model_mode, assembled, has_ocr, has_asr, len(history))
    yield sse_event({"status": "routing", "label": "Typhoon", "mode": model_mode})

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history + [{"role": "user", "content": assembled}]
    yield from stream_chat_completion(chosen, messages, api_key)


def _choose_model(model_mode, assembled, has_ocr, has_asr, history_len):
    if model_mode == "thinking":
        return POWER_MODEL
    if model_mode == "fast":
        return FAST_MODEL
    return classify_complexity(assembled, has_ocr, has_asr, history_len)


def _handle_ocr_upload(file_obj, api_key):
    yield sse_event({"status": "ocr_start"})
    result = None
    for event in iter_ocr_events(
        file_obj,
        api_key=api_key,
        start_page=request.form.get("ocr_start_page", 1),
        page_count=request.form.get("ocr_page_count", OCR_BATCH_SIZE),
    ):
        if event["type"] == "status":
            yield sse_event({k: v for k, v in event.items() if k != "type"})
        elif event["type"] == "error":
            yield sse_event({"error": event["error"]})
            return None
        elif event["type"] == "result":
            result = event

    if not result:
        yield sse_event({"error": "OCR ไม่ได้คืนผลลัพธ์"})
        return None

    done_payload = {
        "status": "ocr_done",
        "preview": result["text"][:200],
        "pages": result["pages"],
        "failed_pages": result["failed_pages"],
        "has_more": result["has_more"],
        "next_page": result.get("next_page"),
    }
    if result.get("total_pages"):
        done_payload["total_pages"] = result["total_pages"]
    yield sse_event(done_payload)
    return result


def _handle_asr_upload(file_obj, mime, api_key):
    yield sse_event({"status": "asr_start"})
    validation_error = validate_asr_upload(file_obj, mime, file_obj.filename)
    if validation_error:
        yield sse_event({"error": validation_error})
        return ""

    transcript = transcribe_with_asr_api(
        file_obj.filename,
        file_obj.stream,
        normalize_asr_mime(file_obj.filename, mime),
        api_key=api_key,
    )
    yield sse_event({"status": "asr_done", "preview": transcript.text[:200]})
    return transcript.text


def _handle_news(news_request):
    yield sse_event({
        "status": "news_start",
        "message": f"📰 กำลังค้นและเปิดอ่านข่าวไทย: {news_request.label}...",
    })
    try:
        articles = fetch_news_search(news_request)
        if not articles:
            yield sse_event({
                "error": "ไม่พบข่าวที่ตรงกับคำค้น ลองเปลี่ยนคำค้นให้กว้างขึ้น"
            })
            return None
        context = format_news_search_context(news_request, articles)
        yield sse_event({
            "status": "news_done",
            "message": f"✓ ดึงข่าว {news_request.label} {len(articles)} รายการ",
        })
        return context
    except Exception as exc:
        yield sse_event({"error": f"ดึงข่าวไม่สำเร็จ: {exc}"})
        return None


def _handle_url_ocr(url, api_key):
    yield sse_event({"status": "url_fetch_start", "message": "🌐 กำลังดาวน์โหลดไฟล์จาก URL..."})
    try:
        file_obj = fetch_url_file(url)
    except Exception as exc:
        yield sse_event({"error": f"ดาวน์โหลดไฟล์ไม่สำเร็จ: {exc}"})
        return ""

    yield sse_event({"status": "ocr_start"})
    result = None
    for event in iter_ocr_events(file_obj, api_key=api_key):
        if event["type"] == "status":
            yield sse_event({k: v for k, v in event.items() if k != "type"})
        elif event["type"] == "error":
            yield sse_event({"error": event["error"]})
            return ""
        elif event["type"] == "result":
            result = event

    if not result:
        yield sse_event({"error": "OCR ไม่ได้คืนผลลัพธ์"})
        return ""

    done_payload = {
        "status": "ocr_done",
        "preview": result["text"][:200],
        "pages": result["pages"],
        "failed_pages": result["failed_pages"],
        "has_more": result["has_more"],
        "next_page": result.get("next_page"),
    }
    if result.get("total_pages"):
        done_payload["total_pages"] = result["total_pages"]
    yield sse_event(done_payload)
    return result["text"]


def _handle_youtube(video_id, api_key):
    yield sse_event({"status": "yt_start"})
    try:
        text = fetch_youtube_transcript(video_id)
        yield sse_event({"status": "yt_done"})
        yield sse_event({"status": "asr_done", "preview": text[:200]})
        return text
    except Exception:
        yield sse_event({"status": "yt_dl_start"})
        audio_bytes, audio_filename, audio_mime = extract_youtube_audio(video_id)
        yield sse_event({"status": "asr_start"})
        transcript = transcribe_with_asr_api(
            audio_filename,
            io.BytesIO(audio_bytes),
            normalize_asr_mime(audio_filename, audio_mime),
            api_key=api_key,
        )
        yield sse_event({"status": "asr_done", "preview": transcript.text[:200]})
        return transcript.text


def _assemble_prompt(context_label, context_text, clean_msg):
    if context_text and clean_msg:
        return f"[{context_label}]\n{context_text}\n\n[คำถาม]\n{clean_msg}"
    if context_text:
        return f"[{context_label}]\n{context_text}\n\nโปรดสรุปและวิเคราะห์เนื้อหาข้างต้น"
    return clean_msg


def _parse_history(raw_history):
    try:
        history = json.loads(raw_history)
    except json.JSONDecodeError:
        return []
    if not isinstance(history, list):
        return []
    return [item for item in history if isinstance(item, dict) and item.get("role") in {"user", "assistant"}]


def _sse_response(generator):
    return Response(
        stream_with_context(generator),
        content_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )
