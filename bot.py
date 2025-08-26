import logging
import os
from io import BytesIO
import time

import openai
from telegram import Update, ChatAction
from telegram.ext import (
    Updater, CommandHandler, MessageHandler, Filters, CallbackContext
)

# ---------- Настройка ----------
# Получаем токены из переменных окружения Render
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-3.5-turbo")

if not OPENAI_API_KEY or not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("Не заданы OPENAI_API_KEY и/или TELEGRAM_BOT_TOKEN в переменных окружения Render")

openai.api_key = OPENAI_API_KEY

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
def send_typing(context: CallbackContext, chat_id: int):
    try:
        context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    except Exception:
        pass

def generate_text_reply(user_text: str) -> str:
    response = openai.ChatCompletion.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text}
        ],
        temperature=0.6,
        max_tokens=600,
    )
    return response.choices[0].message.content.strip()

def transcribe_voice(bytes_data: bytes, filename: str = "voice.ogg") -> str:
    f = BytesIO(bytes_data)
    f.name = filename
    transcript = openai.Audio.transcribe("whisper-1", f)
    return transcript.text.strip()

# ---------- Хендлеры ----------
def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        "Привет! Я ИИ-бот на OpenAI. Напиши сообщение или отправь голосовое 🎙️"
    )

def handle_text(update: Update, context: CallbackContext):
    user_text = (update.message.text or "").strip()
    if not user_text:
        return
    send_typing(context, update.effective_chat.id)
    try:
        reply = generate_text_reply(user_text)
        update.message.reply_text(reply)
    except Exception as e:
        log.exception("OpenAI error")
        update.message.reply_text("Извините, произошла ошибка. Попробуйте позже.")

def handle_voice(update: Update, context: CallbackContext):
    voice = update.message.voice
    if not voice:
        return
    send_typing(context, update.effective_chat.id)
    try:
        file = context.bot.get_file(voice.file_id)
        bio = BytesIO()
        file.download(out=bio)
        audio_bytes = bio.getvalue()
        text = transcribe_voice(audio_bytes)
        reply = generate_text_reply(text)
        update.message.reply_text(f"🎤 Ваше сообщение: {text}\n\n💬 Ответ: {reply}")
    except Exception as e:
        log.exception("Voice handling error")
        update.message.reply_text("Ошибка при обработке голосового сообщения")

# ---------- Запуск бота ----------
def main():
    """Основная функция запуска"""
    try:
        # Создаем updater
        updater = Updater(TELEGRAM_BOT_TOKEN, use_context=True)
        
        # Добавляем обработчики
        dp = updater.dispatcher
        dp.add_handler(CommandHandler("start", start))
        dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))
        dp.add_handler(MessageHandler(Filters.voice, handle_voice))
        
        log.info("Starting bot...")
        
        # Запускаем бота
        updater.start_polling()
        updater.idle()
        
    except Exception as e:
        log.error(f"Bot failed with error: {e}")
        log.info("Restarting in 10 seconds...")
        time.sleep(10)
        main()  # Перезапускаем

if __name__ == "__main__":
    main()
