import logging
import os
from io import BytesIO

from dotenv import load_dotenv
from openai import OpenAI
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes, filters
)

# ---------- Настройка ----------
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

if not OPENAI_API_KEY or not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("Не заданы OPENAI_API_KEY и/или TELEGRAM_BOT_TOKEN в .env")

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
    response = client.responses.create(
        model=OPENAI_MODEL,
        input=[
            {"role": "system", "content": [{"type": "text", "text": SYSTEM_PROMPT}]},
            {"role": "user", "content": [{"type": "text", "text": user_text}]},
        ],
        temperature=0.6,
        max_output_tokens=600,
    )
    return response.output_text.strip()

async def transcribe_voice(bytes_data: bytes, filename: str = "voice.ogg") -> str:
    f = BytesIO(bytes_data)
    f.name = filename
    transcript = client.audio.transcriptions.create(
        model="gpt-4o-mini-transcribe",
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
        await update.message.reply_text(f"Ошибка: {e}")

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
        await update.message.reply_text(f"📝 Расшифровка: {text}\n\n💬 Ответ: {reply}")
    except Exception as e:
        log.exception("Voice handling error")
        await update.message.reply_text(f"Ошибка при обработке голосового: {e}")

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    log.info("Bot started")
    app.run_polling()

if __name__ == "__main__":
    main()
import os
import telegram
from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
