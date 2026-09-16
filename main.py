import logging
import os
import threading
from typing import Optional

import requests
from flask import Flask
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ==========================================
# تنظیمات متغیرهای محیطی
# ==========================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("متغیر TELEGRAM_BOT_TOKEN تنظیم نشده است.")

if not GEMINI_API_KEY:
    raise ValueError("متغیر GEMINI_API_KEY تنظیم نشده است.")

SIGNATURE = "@zoootrope"
MAX_MESSAGE_LENGTH = 4000

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ==========================================
# وب‌سرور Flask برای فعال نگه داشتن سرویس (Render)
# ==========================================

server = Flask(__name__)


@server.route("/")
def index():
    return "Bot is active!", 200


def run_flask():
    port = int(os.environ.get("PORT", 10000))
    # NOTE: dev server OK for Render keepalive endpoint
    server.run(host="0.0.0.0", port=port)


# ==========================================
# Google Gemini API (Direct HTTP)
# ==========================================

SYSTEM_PROMPT = f"""
تو یک دستیار تخصصی برای کانال انیمیشن {SIGNATURE} هستی.
وظیفه: متن/کپشن/پست انیمیشنی زیر را به فارسی روان، جذاب و مناسب تلگرام ترجمه و بازنویسی کن.

قوانین:
1) لحن: حرفه‌ای و خوش‌خوان (نه خیلی رسمی، نه خیلی محاوره‌ای).
2) اصطلاحات رایج انیمیشن (layout, timing, compositing, stop-motion, etc) درست و دقیق برگردانده شوند.
3) اگر لینک داخل متن هست، حفظ شود (همان‌طور که هست).
4) اگر اسم اثر/استودیو/کارگردان داخل متن هست، حذف نشود.
5) در صورت نیاز 2 تا 6 هشتگ مرتبط اضافه کن (نه زیاد).
6) در انتهای خروجی حتماً امضا را دقیقا در یک خط جدا بیاور:
{SIGNATURE}
""".strip()


def call_gemini_generate(text: str, model: str) -> Optional[str]:
    """
    Calls Google Generative Language API (v1beta) generateContent endpoint.
    Returns text if success; otherwise None.
    """
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={GEMINI_API_KEY}"
    )

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": f"{SYSTEM_PROMPT}\n\nمتن ورودی:\n{text}"}],
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "topP": 0.95,
            "maxOutputTokens": 1024,
        },
    }

    try:
        res = requests.post(url, json=payload, timeout=60)
    except Exception as e:
        logger.exception(f"Request error for model={model}: {e}")
        return None

    if res.status_code != 200:
        logger.error(f"Gemini {model} returned {res.status_code}:
