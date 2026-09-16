import os
import asyncio
import re
import urllib.parse
import requests
from flask import Flask
from threading import Thread
import google.generativeai as genai

from telegram import (
    Update,
    InputMediaPhoto,
    InputMediaVideo,
    InputMediaDocument,
    InputMediaAnimation
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# 1. تنظیمات وب‌سرور برای زنده نگه داشتن پروژه در Render
app = Flask(__name__)

@app.route('/')
def home():
    return "Zoootrope Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# 2. دریافت متغیرهای محیطی
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
RENDER_DEPLOY_HOOK = os.getenv("RENDER_DEPLOY_HOOK")
ADMIN_ID = os.getenv("ADMIN_ID", "7477253841")

if not TELEGRAM_BOT_TOKEN or not GEMINI_API_KEY:
    raise ValueError("لطفاً متغیرهای TELEGRAM_BOT_TOKEN و GEMINI_API_KEY را در تنظیمات وارد کنید.")

# 3. تنظیم Gemini API
genai.configure(api_key=GEMINI_API_KEY)
# استفاده از مدل پایدار gemini-2.5-flash
gemini_model = genai.GenerativeModel('gemini-2.5-flash')

# حافظه موقت برای آلبوم‌های چندرسانه‌ای (Media Group)
MEDIA_GROUPS = {}

def split_text_smart(text: str, max_length: int = 1000) -> list[str]:
    """شکستن متن‌های بلند به بخش‌های کوچک‌تر جهت رعایت سقف ۱۰۲۴ کاراکتری کاپشن تلگرام"""
    if len(text) <= max_length:
        return [text]
    
    paragraphs = text.split('\n\n')
    chunks = []
    current_chunk = ""

    for p in paragraphs:
        if len(current_chunk) + len(p) + 2 <= max_length:
            current_chunk = (current_chunk + '\n\n' + p).strip()
        else:
            if current_chunk:
                chunks.append(current_chunk)
            if len(p) > max_length:
                sentences = re.split(r'(?<=[.!?])\s+', p)
                current_chunk = ""
                for s in sentences:
                    if len(current_chunk) + len(s) + 1 <= max_length:
                        current_chunk = (current_chunk + ' ' + s).strip()
                    else:
                        if current_chunk:
                            chunks.append(current_chunk)
                        current_chunk = s
            else:
                current_chunk = p

    if current_chunk:
        chunks.append(current_chunk)

    return chunks

async def rewrite_text_with_gemini(original_text: str) -> str:
    """بازنویسی متن بر اساس قوانین کانال zoootrope"""
    if not original_text or not original_text.strip():
        return ""

    prompt = f"""
    شما یک ویرایشگر حرفه‌ای برای کانال تلگرامی تخصصی انیمیشن به نام @zoootrope هستید.
    وظیفه شما بازنویسی متن زیر به فارسی بسیار روان، جذاب، دقیق و تخصصی در حوزه انیمیشن است.

    قوانین بسیار مهم:
    ۱. هیچ‌گونه ایموجی (Emoji) در متن استفاده نکنید.
    ۲. هیچ‌گونه هشتگ (#) در متن قرار ندهید.
    ۳. تمام آیدی‌های تلگرام (مثل @username)، لینک‌ها و تبلیغات منبع اصلی را کاملاً حذف کنید.
    ۴. تمام لینک‌های هایپرلینک موجود در متن اصلی را دقیقاً روی همان کلمات یا کلمات معادل فارسی نگه دارید.
    ۵. در انتهای تمام شدهٔ متن، حتماً امضای @zoootrope را قرار دهید.

    متن اصلی برای بازنویسی:
    {original_text}
    """

    try:
        response = await asyncio.to_thread(gemini_model.generate_content, prompt)
        result_text = response.text.strip()
        if "@zoootrope" not in result_text:
            result_text += "\n\n@zoootrope"
        return result_text
    except Exception as e:
        print(f"Error in Gemini API: {e}")
        return f"{original_text}\n\n@zoootrope"

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! پست یا رسانه مورد نظر را بفرستید تا با سبک اختصاصی @zoootrope بازنویسی شود.\n\nبرای ریست سرور می‌توانید از دستور /restart استفاده کنید.")

async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور اختصاصی ادمین برای ریست و بازنشانی کامل سرور از طریق Render Deploy Hook"""
    user_id = str(update.effective_user.id)
    
    if user_id != str(ADMIN_ID):
        await update.message.reply_text("❌ شما دسترسی به این دستور را ندارید.")
        return

    if not RENDER_DEPLOY_HOOK:
        await update.message.reply_text("❌ متغیر RENDER_DEPLOY_HOOK در Environment تنظیم نشده است.")
        return

    await update.message.reply_text("🔄 در حال ارسال درخواست Clear Cache & Deploy به Render...\nلطفاً ۳۰ تا ۶۰ ثانیه صبر کنید.")
    
    try:
        # ارسال درخواست POST به Deploy Hook
        response = await asyncio.to_thread(requests.post, RENDER_DEPLOY_HOOK)
        if response.status_code in [200, 201]:
            await update.message.reply_text("✅ دستور Deploy با موفقیت به Render ارسال شد. سرور در حال ری‌استارت است.")
        else:
            await update.message.reply_text(f"❌ خطا در ریست سرور! کد پاسخ: {response.status_code}")
    except Exception as e:
        await update.message.reply_text(f"❌ خطا در برقراری ارتباط با Render: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return

    # ۱. حالت دریافت آلبوم (Media Group)
    if msg.media_group_id:
        mg_id = msg.media_group_id
        if mg_id not in MEDIA_GROUPS:
            MEDIA_GROUPS[mg_id] = {
                'messages': [],
                'caption': None,
                'task': None
            }
        
        MEDIA_GROUPS[mg_id]['messages'].append(msg)
        if msg.caption:
            MEDIA_GROUPS[mg_id]['caption'] = msg.caption

        if MEDIA_GROUPS[mg_id]['task']:
            MEDIA_GROUPS[mg_id]['task'].cancel()

        MEDIA_GROUPS[mg_id]['task'] = asyncio.create_task(process_media_group(mg_id, context))
        return

    # ۲. حالت پیام تک‌رسانه‌ای یا تک‌متنی
    caption_or_text = msg.caption or msg.text or ""
    rewritten_text = ""
    if caption_or_text.strip():
        await msg.reply_chat_action("typing")
        rewritten_text = await rewrite_text_with_gemini(caption_or_text)

    chunks = split_text_smart(rewritten_text, max_length=1000) if rewritten_text else [""]

    if msg.photo:
        await msg.reply_photo(photo=msg.photo[-1].file_id, caption=chunks[0])
    elif msg.video:
        await msg.reply_video(video=msg.video.file_id, caption=chunks[0])
    elif msg.animation:
        await msg.reply_animation(animation=msg.animation.file_id, caption=chunks[0])
    elif msg.document:
        await msg.reply_document(document=msg.document.file_id, caption=chunks[0])
    else:
        if chunks[0]:
            await msg.reply_text(chunks[0])

    for extra_chunk in chunks[1:]:
        await msg.reply_text(extra_chunk)

async def process_media_group(mg_id: str, context: ContextTypes.DEFAULT_TYPE):
    await asyncio.sleep(1.5)
    group_data = MEDIA_GROUPS.pop(mg_id, None)
    if not group_data:
        return

    messages = group_data['messages']
    original_caption = group_data['caption'] or ""

    rewritten_text = ""
    if original_caption.strip():
        rewritten_text = await rewrite_text_with_gemini(original_caption)

    chunks = split_text_smart(rewritten_text, max_length=1000) if rewritten_text else [""]

    media_list = []
    for i, msg in enumerate(messages):
        caption_to_set = chunks[0] if i == 0 else ""
        
        if msg.photo:
            media_list.append(InputMediaPhoto(media=msg.photo[-1].file_id, caption=caption_to_set))
        elif msg.video:
            media_list.append(InputMediaVideo(media=msg.video.file_id, caption=caption_to_set))
        elif msg.animation:
            media_list.append(InputMediaAnimation(media=msg.animation.file_id, caption=caption_to_set))
        elif msg.document:
            media_list.append(InputMediaDocument(media=msg.document.file_id, caption=caption_to_set))

    if media_list:
        first_msg = messages[0]
        await first_msg.reply_media_group(media=media_list)
        for extra_chunk in chunks[1:]:
            await first_msg.reply_text(extra_chunk)

def main():
    # روشن کردن سرور Web همزمان با ربات
    server_thread = Thread(target=run_flask)
    server_thread.daemon = True
    server_thread.start()

    # ساخت و راه‌اندازی ربات تلگرام
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("restart", restart_command))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))

    print("Bot is starting polling...")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
