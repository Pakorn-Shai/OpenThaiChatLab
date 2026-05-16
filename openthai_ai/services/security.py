from flask import current_app


def resolve_api_key():
    server_key = current_app.config["TYPHOON_API_KEY"]
    if server_key:
        return server_key

    raise ValueError("ยังไม่ได้ตั้งค่า TYPHOON_API_KEY ใน .env หรือ environment ของ server")
