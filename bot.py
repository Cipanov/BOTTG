import logging
import os
from io import BytesIO
import time

from openai import OpenAI
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes, filters
)

# ---------- Настройка ----------
# Получаем токены из переменных окружения Render
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

if not OPENAI_API_KEY or not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("Не заданы OPENAI_API_KEY и/или TELEGRAM_BOT_TOKEN в переменных окружения Render")

client = OpenAI(api_key=OPENAI_API_KEY)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
log = logging.getLogger("tg-bot")

SYSTEM_PROMPT = (
    "Ты — полезный и дружелюбный ассистент. "
    "Отвечай по-русски, кратко и по делу."
)

# ---------- Хелперы ----------
async def send_typing(ctx: ContextTypes.DEFAULT_TYPE, chat_id: int):
    try:
        await ctx.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    except Exception:
        pass

async def generate_text_reply(user_text: str) -> str:
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text}
        ],
        temperature=0.6,
        max_tokens=600,
    )
    return response.choices[0].message.content.strip()

async def transcribe_voice(bytes_data: bytes, filename: str = "voice.ogg") -> str:
    f = BytesIO(bytes_data)
    f.name = filename
    transcript = client.audio.transcriptions.create(
        model="whisper-1",
        file=f,
    )
    return transcript.text.strip()

# ---------- Хендлеры ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я ИИ-бот на OpenAI. Напиши сообщение или отправь голосовое 🎙️"
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = (update.message.text or "").strip()
    if not user_text:
        return
    await send_typing(context, update.effective_chat.id)
    try:
        reply = await generate_text_reply(user_text)
        await update.message.reply_text(reply)
    except Exception as e:
        log.exception("OpenAI error")
        await update.message.reply_text("Извините, произошла ошибка. Попробуйте позже.")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    voice = update.message.voice
    if not voice:
        return
    await send_typing(context, update.effective_chat.id)
    try:
        file = await context.bot.get_file(voice.file_id)
        bio = BytesIO()
        await file.download(out=bio)
        audio_bytes = bio.getvalue()
        text = await transcribe_voice(audio_bytes)
        reply = await generate_text_reply(text)
        await update.message.reply_text(f"🎤 Ваше сообщение: {text}\n\n💬 Ответ: {reply}")
    except Exception as e:
        log.exception("Voice handling error")
        await update.message.reply_text("Ошибка при обработке голосового сообщения")

# ---------- Запуск бота с обработкой ошибок ----------
def main():
    max_retries = 5
    retry_delay = 10  # seconds
    
    for attempt in range(max_retries):
        try:
            app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
            app.add_handler(CommandHandler("start", start))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
            app.add_handler(MessageHandler(filters.VOICE, handle_voice))
            
            log.info(f"Starting bot (attempt {attempt + 1}/{max_retries})...")
            app.run_polling()
            
        except Exception as e:
            log.error(f"Bot failed with error: {e}")
            if attempt < max_retries - 1:
                log.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                log.error("Max retries exceeded. Bot stopped.")
                raise

if __name__ == "__main__":
    main()
