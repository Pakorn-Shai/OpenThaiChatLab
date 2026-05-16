import os
import threading
import tempfile
import time
from contextlib import contextmanager

from flask import current_app

from ..constants import OCR_IMAGE_EXTS, OCR_IMAGE_MIMES, PDF_EXTS, PDF_MIMES
from .files import save_upload_to_temp

_ocr_env_lock = threading.Lock()


def detect_ocr_kind(mime, filename):
    ext = os.path.splitext(filename or "")[1].lower()
    if mime in PDF_MIMES or ext in PDF_EXTS:
        return "pdf"
    if mime in OCR_IMAGE_MIMES or ext in OCR_IMAGE_EXTS:
        return "image"
    return "unsupported"


def validate_ocr_upload(file_path, mime, filename):
    size = os.path.getsize(file_path)
    max_bytes = current_app.config["MAX_OCR_FILE_BYTES"]
    if size > max_bytes:
        return None, f"ไฟล์ OCR ต้องมีขนาดไม่เกิน {max_bytes // (1024 * 1024)}MB"

    kind = detect_ocr_kind(mime, filename)
    if kind == "unsupported":
        return None, "OCR รองรับเฉพาะ PDF, PNG, JPG และ JPEG เท่านั้น"
    return kind, None


@contextmanager
def typhoon_ocr_env(api_key=None):
    key = (api_key or "").strip()
    if not key:
        raise ValueError("กรุณาตั้งค่า Typhoon API Key ก่อนใช้งาน OCR")

    with _ocr_env_lock:
        previous = {
            "TYPHOON_OCR_API_KEY": os.environ.get("TYPHOON_OCR_API_KEY"),
            "TYPHOON_API_KEY": os.environ.get("TYPHOON_API_KEY"),
            "TYPHOON_BASE_URL": os.environ.get("TYPHOON_BASE_URL"),
        }
        os.environ["TYPHOON_OCR_API_KEY"] = key
        os.environ["TYPHOON_API_KEY"] = key
        os.environ["TYPHOON_BASE_URL"] = current_app.config["BASE_URL"]
        try:
            yield
        finally:
            for name, value in previous.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value


def get_pdf_page_count(file_path):
    from pypdf import PdfReader

    try:
        return len(PdfReader(file_path).pages)
    except Exception:
        return None


def render_pdf_page_to_temp_image(file_path, page_num):
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(file_path)
    try:
        page = pdf[page_num - 1]
        bitmap = page.render(scale=2)
        image = bitmap.to_pil()
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f"-page-{page_num}.png")
        try:
            image.save(tmp.name, format="PNG")
            return tmp.name
        finally:
            tmp.close()
    finally:
        pdf.close()


def ocr_pdf_page(file_path, page_num):
    from typhoon_ocr import ocr_document

    image_path = render_pdf_page_to_temp_image(file_path, page_num)
    try:
        return ocr_document(pdf_or_image_path=image_path)
    finally:
        try:
            os.unlink(image_path)
        except OSError:
            pass


def run_ocr(file_obj, api_key=None, start_page=1, page_count=None, status=None):
    result = None
    for event in iter_ocr_events(file_obj, api_key, start_page, page_count):
        if event["type"] == "status" and status:
            status({key: value for key, value in event.items() if key != "type"})
        elif event["type"] == "error":
            return {"ok": False, "error": event["error"]}
        elif event["type"] == "result":
            result = event

    if not result:
        return {"ok": False, "error": "OCR ไม่ได้คืนผลลัพธ์"}
    result["ok"] = True
    return result


def iter_ocr_events(file_obj, api_key=None, start_page=1, page_count=None):
    tmp_path = save_upload_to_temp(file_obj)
    try:
        mime = file_obj.content_type or "application/octet-stream"
        filename = file_obj.filename or "document"
        kind, error = validate_ocr_upload(tmp_path, mime, filename)
        if error:
            yield {"type": "error", "error": error}
            return

        if kind == "image":
            from typhoon_ocr import ocr_document

            yield {"type": "status", "status": "ocr_progress", "message": "กำลังอ่านข้อความจากรูปภาพ..."}
            with typhoon_ocr_env(api_key):
                markdown = ocr_document(pdf_or_image_path=tmp_path)
            yield {
                "type": "result",
                "text": f"## Image\n\n{markdown}",
                "pages": [1],
                "failed_pages": [],
                "has_more": False,
            }
            return

        yield from _iter_pdf_ocr(tmp_path, api_key, start_page, page_count)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _iter_pdf_ocr(tmp_path, api_key, start_page, page_count):
    batch_size = current_app.config["OCR_BATCH_SIZE"]
    total_pages = get_pdf_page_count(tmp_path)
    first_page = max(1, int(start_page or 1))
    requested_pages = max(1, min(int(page_count or batch_size), batch_size))
    last_page = first_page + requested_pages - 1
    if total_pages:
        last_page = min(last_page, total_pages)

    yield {"type": "status", "status": "ocr_progress", "message": f"กำลังอ่าน PDF หน้า {first_page}-{last_page}..."}

    sections = []
    failed_pages = []
    with typhoon_ocr_env(api_key):
        for page_num in range(first_page, last_page + 1):
            yield {"type": "status", "status": "ocr_progress", "message": f"กำลังอ่านหน้า {page_num}..."}
            try:
                markdown = ocr_pdf_page(tmp_path, page_num)
                sections.append(f"## Page {page_num}\n\n{markdown}")
            except Exception as exc:
                failed_pages.append({"page": page_num, "error": str(exc)})
                yield {
                    "type": "status",
                    "status": "ocr_progress",
                    "message": f"อ่านหน้า {page_num} ไม่สำเร็จ จะใช้หน้าที่อ่านได้ต่อ",
                }

    if not sections:
        details = "; ".join(f"หน้า {item['page']}: {item['error']}" for item in failed_pages)
        yield {"type": "error", "error": f"OCR อ่าน PDF ไม่สำเร็จ ({details})"}
        return

    has_more = bool(total_pages and last_page < total_pages)
    if has_more:
        next_first = last_page + 1
        next_last = min(next_first + batch_size - 1, total_pages)
        yield {
            "type": "status",
            "status": "ocr_wait",
            "message": f"อ่านถึงหน้า {last_page} แล้ว ยังมีหน้า {next_first}-{next_last} ที่อ่านต่อได้",
        }
        time.sleep(current_app.config["OCR_BATCH_WAIT_SECONDS"])

    yield {
        "type": "result",
        "text": "\n\n".join(sections),
        "pages": list(range(first_page, last_page + 1)),
        "failed_pages": failed_pages,
        "has_more": has_more,
        "next_page": last_page + 1 if has_more else None,
        "total_pages": total_pages,
    }
