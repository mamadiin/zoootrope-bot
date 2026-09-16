import os
import asyncio
import threading
from flask import Flask
from telegram import Update, InputMediaPhoto, InputMediaVideo
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

# Dictionary to collect media group messages
MEDIA_GROUPS = {}

def extract_html_links(incoming_text, entities):
    if not entities or not incoming_text:
        return incoming_text
    html_text = incoming_text
    for entity in sorted(entities, key=lambda e: e.offset, reverse=True):
        if entity.type == "text_link":
            url = entity.url
            start_idx = entity.offset
            end_idx = entity.offset + entity.length
            text_snippet = incoming_text[start_idx:end_idx]
            replacement = f'<a href="{url}">{text_snippet}</a>'
            html_text = html_text[:start_idx] + replacement + html_text[end_idx:]
    return html_text

def split_text_smart(text, max_len=1000):
    """Splits text smoothly at line breaks if it exceeds max_len."""
    if len(text) <= max_len:
        return text, ""
    
    split_pos = text.rfind('\n', 0, max_len)
    if split_pos == -1:
        split_pos = text.rfind(' ', 0, max_len)
    if split_pos == -1:
        split_pos = max_len
        
    return text[:split_pos].strip(), text[split_pos:].strip()

async def process_payload(context: ContextTypes.DEFAULT_TYPE, chat_id: int, formatted_input: str, media_items: list):
    if not client:
        await context.bot.send_message(chat_id=chat_id, text="خطا: کلید GEMINI_API_KEY تنظیم نشده است.")
        return

    status_msg = await context.bot.send_message(chat_id=chat_id, text="⏳ در حال خلاصه‌نویسی و آماده‌سازی پست...")

    prompt = (
        "You are an expert animation, 3D/2D animation, stop-motion, and CG editor for the @zoootrope Telegram channel.\n"
        "Summarize and rewrite the following post into fluent, concise, highly engaging Persian suitable for an animation channel.\n\n"
        "CRITICAL RULES:\n"
        "1. Summarize the text efficiently while keeping all core facts, names, technical specs, dates, and essential nuances intact.\n"
        "2. Do NOT use any emojis.\n"
        "3. Do NOT use any hashtags (#).\n"
        "4. Remove any original Telegram channel credits/usernames at the end, but DO NOT mention other sources.\n"
        "5. Preserve all HTML links (e.g. <a href='...'>text</a>) exactly as they are, attached to the equivalent translated words.\n"
        "6. Output ONLY the final ready-to-publish Persian text.\n\n"
        f"Input Content:\n{formatted_input}"
    )

    try:
        response = client.models.generate_content(
            model='gemini-3.6-flash',
            contents=prompt,
        )
        
        output_text = response.text.strip()
        
        # Ensure ending always has @zoootrope signature
        if "@zoootrope" not in output_text:
            output_text += "\n\n@zoootrope"

        await status_msg.delete()

        caption_part, continuation_part = split_text_smart(output_text, max_len=1000)

        if media_items:
            if len(media_items) == 1:
                item = media_items[0]
                m_type, file_id = item['type'], item['file_id']
                
                if m_type == 'photo':
                    await context.bot.send_photo(chat_id=chat_id, photo=file_id, caption=caption_part, parse_mode="HTML")
                elif m_type == 'video':
                    await context.bot.send_video(chat_id=chat_id, video=file_id, caption=caption_part, parse_mode="HTML")
                elif m_type == 'animation':
                    await context.bot.send_animation(chat_id=chat_id, animation=file_id, caption=caption_part, parse_mode="HTML")
            else:
                # Media group (Album)
                media_group_list = []
                for i, item in enumerate(media_items):
                    c = caption_part if i == 0 else None
                    pm = "HTML" if i == 0 else None
                    
                    if item['type'] == 'photo':
                        media_group_list.append(InputMediaPhoto(media=item['file_id'], caption=c, parse_mode=pm))
                    elif item['type'] == 'video':
                        media_group_list.append(InputMediaVideo(media=item['file_id'], caption=c, parse_mode=pm))
                
                await context.bot.send_media_group(chat_id=chat_id, media=media_group_list)
        else:
            await context.bot.send_message(chat_id=chat_id, text=caption_part, parse_mode="HTML", disable_web_page_preview=True)

        # Send remaining text if it exceeded single caption size limit
        if continuation_part:
            await context.bot.send_message(chat_id=chat_id, text=continuation_part, parse_mode="HTML", disable_web_page_preview=True)

    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ خطایی رخ داد:\n{str(e)}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return

    incoming_text = msg.text or msg.caption or ""
    entities = msg.entities or msg.caption_entities
    formatted_input = extract_html_links(incoming_text, entities)

    # Detect media type
    media_info = None
    if msg.photo:
        media_info = {'type': 'photo', 'file_id': msg.photo[-1].file_id}
    elif msg.video:
        media_info = {'type': 'video', 'file_id': msg.video.file_id}
    elif msg.animation:
        media_info = {'type': 'animation', 'file_id': msg.animation.file_id}

    media_group_id = msg.media_group_id

    if media_group_id:
        if media_group_id not in MEDIA_GROUPS:
            MEDIA_GROUPS[media_group_id] = {
                'text': formatted_input,
                'items': [],
                'chat_id': msg.chat_id,
                'task': None
            }
        
        if formatted_input and not MEDIA_GROUPS[media_group_id]['text']:
            MEDIA_GROUPS[media_group_id]['text'] = formatted_input

        if media_info:
            MEDIA_GROUPS[media_group_id]['items'].append(media_info)

        # Cancel previous timer and reset for batch processing
        if MEDIA_GROUPS[media_group_id]['task']:
            MEDIA_GROUPS[media_group_id]['task'].cancel()

        async def delayed_process():
            await asyncio.sleep(2.0)  # Wait 2s for all album items to arrive
            group_data = MEDIA_GROUPS.pop(media_group_id, None)
            if group_data:
                await process_payload(context, group_data['chat_id'], group_data['text'], group_data['items'])

        MEDIA_GROUPS[media_group_id]['task'] = asyncio.create_task(delayed_process())

    else:
        # Single message processing
        media_items = [media_info] if media_info else []
        await process_payload(context, msg.chat_id, formatted_input, media_items)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام! ربات زوتروپ آماده است. 🎬\n\n"
        "هر پستی (حتی آلبوم عکس/ویدیو) بفرستید، آن را خلاصه‌نویسی کرده، بدون ایموجی و هشتگ، با حفظ لینک‌ها و با امضای @zoootrope خروجی می‌دهد."
    )

def main():
    threading.Thread(target=run_flask, daemon=True).start()
    
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        print("Error: TELEGRAM_BOT_TOKEN environment variable not set!")
        return

    application = ApplicationBuilder().token(bot_token).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.VIDEO | filters.ANIMATION | filters.CAPTION, handle_message))
    
    print("Zoootrope Bot is running...")
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
