import asyncio
import logging
import os
import threading
from typing import Optional
import requests
from flask import Flask
from telegram import Update
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
# وب‌سرور Flask برای فعال نگه داشتن سرویس
# ==========================================

server = Flask(__name__)

@server.route("/")
def index():
    return "Bot is active!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    server.run(host="0.0.0.0", port=port)

# ==========================================
# ارتباط مستقیم با Google Gemini API
# ==========================================

SYSTEM_PROMPT = """
تو یک دستیار تخصصی برای کانال انیمیشن @zoootrope هستی.
وظیفه: متن، زیرنویس یا پست انیمیشنی زیر را به فارسی جذاب، روان و مناسب کانال تلگرام ترجمه و بازنویسی کن.

قوانین:
1. لحن باید حرفه‌ای، روان و استاندارد انیمیشن باشد.
2. اصطلاحات انیمیشن به درستی برگردانده شوند.
3. هشتگ‌های مرتبط مثل #انیمیشن یا نام اثر در صورت نیاز اضافه شود.
4. اگر لینکی در متن وجود دارد، آن را در جای مناسب حفظ کن.
5. در انتهای پیام حتماً این امضا درج شود:
@zoootrope
"""

def generate_animation_post(text: str) -> Optional[str]:
    models = ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro"]
    
    full_prompt = f"{SYSTEM_PROMPT}\n\nمتن ورودی:\n{text}"
    
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": full_prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.7
        }
    }

    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        try:
            res = requests.post(url, json=payload, timeout=45)
            if res.status_code == 200:
                data = res.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts and "text" in parts[0]:
                        return parts[0]["text"]
            else:
                logger.error(f"Gemini {model} returned status {res.status_code}: {res.text}")
        except Exception as e:
            logger.error(f"Error calling {model}: {e}")

    return None

# ==========================================
# هندلرهای تلگرام
# ==========================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "سلام! هر متن، خبر یا پست انیمیشنی داری بفرست تا برات ترجمه و آماده‌سازی کنم.\n\n"
        "امضا کانال: @zoootrope"
    )
    await update.message.reply_text(welcome_text)

async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    deploy_hook = os.getenv("RENDER_DEPLOY_HOOK")
    if not deploy_hook:
        await update.message.reply_text("متغیر RENDER_DEPLOY_HOOK تنظیم نشده است.")
        return

    await update.message.reply_text("در حال راه‌اندازی مجدد سرویس...")
    try:
        res = requests.post(deploy_hook, timeout=10)
        if res.status_code in [200, 201]:
            await update.message.reply_text("درخواست ری‌استارت با موفقیت ارسال شد.")
        else:
            await update.message.reply_text(f"خطا در ارسال درخواست: {res.status_code}")
    except Exception as e:
        await update.message.reply_text(f"خطا: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message:
        return

    text = message.text or message.caption
    if not text:
        return

    await message.reply_chat_action("typing")

    processed = generate_animation_post(text)
    if not processed:
        await message.reply_text("خطا در ارتباط با هوش مصنوعی. لطفاً دوباره تلاش کنید.")
        return

    if len(processed) <= MAX_MESSAGE_LENGTH:
        await message.reply_text(processed)
    else:
        for i in range(0, len(processed), MAX_MESSAGE_LENGTH):
            await message.reply_text(processed[i:i + MAX_MESSAGE_LENGTH])

# ==========================================
# اجرای ربات
# ==========================================

def main():
    threading.Thread(target=run_flask, daemon=True).start()

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("restart", restart_command))
    app.add_handler(MessageHandler(filters.TEXT | filters.Caption(), handle_message))

    print("Bot is polling...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
