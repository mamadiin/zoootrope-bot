import asyncio
import logging
import os
import threading
from typing import Optional

import google.generativeai as genai
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

# =========================================================
# تنظیمات
# =========================================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("متغیر TELEGRAM_BOT_TOKEN تنظیم نشده است.")

if not GEMINI_API_KEY:
    raise ValueError("متغیر GEMINI_API_KEY تنظیم نشده است.")

genai.configure(api_key=GEMINI_API_KEY)

# مدل پایدار و مطمئن
MODEL_NAME = "gemini-1.5-flash"
SIGNATURE = "@zoootrope"
MAX_MESSAGE_LENGTH = 4000

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

# حافظه موقت برای جلوگیری از تکرار پیام‌های آلبومی
MEDIA_GROUPS = {}

# =========================================================
# سرور Flask برای Render
# =========================================================

flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "Zoootrope bot is running.", 200

@flask_app.route("/health")
def health():
    return "OK", 200

def run_flask():
    port = int(os.getenv("PORT", "10000"))
    flask_app.run(host="0.0.0.0", port=port, use_reloader=False)

# =========================================================
# توابع کمکی متن
# =========================================================

def split_text_smart(text: str, max_length: int = MAX_MESSAGE_LENGTH) -> list[str]:
    if len(text) <= max_length:
        return [text]
    parts = []
    remaining = text.strip()
    while len(remaining) > max_length:
        cut_positions = [
            remaining.rfind("\n\n", 0, max_length),
            remaining.rfind("\n", 0, max_length),
            remaining.rfind(". ", 0, max_length),
            remaining.rfind(" ", 0, max_length),
        ]
        cut = max(cut_positions)
        if cut < max_length // 2:
            cut = max_length
        part = remaining[:cut].strip()
        if part:
            parts.append(part)
        remaining = remaining[cut:].strip()
    if remaining:
        parts.append(remaining)
    return parts

def add_signature(text: str) -> str:
    text = text.strip()
    if not text:
        return SIGNATURE
    if text.endswith(SIGNATURE):
        return text
    return f"{text}\n\n{SIGNATURE}"

def remove_unwanted_prefix(text: str) -> str:
    prefixes = ["متن بازنویسی‌شده:", "بازنویسی:", "نسخه بازنویسی‌شده:", "Rewritten text:"]
    cleaned = text.strip()
    for prefix in prefixes:
        if cleaned.lower().startswith(prefix.lower()):
            cleaned = cleaned[len(prefix):].strip()
    return cleaned

# =========================================================
# ارتباط با Gemini
# =========================================================

def rewrite_text_sync(original_text: str) -> str:
    prompt = f"""
تو ویراستار فارسی یک کانال تلگرامی درباره انیمیشن هستی.
متن زیر را به فارسی روان، طبیعی و حرفه‌ای بازنویسی کن.

قوانین بسیار مهم:
1. مفهوم و اطلاعات اصلی متن حفظ شود.
2. متن را ترجمه یا بازنویسی روان کن؛ توضیح اضافه نده.
3. هیچ ایموجی، هشتگ یا نام منبع اضافه نکن.
4. اگر نام منبع در متن وجود دارد (مثل نام کانال‌ها)، آن را حذف کن؛ اما نام فیلم، کارگردان، استودیو یا شخصیت را حذف نکن.
5. اگر متن دارای لینک است، لینک‌ها را حفظ کن و روی همان کلمات نگه دار.
6. امضای @zoootrope را خودت اضافه نکن؛ برنامه اضافه می‌کند.
7. فقط متن نهایی را برگردان.

متن اصلی:
----------------
{original_text}
----------------
"""
    model = genai.GenerativeModel(MODEL_NAME)
    response = model.generate_content(
        prompt,
        generation_config={"temperature": 0.7, "max_output_tokens": 2048},
    )
    result = getattr(response, "text", None)
    if not result or not result.strip():
        raise RuntimeError("پاسخی از Gemini دریافت نشد.")
    return remove_unwanted_prefix(result)

async def rewrite_text_with_gemini(original_text: str) -> Optional[str]:
    if not original_text or not original_text.strip():
        return None
    try:
        rewritten = await asyncio.to_thread(rewrite_text_sync, original_text)
        return add_signature(rewritten)
    except Exception as error:
        logger.exception("Gemini error: %s", error)
        return None

# =========================================================
# ارسال پاسخ
# =========================================================

async def send_long_text(update: Update, text: str, reply_to_message_id: Optional[int] = None):
    if not update.effective_chat:
        return
    parts = split_text_smart(text)
    for index, part in enumerate(parts):
        kwargs = {
            "chat_id": update.effective_chat.id,
            "text": part,
            "parse_mode": ParseMode.HTML,
            "disable_web_page_preview": False,
        }
        if index == 0 and reply_to_message_id:
            kwargs["reply_to_message_id"] = reply_to_message_id

        try:
            await update.get_bot().send_message(**kwargs)
        except Exception:
            plain_kwargs = {
                "chat_id": update.effective_chat.id,
                "text": part,
                "disable_web_page_preview": False,
            }
            if index == 0 and reply_to_message_id:
                plain_kwargs["reply_to_message_id"] = reply_to_message_id
            await update.get_bot().send_message(**plain_kwargs)

# =========================================================
# دستورات و پردازش پیام‌ها
# =========================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! متن یا پست انیمیشنی را بفرست تا بازنویسی کنم.")

async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    deploy_hook = os.getenv("RENDER_DEPLOY_HOOK")
    if not deploy_hook:
        await update.message.reply_text("متغیر RENDER_DEPLOY_HOOK تنظیم نشده است.")
        return
    try:
        import requests
        response = await asyncio.to_thread(requests.post, deploy_hook, timeout=20)
        if 200 <= response.status_code < 300:
            await update.message.reply_text("درخواست راه‌اندازی مجدد ارسال شد.")
        else:
            await update.message.reply_text(f"خطا در دیپلوی. کد: {response.status_code}")
    except Exception as error:
        logger.exception("Restart error: %s", error)
        await update.message.reply_text("راه‌اندازی مجدد انجام نشد.")

async def process_media_group_delayed(media_group_id: str, context: ContextTypes.DEFAULT_TYPE):
    await asyncio.sleep(1.5)
    data = MEDIA_GROUPS.pop(media_group_id, None)
    if not data:
        return
    
    update = data["update"]
    caption = data["caption"]
    
    if not caption:
        return

    await update.message.chat.send_action("typing")
    rewritten = await rewrite_text_with_gemini(caption)
    
    if rewritten is None:
        await update.message.reply_text("خطا در پردازش با Gemini. لطفاً لاگ Render را چک کنید.")
        return

    await send_long_text(update, rewritten, reply_to_message_id=update.message.message_id)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    # مدیریت آلبوم عکس/ویدیو
    if update.message.media_group_id:
        mg_id = update.message.media_group_id
        caption = update.message.caption or ""
        
        if mg_id not in MEDIA_GROUPS:
            MEDIA_GROUPS[mg_id] = {"update": update, "caption": caption}
            asyncio.create_task(process_media_group_delayed(mg_id, context))
        else:
            if caption and not MEDIA_GROUPS[mg_id]["caption"]:
                MEDIA_GROUPS[mg_id]["caption"] = caption
        return

    # پیام معمولی متنی یا تک‌رسانه‌ای
    text = update.message.text or update.message.caption
    if not text or not text.strip():
        return

    await update.message.chat.send_action("typing")
    rewritten = await rewrite_text_with_gemini(text)

    if rewritten is None:
        await update.message.reply_text("خطا در ارتباط با Gemini. لطفا چند لحظه دیگر تست کنید.")
        return

    await send_long_text(update, rewritten, reply_to_message_id=update.message.message_id)

# =========================================================
# اجرای اصلی
# =========================================================

def main():
    threading.Thread(target=run_flask, daemon=True).start()

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("restart", restart_command))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.ATTACHMENT & ~filters.COMMAND, handle_message))

    logger.info("Bot started successfully.")
    application.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
