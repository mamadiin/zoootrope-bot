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
# تنظیمات
# ==========================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is missing")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY is missing")

SIGNATURE = "@zoootrope"
MAX_MESSAGE_LENGTH = 4000

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ==========================================
# وب‌سرور Flask برای Render
# ==========================================

server = Flask(__name__)

@server.route("/")
def index():
    return "Bot is active!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    server.run(host="0.0.0.0", port=port)

# ==========================================
# اتصال به هوش مصنوعی گوگل (Gemini API)
# ==========================================

SYSTEM_PROMPT = (
    "تو یک دستیار تخصصی برای کانال انیمیشن @zoootrope هستی.\n"
    "وظیفه: متن/کپشن/پست انیمیشنی زیر را به فارسی روان، جذاب و مناسب تلگرام ترجمه و بازنویسی کن.\n\n"
    "قوانین:\n"
    "1) لحن: حرفه‌ای، پرانرژی و خوش‌خوان برای مخاطبان انیمیشن.\n"
    "2) اصطلاحات تخصصی انیمیشن و کامپوزیت درست ترجمه شوند.\n"
    "3) اگر لینکی داخل متن هست، عیناً حفظ شود.\n"
    "4) نام آثار و هنرمندان حذف نشوند.\n"
    "5) در صورت نیاز چند هشتگ مرتبط اضافه کن.\n"
    "6) در انتهای خروجی حتماً امضای @zoootrope در یک خط جداگانه آورده شود."
)

def call_gemini(text: str, model_name: str) -> Optional[str]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": f"{SYSTEM_PROMPT}\n\nمتن ورودی:\n{text}"}
                ]
            }
        ]
    }
    try:
        res = requests.post(url, json=payload, timeout=60)
        if res.status_code != 200:
            logger.error("Gemini %s error %s: %s", model_name, res.status_code, res.text)
            return None
        data = res.json()
        candidates = data.get("candidates", [])
        if not candidates:
            return None
        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            return None
        return parts[0].get("text", "").strip()
    except Exception as e:
        logger.exception("Gemini call error: %s", e)
        return None

def generate_animation_post(text: str) -> Optional[str]:
    # اولویت با مدل‌های فعال و پرسرعت گوگل
    models = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-1.5-flash"]
    for model in models:
        result = call_gemini(text, model)
        if result:
            if SIGNATURE not in result:
                result = result + "\n\n" + SIGNATURE
            return result
    return None

# ==========================================
# هندلرهای تلگرام
# ==========================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"سلام! پست یا خبر انیمیشنی رو بفرست تا آماده‌ش کنم.\n\n{SIGNATURE}"
    )

def chunk_text(text: str, size: int = MAX_MESSAGE_LENGTH):
    for i in range(0, len(text), size):
        yield text[i : i + size]

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    text = msg.text or msg.caption
    if not text or not text.strip():
        return
    
    await msg.chat.send_action(action=ChatAction.TYPING)
    result = generate_animation_post(text.strip())
    
    if not result:
        await msg.reply_text(
            f"متأسفانه دریافت پاسخ از هوش مصنوعی انجام نشد. لطفاً مجدداً امتحان کنید.\n\n{SIGNATURE}"
        )
        return
        
    for chunk in chunk_text(result):
        await msg.reply_text(chunk)

# ==========================================
# اجرای ربات
# ==========================================

def main():
    threading.Thread(target=run_flask, daemon=True).start()
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT | filters.CAPTION, handle_message))
    logger.info("Bot is running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
