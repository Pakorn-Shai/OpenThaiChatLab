import json


def sse_event(payload):
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def sse_done():
    return "data: [DONE]\n\n"
