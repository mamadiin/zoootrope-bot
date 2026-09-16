import asyncio
import logging
import os
import threading
from typing import Optional

from openai import OpenAI
from flask import Flask
from telegram import Update
from telegram.constants import ParseMode
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
# کلید GapGPT شما در این متغیر قرار می‌گیرد
API_KEY = os.getenv("GEMINI_API_KEY")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("متغیر TELEGRAM_BOT_TOKEN تنظیم نشده است.")

if not API_KEY:
    raise ValueError("متغیر GEMINI_API_KEY تنظیم نشده است.")

# اتصال به اندپوینت GapGPT
client = OpenAI(
    api_key=API_KEY,
    base_url="https://api.gapgpt.app/v1"
)

# مدل متنی سریع و قوی
MODEL_NAME = "gpt-4o-mini"
SIGNATURE = "@zoootrope"
MAX_MESSAGE_LENGTH = 4000

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ==========================================
# سرور Flask برای زنده نگه‌داشتن وب‌سرویس رندر
# ==========================================

server = Flask(__name__)

@server.route("/")
def index():
    return "Bot is running fine!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    server.run(host="0.0.0.0", port=port)

# ==========================================
# منطق پرامپت و پردازش هوش مصنوعی
# ==========================================

SYSTEM_PROMPT = """
تو یک دستیار حرفه‌ای برای کانال تلگرامی تخصصی انیمیشن (@zoootrope) هستی.
وظیفه تو دریافت پست‌ها، اخبار، متن‌ها یا زیرنویس‌های مربوط به انیمیشن (به زبان‌های انگلیسی، روسی یا سایر زبان‌ها) و بازنویسی یا ترجمه دقیق آن‌ها به زبان فارسی روان، جذاب و استاندارد برای انتشار در کانال است.

قوانین مهم:
1. لحن باید جذاب، ژورنالیستی، حرفه‌ای و خوانا باشد.
2. اصطلاحات تخصصی انیمیشن را درست به کار ببر.
3. هشتگ‌های مرتبط مثل #انیمیشن، نام کارگردان، نام استودیو یا سبک را در صورت مناسب بودن اضافه کن.
4. اگر متنی دارای لینک است، لینک‌ها را در ترجمه فارسی درون متن روی کلمات مناسب حفظ کن.
5. در انتهای متن خروجی حتماً این امضا قرار بگیرد:
@zoootrope
"""

def generate_animation_post(text: str) -> Optional[str]:
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text}
            ],
            temperature=0.7,
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Error calling API: {e}")
        return None

# ==========================================
# هندلرهای تلگرام
# ==========================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "سلام! متن یا پست انیمیشنی را بفرست تا بازنویسی کنم.\n\n"
        "امضا کانال: @zoootrope"
    )
    await update.message.reply_text(welcome_text)

async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    deploy_hook = os.getenv("RENDER_DEPLOY_HOOK")
    if not deploy_hook:
        await update.message.reply_text("متغیر RENDER_DEPLOY_HOOK تنظیم نشده است.")
        return

    await update.message.reply_text("در حال ارسال درخواست راه‌اندازی مجدد سرور...")
    import requests
    try:
        res = requests.post(deploy_hook)
        if res.status_code in [200, 201]:
            await update.message.reply_text("درخواست ری‌استارت با موفقیت ارسال شد. سرویس ظرف ۱ الی ۲ دقیقه آینده بالا می‌آید.")
        else:
            await update.message.reply_text(f"خطا در ارسال درخواست. کد وضعیت: {res.status_code}")
    except Exception as e:
        await update.message.reply_text(f"خطا در ارسال درخواست: {e}")

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
        await message.reply_text("خطا در پردازش با هوش مصنوعی. لطفاً دوباره تست کنید.")
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
