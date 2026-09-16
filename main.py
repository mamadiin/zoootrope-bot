import os
import sys
import re
import asyncio
from telegram import Update, InputMediaPhoto, InputMediaVideo
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from google import genai
from google.genai import types

# خواندن متغیرهای محیطی از Render
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# راه‌اندازی کلاینت رسمی Gemini
client = genai.Client(api_key=GEMINI_API_KEY)

# سیستم پرامپت دبیر ارشد خبری انیمیشن
PROMPT_SYSTEM = """
تو دبیر ارشد و خبرنگار تخصصی حوزه انیمیشن، جلوه‌های ویژه (VFX) و هنر دیجیتال برای رسانه تخصصی @zoootrope هستی.
وظیفه تو: تبدیل متن خام ورودی به یک پست خبری مستقل، بسیار جذاب، روان، حرفه‌ای و خواندنی به زبان فارسی.

قوانین حیاتی که باید رعایت کنی:
1. اصلاً ترجمه کلمه‌به‌کلمه نکن؛ مثل یک ژورنالیست مسلط متن را از نو بنویس.
2. اصطلاحات تخصصی انیمیشن و CG را درست و رایج در جامعه هنری به کار ببر.
3. تمام لینک‌های موجود در متن اصلی را دقیقاً در همان جایگاه مفهومی با تگ HTML حفظ کن: <a href="URL">متن لینک</a>
4. لحن حرفه‌ای، جذاب و ترغیب‌کننده باشد.
5. در انتهای پست حتماً امضای زیر را قرار بده:
@zoootrope
"""

# صف نگه‌داری آلبوم‌های ارسالی
media_groups = {}
media_group_locks = {}

def clean_html_tags(text: str) -> str:
    """حذف تگ‌های غیرمجاز تلگرام و نگه‌داشتن تگ‌های استاندارد"""
    allowed_tags = ['b', 'strong', 'i', 'em', 'u', 'ins', 's', 'strike', 'del', 'a', 'code', 'pre']
    pattern = r'<\/?([a-zA-Z0-9]+)(?:\s+[^>]*)?>'
    
    def replace_tag(match):
        tag = match.group(1).lower()
        if tag in allowed_tags:
            return match.group(0)
        return ""
        
    return re.sub(pattern, replace_tag, text)

async def rewrite_with_gemini(text: str) -> str:
    """ارسال متن به هوش مصنوعی Gemini جهت بازنویسی خبری"""
    try:
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=text,
            config=types.GenerateContentConfig(
                system_instruction=PROMPT_SYSTEM,
                temperature=0.7,
                safety_settings=[
                    types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
                ]
            )
        )
        return clean_html_tags(response.text.strip())
    except Exception as e:
        print(f"Gemini API Error: {e}", file=sys.stderr)
        return f"⚠️ خطا در بازنویسی خبر: {e}"

async def process_media_group(media_group_id: str, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت ارسال آلبوم عکس/ویدیو پس از دریافت کامل تمام مدیاها"""
    await asyncio.sleep(3.5)
    
    data = media_groups.pop(media_group_id, None)
    media_group_locks.pop(media_group_id, None)
    if not data:
        return

    chat_id = data["chat_id"]
    caption = data.get("caption", "")
    items = data.get("items", [])

    final_text = ""
    if caption:
        final_text = await rewrite_with_gemini(caption)

    media_list = []
    for i, item in enumerate(items):
        m_caption = final_text if i == 0 and final_text else None
        m_parse = ParseMode.HTML if m_caption else None
        
        if item["type"] == "photo":
            media_list.append(InputMediaPhoto(media=item["file_id"], caption=m_caption, parse_mode=m_parse))
        elif item["type"] == "video":
            media_list.append(InputMediaVideo(media=item["file_id"], caption=m_caption, parse_mode=m_parse))

    if media_list:
        try:
            await context.bot.send_media_group(chat_id=chat_id, media=media_list)
        except Exception as e:
            print(f"Error sending media group: {e}", file=sys.stderr)

async def handle_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg:
        return

    chat_id = update.effective_chat.id

    # مدیریت آلبوم‌ها (عکس/ویدیو چندتایی)
    if msg.media_group_id:
        mg_id = msg.media_group_id
        if mg_id not in media_groups:
            media_groups[mg_id] = {"chat_id": chat_id, "caption": "", "items": []}

        raw_caption = msg.caption_html or msg.caption or ""
        if raw_caption and not media_groups[mg_id]["caption"]:
            media_groups[mg_id]["caption"] = raw_caption

        if msg.photo:
            media_groups[mg_id]["items"].append({"type": "photo", "file_id": msg.photo[-1].file_id})
        elif msg.video:
            media_groups[mg_id]["items"].append({"type": "video", "file_id": msg.video.file_id})

        if mg_id not in media_group_locks:
            media_group_locks[mg_id] = True
            asyncio.create_task(process_media_group(mg_id, context))
        return

    # مدیریت پست تکی متنی
    if msg.text:
        rewritten = await rewrite_with_gemini(msg.text_html or msg.text)
        await msg.reply_text(rewritten, parse_mode=ParseMode.HTML, disable_web_page_preview=False)
        return

    # مدیریت پست تکی تصویری
    if msg.photo:
        caption = msg.caption_html or msg.caption or ""
        rewritten = await rewrite_with_gemini(caption) if caption else ""
        await msg.reply_photo(
            photo=msg.photo[-1].file_id,
            caption=rewritten,
            parse_mode=ParseMode.HTML if rewritten else None
        )
        return

    # مدیریت پست تکی ویدیویی
    if msg.video:
        caption = msg.caption_html or msg.caption or ""
        rewritten = await rewrite_with_gemini(caption) if caption else ""
        await msg.reply_video(
            video=msg.video.file_id,
            caption=rewritten,
            parse_mode=ParseMode.HTML if rewritten else None
        )
        return

def main():
    if not TELEGRAM_BOT_TOKEN or not GEMINI_API_KEY:
        print("Error: TELEGRAM_BOT_TOKEN or GEMINI_API_KEY is not set!", file=sys.stderr)
        return

    print("Bot is starting on Render...")
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.ALL, handle_post))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
