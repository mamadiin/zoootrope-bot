import os
import threading
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from google import genai

# 1. Web server for Render port check
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Zoootrope Bot is Live!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

# 2. Gemini API Client Initialization
gemini_api_key = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=gemini_api_key) if gemini_api_key else None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام! ربات زوتروپ آماده است. 🎬\n\n"
        "هر پستی (متن یا کپشن) به هر زبانی بفرستی، "
        "آن را به یک پست خبری روون و جذاب فارسی همراه با حفظ کامل لینک‌ها و جزئیات بازنویسی می‌کنم."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    incoming_text = update.message.text or update.message.caption
    
    if not incoming_text:
        return

    if not client:
        await update.message.reply_text("خطا: کلید GEMINI_API_KEY در سرویس رندر تنظیم نشده است.")
        return

    # Preserve hyperlinks from Telegram entities into HTML format
    entities = update.message.entities or update.message.caption_entities
    formatted_input = incoming_text
    
    if entities:
        html_text = incoming_text
        for entity in sorted(entities, key=lambda e: e.offset, reverse=True):
            if entity.type == "text_link":
                url = entity.url
                start = entity.offset
                end = entity.offset + entity.length
                text_snippet = incoming_text[start:end]
                replacement = f'<a href="{url}">{text_snippet}</a>'
                html_text = html_text[:start] + replacement + html_text[end:]
        formatted_input = html_text

    status_msg = await update.message.reply_text("⏳ در حال تحلیل و نگارش پست...")

    prompt = (
        "You are an expert animation, 3D/2D animation, stop-motion, and CG editor/writer for @zoootrope Telegram channel.\n"
        "Rewrite the following post into fluent, natural, engaging Persian suitable for an animation news channel.\n\n"
        "CRITICAL RULES:\n"
        "1. Keep all details, technical specs, names, dates, and nuances intact.\n"
        "2. Do NOT shorten or omit details.\n"
        "3. Preserve all HTML links (e.g. <a href='...'>text</a>) exactly as they are, attached to the equivalent translated words.\n"
        "4. Output ONLY the final ready-to-publish Persian text, formatted neatly.\n\n"
        f"Input Content:\n{formatted_input}"
    )

    try:
        # اصلاح نام مدل جمینای به نسخه استاندارد پایدار
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        
        output_text = response.text
        
        try:
            await status_msg.edit_text(output_text, parse_mode="HTML", disable_web_page_preview=True)
        except Exception:
            await status_msg.edit_text(output_text)

    except Exception as e:
        await status_msg.edit_text(f"❌ خطایی رخ داد:\n{str(e)}")

def main():
    threading.Thread(target=run_flask, daemon=True).start()
    
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        print("Error: TELEGRAM_BOT_TOKEN environment variable not set!")
        return

    application = ApplicationBuilder().token(bot_token).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT | filters.CAPTION, handle_message))
    
    print("Zoootrope Bot is running...")
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
