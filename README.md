# Open Thai AI

เว็บแอป Flask สำหรับคุยกับโมเดล Typhoon พร้อมความสามารถเสริมสำหรับงานภาษาไทย เช่น อ่านเอกสารด้วย OCR, ถอดเสียงด้วย ASR, ดึง transcript จาก YouTube, อ่านไฟล์จาก URL และดึงข่าวล่าสุดจาก Google News RSS เพื่อนำมาใช้เป็นบริบทในการตอบคำถาม

## ฟีเจอร์หลัก

- แชตกับ Typhoon ผ่าน Server-Sent Events (SSE) เพื่อสตรีมคำตอบแบบ real-time
- เลือกโหมดโมเดลได้ระหว่างเร็ว, วิเคราะห์หนัก หรือให้ระบบช่วยเลือกตามความซับซ้อน
- OCR สำหรับ PDF, PNG, JPG และ JPEG โดยอ่าน PDF เป็นชุดหน้า
- ASR สำหรับไฟล์เสียง `.wav`, `.mp3`, `.flac`, `.ogg` และ `.opus`
- รองรับ YouTube URL โดยพยายามใช้ transcript ก่อน และ fallback เป็นการดึงเสียงมาถอดข้อความ
- รองรับ OCR จาก URL ของไฟล์ PDF หรือรูปภาพ
- ตรวจจับคำถามข่าวและดึงข่าวล่าสุดหมวดข่าวร้อน, กีฬา, การเงิน, เทคโนโลยี และการเมือง
- ใช้ API key ฝั่ง server เท่านั้น ไม่ส่งหรือเก็บ Typhoon API key ใน browser

## โครงสร้างโปรเจกต์

```text
.
├── app.py                    # local development entrypoint
├── wsgi.py                   # production WSGI entrypoint
├── requirements.txt          # Python dependencies
├── templates/
│   └── index.html            # หน้าเว็บหลัก
└── openthai_ai/
    ├── __init__.py           # Flask app factory และ security headers
    ├── config.py             # config จาก environment variables
    ├── constants.py          # รายชื่อโมเดล, MIME/extension allowlist, system prompt
    ├── routes/
    │   ├── main.py           # / และ /healthz
    │   └── api.py            # API endpoints หลัก
    └── services/
        ├── asr.py            # ตรวจไฟล์เสียงและเรียก Typhoon ASR
        ├── chat.py           # เลือกโมเดลและสตรีมคำตอบ
        ├── files.py          # ตรวจชนิดไฟล์และจัดการไฟล์ชั่วคราว
        ├── news.py           # ดึงข่าวจาก Google News RSS
        ├── ocr.py            # OCR รูปภาพ/PDF และ batch PDF pages
        ├── security.py       # จัดการ API key ฝั่ง server
        ├── sse.py            # helper สำหรับ SSE payload
        ├── typhoon_client.py # OpenAI-compatible client สำหรับ Typhoon
        ├── url_fetch.py      # ดาวน์โหลดไฟล์จาก URL สำหรับ OCR
        └── youtube.py        # YouTube transcript และ audio fallback
```

## การติดตั้ง

ต้องมี Python 3.10+ แนะนำให้สร้าง virtual environment ก่อนติดตั้ง dependency

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

จากนั้นตั้งค่า `TYPHOON_API_KEY` ในไฟล์ `.env`

```env
TYPHOON_API_KEY=your_typhoon_api_key
```

## การรันแบบ Local

```powershell
python app.py
```

ค่าเริ่มต้นจะรันที่ `http://127.0.0.1:5000`

## การรันแบบ Production-Style บน Windows

```powershell
waitress-serve --listen=0.0.0.0:5000 wsgi:app
```

## Environment Variables

| ตัวแปร | ค่าเริ่มต้น | คำอธิบาย |
| --- | --- | --- |
| `TYPHOON_API_KEY` | ว่าง | API key สำหรับ Typhoon ใช้ทั้ง chat, OCR และ ASR |
| `API_KEY` | ว่าง | fallback เดิม หากไม่ได้ตั้ง `TYPHOON_API_KEY` |
| `TYPHOON_BASE_URL` | `https://api.opentyphoon.ai/v1` | endpoint ของ Typhoon API |
| `HOST` | `127.0.0.1` | host สำหรับ `python app.py` |
| `PORT` | `5000` | port สำหรับ `python app.py` |
| `FLASK_DEBUG` | `false` | เปิด/ปิด Flask debug mode |
| `MAX_UPLOAD_BYTES` | `31457280` | ขนาด request upload สูงสุดโดยรวม |
| `MAX_ASR_FILE_BYTES` | `26214400` | ขนาดไฟล์เสียงสูงสุด |
| `MAX_OCR_FILE_BYTES` | `10485760` | ขนาดไฟล์ OCR สูงสุด |
| `OCR_BATCH_SIZE` | `5` | จำนวนหน้า PDF สูงสุดที่อ่านต่อ batch |
| `OCR_BATCH_WAIT_SECONDS` | `3` | เวลารอก่อนแจ้งว่ายังมีหน้า PDF ต่อ |
| `CHAT_TEMPERATURE` | `0.6` | temperature สำหรับ chat completion |
| `CHAT_TOP_P` | `0.6` | top-p สำหรับ chat completion |
| `CHAT_MAX_COMPLETION_TOKENS` | `2048` | token สูงสุดของคำตอบ |

## API Endpoints

| Method | Path | คำอธิบาย |
| --- | --- | --- |
| `GET` | `/` | หน้าเว็บหลัก |
| `GET` | `/healthz` | health check คืนค่า `{ "ok": true }` |
| `GET` | `/models` | รายชื่อโมเดล Typhoon ที่เลือกได้ |
| `POST` | `/chat` | แชตแบบ JSON และสตรีมคำตอบผ่าน SSE |
| `POST` | `/smart-chat` | endpoint หลักของหน้าเว็บ รองรับข้อความ, history, ไฟล์, YouTube, URL OCR และข่าว |
| `POST` | `/ocr` | OCR ไฟล์ PDF/รูปภาพ แบบ response JSON |
| `POST` | `/asr` | ถอดเสียงไฟล์ audio แบบ response JSON |

## ไฟล์ที่รองรับ

| งาน | นามสกุลที่รองรับ | ขนาดเริ่มต้น |
| --- | --- | --- |
| OCR | `.pdf`, `.png`, `.jpg`, `.jpeg` | ไม่เกิน 10 MB |
| ASR | `.wav`, `.mp3`, `.flac`, `.ogg`, `.opus` | ไม่เกิน 25 MB |

สำหรับ PDF ระบบจะอ่านทีละ batch ตาม `OCR_BATCH_SIZE` และคืนข้อมูล `has_more` / `next_page` เพื่อให้ client อ่านหน้าถัดไปได้

## หมายเหตุด้านความปลอดภัย

- API key ถูกอ่านจาก environment ฝั่ง server เท่านั้น
- Flask debug ปิดเป็นค่าเริ่มต้น
- มี security headers เช่น `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` และ `Permissions-Policy`
- OCR ใช้ lock ขณะตั้งค่า environment ชั่วคราว เพราะ library ภายนอกอ่าน API key จาก environment variables
- ฝั่งหน้าเว็บควร sanitize HTML/Markdown ก่อนแสดงผลเสมอ
