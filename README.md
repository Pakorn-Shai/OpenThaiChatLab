# OpenThaiChatLab

OpenThaiChatLab เป็นเว็บแอป Flask สำหรับคุยกับโมเดล Typhoon ของ SCB 10X โดยออกแบบให้ใช้งานภาษาไทยได้คล่องทั้งงานถามตอบทั่วไป งานเขียน งานแปล งานโค้ด งานสรุปเอกสาร OCR งานถอดเสียง ASR งานสรุป YouTube และงานสรุปข่าวล่าสุดจาก Google News RSS

แอปนี้ใช้ API key ฝั่ง server เท่านั้น ผู้ใช้หน้าเว็บไม่ต้องกรอก key ใน browser และคำตอบถูกส่งกลับแบบ streaming ผ่าน Server-Sent Events (SSE) เพื่อให้เห็นข้อความไหลแบบ real-time

## ความสามารถหลัก

- แชตภาษาไทยกับ Typhoon แบบ real-time streaming
- รองรับ Markdown, code block, syntax highlighting และปุ่ม copy code ในหน้าเว็บ
- เลือกโหมดโมเดลได้ระหว่าง `Fast` และ `Thinking`
- ใช้ `typhoon-v2.1-12b-instruct` สำหรับงานทั่วไป/เร็ว
- ใช้ `typhoon-v2.5-30b-a3b-instruct` สำหรับงานวิเคราะห์หนัก
- มี logic เลือกโมเดลตามความซับซ้อนใน service layer สำหรับโหมด auto ภายในระบบ
- แนบไฟล์เอกสารหรือรูปภาพเพื่อ OCR ได้
- OCR รองรับ PDF, PNG, JPG และ JPEG
- อ่าน PDF เป็น batch ตามจำนวนหน้าที่กำหนด และแจ้ง `has_more` / `next_page` เมื่อยังมีหน้าต่อ
- แนบไฟล์เสียงเพื่อถอดความด้วย ASR ได้
- ASR รองรับ WAV, MP3, FLAC, OGG และ OPUS
- endpoint ASR รองรับโหมด timestamp ผ่าน `response_format=verbose_json`
- วาง YouTube URL เพื่อดึง transcript ภาษาไทย/อังกฤษ
- หาก YouTube ไม่มี transcript ระบบ fallback เป็นการดาวน์โหลดเสียงด้วย `yt-dlp` แล้วส่งเข้า ASR
- วาง URL ของไฟล์ PDF/รูปภาพเพื่อดาวน์โหลดและทำ OCR ได้
- ตรวจจับคำถามข่าวและดึงข่าวล่าสุดจาก Google News RSS
- หมวดข่าวที่รองรับ: ข่าวร้อน, กีฬา, การเงิน, เทคโนโลยี, การเมือง
- เก็บ cache ข่าว 15 นาทีเพื่อลดการเรียก RSS ซ้ำ
- ส่ง history ของบทสนทนาให้โมเดลเพื่อคุยต่อเนื่องได้
- Export บทสนทนาเป็นไฟล์ Markdown จากหน้าเว็บ
- มีปุ่ม New Chat, theme light/dark, preview ไฟล์แนบ และ preview YouTube ID
- มี health check endpoint สำหรับ deploy/monitor
- ใส่ security headers พื้นฐานให้ทุก response

## โครงสร้างโปรเจกต์

```text
OpenThaiChatLab/
├── app.py
├── wsgi.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── templates/
│   └── index.html
└── openthai_ai/
    ├── __init__.py
    ├── config.py
    ├── constants.py
    ├── routes/
    │   ├── __init__.py
    │   ├── main.py
    │   └── api.py
    └── services/
        ├── __init__.py
        ├── asr.py
        ├── chat.py
        ├── files.py
        ├── news.py
        ├── ocr.py
        ├── security.py
        ├── sse.py
        ├── typhoon_client.py
        ├── url_fetch.py
        └── youtube.py
```

## หน้าที่ของแต่ละไฟล์

| Path | หน้าที่ |
| --- | --- |
| `app.py` | entrypoint สำหรับรัน local development ด้วย `python app.py` |
| `wsgi.py` | entrypoint สำหรับ production WSGI server เช่น Waitress |
| `requirements.txt` | dependency ของ Python project |
| `.env.example` | ตัวอย่าง environment variables ที่ต้องตั้งค่า |
| `templates/index.html` | หน้าเว็บ chat ทั้งหมด รวม UI, CSS และ JavaScript |
| `openthai_ai/__init__.py` | Flask app factory, register blueprints และเพิ่ม security headers |
| `openthai_ai/config.py` | โหลด `.env` และอ่าน config จาก environment variables |
| `openthai_ai/constants.py` | รายชื่อโมเดล, system prompt, regex YouTube, MIME/extension allowlist |
| `openthai_ai/routes/main.py` | route หน้าแรก `/` และ health check `/healthz` |
| `openthai_ai/routes/api.py` | API หลักของ chat, smart chat, OCR, ASR และ model list |
| `openthai_ai/services/chat.py` | เลือกโมเดลตามความซับซ้อนและ stream chat completion |
| `openthai_ai/services/ocr.py` | ตรวจไฟล์ OCR, render PDF เป็นรูป, OCR ทีละหน้า/ทีละ batch |
| `openthai_ai/services/asr.py` | ตรวจไฟล์เสียงและเรียก Typhoon ASR |
| `openthai_ai/services/files.py` | ตรวจชนิดไฟล์, วัดขนาดไฟล์ และบันทึกไฟล์ชั่วคราว |
| `openthai_ai/services/news.py` | ตรวจ intent ข่าว, เลือกหมวด, ดึง Google News RSS และจัด format context |
| `openthai_ai/services/youtube.py` | ดึง YouTube transcript และ fallback เป็น audio extraction |
| `openthai_ai/services/url_fetch.py` | ตรวจ URL ของ PDF/รูปภาพ ดาวน์โหลดไฟล์ และส่งต่อเข้า OCR pipeline |
| `openthai_ai/services/security.py` | resolve API key ฝั่ง server |
| `openthai_ai/services/sse.py` | helper สำหรับสร้าง SSE event และ `[DONE]` |
| `openthai_ai/services/typhoon_client.py` | สร้าง OpenAI-compatible client สำหรับ Typhoon API |

## การติดตั้ง

ต้องมี Python 3.10+ จากนั้นติดตั้ง dependency:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

ตั้งค่า API key ในไฟล์ `.env`:

```env
TYPHOON_API_KEY=your_typhoon_api_key
```

ถ้าไม่ได้ตั้ง `TYPHOON_API_KEY` ระบบจะ fallback ไปอ่าน `API_KEY`

## การรันแบบ Local

```powershell
python app.py
```

ค่าเริ่มต้นจะเปิดที่:

```text
http://127.0.0.1:5000
```

## การรันแบบ Production-Style

```powershell
waitress-serve --listen=0.0.0.0:5000 wsgi:app
```

## Environment Variables

| ตัวแปร | ค่าเริ่มต้น | คำอธิบาย |
| --- | --- | --- |
| `TYPHOON_API_KEY` | ว่าง | API key หลักสำหรับ Typhoon chat, OCR และ ASR |
| `API_KEY` | ว่าง | fallback key หากไม่ได้ตั้ง `TYPHOON_API_KEY` |
| `TYPHOON_BASE_URL` | `https://api.opentyphoon.ai/v1` | base URL ของ Typhoon API |
| `HOST` | `127.0.0.1` | host สำหรับ `python app.py` |
| `PORT` | `5000` | port สำหรับ `python app.py` |
| `FLASK_DEBUG` | `false` | เปิด/ปิด Flask debug mode |
| `MAX_UPLOAD_BYTES` | `31457280` | ขนาด request upload สูงสุดโดยรวม 30 MB |
| `MAX_ASR_FILE_BYTES` | `26214400` | ขนาดไฟล์เสียงสูงสุด 25 MB |
| `MAX_OCR_FILE_BYTES` | `10485760` | ขนาดไฟล์ OCR สูงสุด 10 MB |
| `OCR_BATCH_SIZE` | `5` | จำนวนหน้า PDF สูงสุดที่ OCR ต่อ batch |
| `OCR_BATCH_WAIT_SECONDS` | `3` | เวลารอก่อนแจ้งว่ายังมีหน้า PDF ต่อ |
| `CHAT_TEMPERATURE` | `0.6` | temperature สำหรับ chat completion |
| `CHAT_TOP_P` | `0.6` | top-p สำหรับ chat completion |
| `CHAT_MAX_COMPLETION_TOKENS` | `2048` | token สูงสุดของคำตอบ |

## API Endpoints

| Method | Path | Content-Type | คำอธิบาย |
| --- | --- | --- | --- |
| `GET` | `/` | HTML | หน้าเว็บหลัก |
| `GET` | `/healthz` | JSON | health check คืนค่า `{ "ok": true }` |
| `GET` | `/models` | JSON | รายชื่อโมเดลที่เลือกได้ |
| `POST` | `/chat` | JSON → SSE | แชตกับ Typhoon โดยส่ง `messages` และ `model` |
| `POST` | `/smart-chat` | multipart/form-data → SSE | endpoint หลักของหน้าเว็บ รองรับข้อความ, history, model mode, ไฟล์แนบ, YouTube, URL OCR และข่าว |
| `POST` | `/ocr` | multipart/form-data → JSON | OCR ไฟล์ PDF/รูปภาพ |
| `POST` | `/asr` | multipart/form-data → JSON | ถอดเสียงไฟล์ audio |

### ตัวอย่าง `/chat`

```json
{
  "model": "typhoon-v2.1-12b-instruct",
  "messages": [
    { "role": "user", "content": "ช่วยสรุปข้อดีของ Flask ให้หน่อย" }
  ]
}
```

### ตัวอย่าง form field ของ `/smart-chat`

| Field | จำเป็น | คำอธิบาย |
| --- | --- | --- |
| `message` | ไม่เสมอ | ข้อความผู้ใช้ ถ้าแนบไฟล์อย่างเดียวก็เว้นได้ |
| `history` | ไม่ | JSON array ของ `{ role, content }` |
| `model_mode` | ไม่ | `fast` หรือ `thinking` ค่าเริ่มต้นคือ `fast` |
| `file` | ไม่ | ไฟล์ OCR หรือ ASR |
| `ocr_start_page` | ไม่ | หน้าเริ่มต้นสำหรับ OCR PDF |
| `ocr_page_count` | ไม่ | จำนวนหน้าที่ต้อง OCR ใน batch นั้น |

## ไฟล์ที่รองรับ

| งาน | นามสกุล | MIME ที่รองรับ | ขนาดเริ่มต้น |
| --- | --- | --- | --- |
| OCR รูปภาพ | `.png`, `.jpg`, `.jpeg` | `image/png`, `image/jpeg` | ไม่เกิน 10 MB |
| OCR PDF | `.pdf` | `application/pdf` | ไม่เกิน 10 MB |
| ASR | `.wav`, `.mp3`, `.flac`, `.ogg`, `.opus` | `audio/wav`, `audio/mpeg`, `audio/mp3`, `audio/flac`, `audio/ogg`, `audio/opus` | ไม่เกิน 25 MB |

## ลำดับการทำงานของ Smart Chat

1. รับ `message`, `history`, `model_mode` และไฟล์แนบจากหน้าเว็บ
2. ถ้ามีไฟล์แนบ ระบบตรวจว่าเป็น OCR หรือ ASR
3. ถ้าไม่มีไฟล์แนบ แต่ข้อความมี YouTube URL ระบบดึง transcript หรือ fallback เป็น ASR จากเสียง
4. ถ้าไม่มี YouTube แต่มี URL ของ PDF/รูปภาพ ระบบดาวน์โหลดไฟล์แล้ว OCR
5. ถ้าเป็นคำถามข่าว ระบบเลือกหมวดข่าวและดึงข่าวล่าสุดจาก Google News RSS
6. รวม context ที่ได้เข้ากับคำถามผู้ใช้
7. เลือกโมเดลตาม `model_mode`
8. ส่งคำตอบกลับหน้าเว็บแบบ SSE streaming

## โมเดลที่ใช้

| งาน | โมเดล |
| --- | --- |
| Chat เร็ว/ทั่วไป | `typhoon-v2.1-12b-instruct` |
| Chat วิเคราะห์หนัก | `typhoon-v2.5-30b-a3b-instruct` |
| OCR | `typhoon-ocr` |
| ASR | `typhoon-asr-realtime` |

ถ้าเรียก fast model แล้ว API key นั้นใช้โมเดลดังกล่าวไม่ได้ และ error มีข้อความ `Model not found` ระบบจะ fallback ไปใช้ power model อัตโนมัติ

## หมายเหตุด้านความปลอดภัย

- API key อ่านจาก environment ฝั่ง server เท่านั้น
- ไม่ส่ง Typhoon API key ไปที่ browser
- Flask debug ปิดเป็นค่าเริ่มต้น
- มี security headers: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`
- OCR service ใช้ lock ตอนตั้งค่า environment ชั่วคราว เพราะ library ภายนอกอ่าน key จาก environment variables
- หน้าเว็บ sanitize Markdown ด้วย DOMPurify ก่อนแสดงผล

## การตรวจสอบหลังติดตั้ง

เปิดแอปแล้วเข้า:

```text
http://127.0.0.1:5000/healthz
```

ควรได้ผลลัพธ์:

```json
{ "ok": true }
```

จากนั้นลองเข้า `http://127.0.0.1:5000` เพื่อใช้งานหน้าแชต
