import os
import threading
from flask import Flask
from telegram.ext import ApplicationBuilder, CommandHandler

# -----------------------------
# Flask app برای Render
# -----------------------------
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)

# -----------------------------
# هندلرهای ربات
# -----------------------------
async def start(update, context):
    await update.message.reply_text("سلام! ربات فعاله ✅")

# -----------------------------
# اجرای اصلی
# -----------------------------
def main():
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")

    application = ApplicationBuilder().token(bot_token).build()

    # مهم: حذف webhook قبلی برای جلوگیری از Conflict
    application.bot.delete_webhook(drop_pending_updates=True)

    application.add_handler(CommandHandler("start", start))

    print("Starting Flask server...")
    threading.Thread(target=run_flask, daemon=True).start()

    print("Starting Telegram bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    from telegram import Update
    main()
