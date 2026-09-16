import os
import threading
import logging
from flask import Flask
from google import genai
from telegram import Update, InputMediaPhoto, InputMediaVideo
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, filters

# Flask Web Server for Render
server = Flask(__name__)

@server.route('/')
def home():
    return "Zoootrope Bot is Live!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    server.run(host="0.0.0.0", port=port)

# API Keys
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

def extract_html_links(incoming_text, entities):
    if not incoming_text or not entities:
        return incoming_text or ""
    
    sorted_entities = sorted(entities, key=lambda e: e.offset, reverse=True)
    chars = list(incoming_text)
    
    for ent in sorted_entities:
        start = ent.offset
        end = start + ent.length
        if ent.type == "text_link":
            url = ent.url
            inner = "".join(chars[start:end])
            chars[start:end] = list(f'<a href="{url}">{inner}</a>')
            
    return "".join(chars)

def split_text_smart(text: str, max_len: int = 1000):
    if len(text) <= max_len:
        return text, ""
    
    split_index = text.rfind("\n\n", 0, max_len)
    if split_index == -1:
        split_index = text.rfind("\n", 0, max_len)
    if split_index == -1:
        split_index = text.rfind(" ", 0, max_len)
    if split_index == -1:
        split_index = max_len
        
    part1 = text[:split_index].strip()
    part2 = text[split_index:].strip()
    return part1, part2

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

    models_to_try = [
        'gemini-3.6-flash',
        'gemini-3.1-pro-preview',
        'gemini-2.5-flash',
        'gemini-2.5-pro'
    ]

    response_text = None
    last_error = None

    for model_name in models_to_try:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            if response and response.text:
                response_text = response.text.strip()
                break
        except Exception as e:
            last_error = e
            continue

    if not response_text:
        await status_msg.delete()
        await context.bot.send_message(
            chat_id=chat_id, 
            text=f"❌ خطایی رخ داد (تمام سهمیه‌ها مصرف شده است):\n{str(last_error)}"
        )
        return

    output_text = response_text
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

    if continuation_part:
        await context.bot.send_message(chat_id=chat_id, text=continuation_part, parse_mode="HTML", disable_web_page_preview=True)

media_groups = {}

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
        
    chat_id = msg.chat_id
    mg_id = msg.media_group_id

    text_content = msg.text or msg.caption or ""
    entities = msg.entities or msg.caption_entities or []
    formatted_text = extract_html_links(text_content, entities)

    item = None
    if msg.photo:
        item = {'type': 'photo', 'file_id': msg.photo[-1].file_id}
    elif msg.video:
        item = {'type': 'video', 'file_id': msg.video.file_id}
    elif msg.animation:
        item = {'type': 'animation', 'file_id': msg.animation.file_id}

    if mg_id:
        if mg_id not in media_groups:
            media_groups[mg_id] = {
                'items': [],
                'text': '',
                'chat_id': chat_id,
                'task': None
            }
        
        if item:
            media_groups[mg_id]['items'].append(item)
        if formatted_text:
            media_groups[mg_id]['text'] = formatted_text
            
        if media_groups[mg_id]['task']:
            media_groups[mg_id]['task'].cancel()
            
        async def delayed_process():
            import asyncio
            await asyncio.sleep(2)
            group_data = media_groups.pop(mg_id, None)
            if group_data:
                await process_payload(
                    context, 
                    group_data['chat_id'], 
                    group_data['text'], 
                    group_data['items']
                )
                
        import asyncio
        media_groups[mg_id]['task'] = asyncio.create_task(delayed_process())
    else:
        media_items = [item] if item else []
        await process_payload(context, chat_id, formatted_text, media_items)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام! پست، متن، عکس یا ویدیوی مورد نظرت رو بفرست تا اون رو به فرمت آماده انتشار در کانال @zoootrope تبدیل کنم.\n\n@zoootrope"
    )

def main():
    threading.Thread(target=run_flask, daemon=True).start()
    
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    
    print("Bot is polling...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
