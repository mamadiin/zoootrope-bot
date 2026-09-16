import os
import threading
from flask import Flask
from telegram.ext import ApplicationBuilder, CommandHandler

# ۱. ساخت وب‌سرور کاذب برای رندر
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Bot is live and running!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

# ۲. تابع نمونه برای تست ربات تلگرام
async def start(update, context):
    await update.message.reply_text("سلام! ربات آنلاین است و روی سرویس ابری کار می‌کند. 🚀")

def main():
    # روشن کردن Flask در یک Thread جداگانه
    threading.Thread(target=run_flask, daemon=True).start()
    
    # گرفتن توکن ربات از Environment Variables رندر
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        print("خطا: توکن تلگرام یافت نشد!")
        return

    # ساخت و اجرای ربات تلگرام
    application = ApplicationBuilder().token(bot_token).build()
    
    # اضافه کردن هندلر تست
    application.add_handler(CommandHandler('start', start))
    
    # اجرای ربات (Polling)
    print("Telegram Bot is polling...")
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
