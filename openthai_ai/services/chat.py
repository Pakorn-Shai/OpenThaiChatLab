from flask import current_app

from ..constants import FAST_MODEL, MODEL_LABELS, POWER_MODEL
from .sse import sse_event
from .typhoon_client import get_client


def classify_complexity(text, has_ocr, has_asr, history_len):
    score = 0
    low = text.lower()
    words = len(text.split())
    if words > 120:
        score += 2
    if words > 300:
        score += 3
    code_signals = ["```", "def ", "class ", "function ", "import ", "เขียนโค้ด", "debug", "optimize"]
    if any(signal in low for signal in code_signals):
        score += 3
    analysis_keywords = [
        "วิเคราะห์",
        "analyze",
        "เปรียบเทียบ",
        "compare",
        "อธิบายว่าทำไม",
        "explain why",
        "วิจัย",
        "research",
        "critique",
        "ทีละขั้น",
        "step by step",
        "ประเมิน",
        "evaluate",
        "ข้อดีข้อเสีย",
        "pros and cons",
    ]
    if any(keyword in low for keyword in analysis_keywords):
        score += 4
    summary_keywords = ["สรุป", "summarize"]
    if any(keyword in low for keyword in summary_keywords):
        score += 2
    if has_ocr:
        score += 2
    if has_asr:
        score += 1
    if history_len > 8:
        score += 1
    math_signals = ["$", r"\frac", r"\sum", "equation", "สมการ", "คำนวณ"]
    if any(signal in text for signal in math_signals):
        score += 2
    return POWER_MODEL if score >= 4 else FAST_MODEL


def stream_chat_completion(model, messages, api_key):
    try:
        stream = _create_chat_stream(model, messages, api_key)
    except Exception as exc:
        if model == FAST_MODEL and "Model not found" in str(exc):
            yield sse_event({
                "status": "routing",
                "label": MODEL_LABELS[POWER_MODEL],
                "message": "v2.1 ยังไม่พร้อมใช้งานกับ API key นี้ จึงสลับไปใช้ v2.5",
            })
            stream = _create_chat_stream(POWER_MODEL, messages, api_key)
        else:
            raise

    for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta is not None:
            yield sse_event({"content": delta})
        if chunk.usage:
            yield sse_event({
                "usage": {
                    "prompt_tokens": chunk.usage.prompt_tokens,
                    "completion_tokens": chunk.usage.completion_tokens,
                    "total_tokens": chunk.usage.total_tokens,
                }
            })


def _create_chat_stream(model, messages, api_key):
    return get_client(api_key).chat.completions.create(
        model=model,
        messages=messages,
        temperature=current_app.config["CHAT_TEMPERATURE"],
        max_completion_tokens=current_app.config["CHAT_MAX_COMPLETION_TOKENS"],
        top_p=current_app.config["CHAT_TOP_P"],
        frequency_penalty=0,
        stream=True,
        stream_options={"include_usage": True},
    )
