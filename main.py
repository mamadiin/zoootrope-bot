import os
import threading
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from google import genai
from google.genai import types

# ۱. ساخت وب‌سرور برای زنده نگه داشتن سرویس در Render
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Zoootrope Bot is Live!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

# ۲. راه‌اندازی کلاینت جمینای
gemini_api_key = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=gemini_api_key) if gemini_api_key else None

# دستور /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام! ربات زوتروپ آماده است. 🎬\n\n"
        "هر پستی (متن یا کپشن همراه عکس/ویدیو) به هر زبانی بفرستی یا فوروارد کنی، "
        "اون رو برات به یک پست خبری روون و جذاب فارسی همراه با حفظ کامل لینک‌ها و جزئیات بازنویسی می‌کنم."
    )

# تابع اصلی پردازش متن و خبرها
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # دریافت متن (چه پیام متنی ساده باشد، چه کپشنِ عکس/ویدیو)
    incoming_text = update.message.text or update.message.caption
    
    if not incoming_text:
        return

    if not client:
        await update.message.reply_text("خطا: کلید GEMINI_API_KEY تنظیم نشده است.")
        return

    # استخراج لینک‌های داخل متن (اگر وجود داشته باشد)
    entities = update.message.entities or update.message.caption_entities
    formatted_input = incoming_text
    
    # اگر متنی دارای لینک هایپرتکست بود، آن را به ساختار قابل فهم HTML تبدیل می‌کنیم
    if entities:
        # ساخت متن همراه با تگ‌های HTML لینک‌ها
        offset_shift = 0
        html_text = incoming_text
        # بررسی معکوس برای عدم تداخل ایندکس‌ها
        for entity in sorted(entities, key=lambda e: e.offset, reverse=True):
            if entity.type == "text_link":
                url = entity.url
                start = entity.offset
                end = entity.offset + entity.length
                text_snippet = incoming_text[start:end]
                replacement = f'<a href="{url}">{text_snippet}</a>'
                html_text = html_text[:start] + replacement + html_text[end:]
        formatted_input = html_text

    # ارسال پیام «در حال پردازش...» به کاربر
    status_msg = await update.message.reply_text("⏳ در حال تحلیل و نگارش پست...")

    # پرامپت دقیق برای Gemini جهت بازنویسی خبری
    prompt = f"""
تو یک نویسنده، مترجم و سردبیر متخصص در حوزه انیمیشن، سينما و صنعت CG (کارتون، سه‌بعدی، دو‌بعدی، استاپ‌موشن نشده است.")
        return

    # استخراج لینک‌های داخل متن (اگر وجود داشته باشد)
    entities = update.message.entities or update.message.caption_entities
    formatted_input = incoming_text
    
    # اگر متنی دارای لینک هایپرتکست بود، آن را به ساختار قابل فهم HTML تبدیل می‌کنیم
    if entities:
        # ساخت متن همراه با تگ‌های HTML لینک‌ها
        offset_shift = 0
        html_text = incoming_text
        # بررسی معکوس برای عدم تداخل ایندکس‌ها
        for entity in sorted(entities, key=lambda e: e.offset, reverse=True):
            if entity.type == "text_link":
                url = entity.url
                start = entity.offset
                end = entity.offset + entity.length
                text_snippet = incoming_text[start:end]
                replacement = f'<a href="{url}">{text_snippet}</a>'
                html_text = html_text[:start] + replacement + html_text[end:]
        formatted_input = html_text

    # ارسال پیام «در حال پردازش...» به کاربر
    status_msg = await update.message.reply_text("⏳ در حال تحلیل و نگارش پست...")

    # پرامپت دقیق برای Gemini جهت بازنویسی خبری
    prompt = f"""
تو یک نویسنده، مترجم و سردبیر متخصص در حوزه انیمیشن، سينما و صنعت CG (کارتون، سه‌بعدی، دو‌بعدی، استاپ‌موشن و غیره) برای کانال تلگرامی @zoootrope هستی.

وظیفه تو:
متن زیر را (که ممکن است یک خبر، پست تحلیلی یا کوتاه باشد) دریافت کرده و آن را به یک **پست جذاب، روون و حرفه‌ای به زبان فارسی** تبدیل کنی.

قواعد مهم:
۱. **حفظ کامل جزئیات:** هیچ اطلاعات، نام، آمار، تکنیک یا دیتیلی نباید حذف شود.
۲. **لحن و e:
        # اگر در HTML پارسر تلگرام خطایی رخ داد، بدون پارس ارسال کن
        try:
            await status_msg.edit_text(response.text)
        except Exception:
            await status_msg.edit_text(f"❌ خطایی رخ داد:\n{str(e)}")

def main():
    # ۱. اجرای Flask در ترد جداگانه
    threading.Thread(target=run_flask, daemon=True).start()
    
    # ۲. گرفتن توکن تلگرام
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        print("Error: TELEGRAM_BOT_TOKEN not set!")
        return

    # ۳. ساخت ربات
    application = ApplicationBuilder().token(bot_token).build()
    
    # ۴. اضافه کردن هندلرها
    application.add_handler(CommandHandler('start', start))
    # هندلر برای دریافت متن یا کپشن رسانه‌ها
    application.add_handler(MessageHandler(filters.TEXT | filters.CAPTION, handle_message))
    
    print("Zoootrope Bot is polling and ready!")
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
