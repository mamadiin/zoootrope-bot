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
# تنظیمات
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
# سرور Flask برای زنده نگه‌داشتن وب‌سرویس
# ==========================================

server = Flask(__name__)

@server.route("/")
def index():
    return "Bot is running fine!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    server.run(host="0.0.0.0", port=port)

# ==========================================
# ارتباط مستقیم با Google Gemini API
# ==========================================

SYSTEM_PROMPT = (
    "تو یک دستیار حرفه‌ای برای کانال تلگرامی تخصصی انیمیشن (@zoootrope) هستی.\n"
    "وظیفه تو دریافت پست‌ها، اخبار، متن‌ها یا زیرنویس‌های مربوط به انیمیشن (به زبان‌های انگلیسی، روسی یا سایر زبان‌ها) "
    "و بازنویسی یا ترجمه دقیق آن‌ها به زبان فارسی روان، جذاب و استاندارد برای انتشار در کانال است.\n\n"
    "قوانین مهم:\n"
    "1. لحن باید جذاب، ژورنالیستی، حرفه‌ای و خوانا باشد.\n"
    "2. اصطلاحات تخصصی انیمیشن را درست به کار ببر.\n"
    "3. هشتگ‌های مرتبط مثل #انیمیشن، نام کارگردان، نام استودیو یا سبک را در صورت مناسب بودن اضافه کن.\n"
    "4. اگر متنی دارای لینک است، لینک‌ها را در ترجمه فارسی درون متن روی کلمات مناسب حفظ کن.\n"
    "5. در انتهای متن خروجی حتماً این امضا قرار بگیرد:\n"
    "@zoootrope"
)

def generate_animation_post(text: str) -> Optional[str]:
    # استفاده از مدل‌های پایدار و رسمی Gemini
    models_to_try = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash"]
    
    for model in models_to_try:
        url = f")s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ==========================================
# سرور Flask برای زنده نگه‌داشتن وب‌سرویس
# ==========================================

server = Flask(__name__)

@server.route("/")
def index():
    return "Bot is running fine!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    server.run(host="0.0.0.0", port=port)

# ==========================================
# ارتباط مستقیم با Google Gemini API
# ==========================================

SYSTEM_PROMPT = (
    "تو یک دستیار حرفه‌ای برای کانال تلگرامی تخصصی انیمیشن (@zoootrope) هستی.\n"
    "وظیفه تو دریافت پست‌ها، اخبار، متن‌ها یا زیرنویس‌های مربوط به انیمیشن (به زبان‌های انگلیسی، روسی یا سایر زبان‌ها) "
    "و بازنویسی یا ترجمه دقیق آن‌ها به زبان فارسی روان، جذاب و استاندارد برای انتشار در کانال است.\n\n"
    "قوانین مهم:\n"
    "1. لحن باید جذاب، ژورنالیستی، حرفه‌ای و خوانا باشد.\n"
    "2. اصطلاحات تخصصی انیمیشن را درست به کار ببر.\n"
    "3. هشتگ‌های مرتبط مثل #انیمیشن، نام کارگردان، نام استودیو یا سبک را در صورت مناسب بودن اضافه کن.\n"
    "4. اگر متنی دارای لینک است، لینک‌ها را در ترجمه فارسی درون متن روی کلمات مناسب حفظ کن.\n"
    "5. در انتهای متن خروجی حتماً این امضا قرار بگیرد:\n"
    "@zoootrope"
)

def generate_animation_post(text: str) -> Optional[str]:
    # استفاده از مدل‌های پایدار و رسمی Gemini
    models_to_try = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash"]
    
    for model in models_to_try:
        url = f" است.")
        return

    await update.message.reply_text("در حال ارسال درخواست راه‌اندازی مجدد سرور...")
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
        await message.reply_text("خطا در پردازش با هوش مصنوعی. لطفاً لاگ سرور را بررسی کنید.")
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

    print("Bot is running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
