from flask import current_app
from openai import OpenAI


def get_client(api_key):
    key = (api_key or "").strip()
    if not key:
        raise ValueError("กรุณาตั้งค่า Typhoon API Key ก่อนใช้งาน")
    return OpenAI(api_key=key, base_url=current_app.config["BASE_URL"])
