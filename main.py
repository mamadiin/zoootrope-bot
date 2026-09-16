import os
import threading
from flask import Flask
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

# 1. تنظیمات وب‌سرور برای رندر (حیاتی برای سرویس رایگان)
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    # رندر معمولا روی پورت 10000 کار می‌کند
    flask_app.run(host='0.0.0.0', port=10000)

# شروع وب‌سرور در یک ترد جداگانه
threading.Thread(target=run_flask, daemon=True).start()

# 2. منطق اصلی ربات تلگرام
async def start(update, context):
    await update.message.reply_text("سلام! ربات فعال است.")

def main():
    # دریافت توکن‌ها از محیط (در پنل رندر تنظیم کردید)
    BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    
    # ساخت اپلیکیشن ربات
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # اینجا هندلرهای خودت را اضافه کن
    start_handler = CommandHandler('start', start)
    application.add_handler(start_handler)
    
    # اجرای ربات
    print("Bot is starting...")
    application.run_polling()

if __name__ == '__main__':
    main()
