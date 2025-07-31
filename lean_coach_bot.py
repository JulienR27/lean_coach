import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (ApplicationBuilder, CommandHandler,
                          MessageHandler, ContextTypes, filters)
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from reminder_utils import schedule_reminder, list_reminders
import asyncio
from google import genai
from google.genai import types
#from google.api_core import retry
from db import init_db
from models import User, Message, Reminder
from db_utils import content_to_json, content_from_json
from db import engine, LocalSession, load_all_messages, save_message
from handlers import handle_message_factory

# === CONFIGURATION ===
load_dotenv()
# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
#Loading messages history
init_db()
users_chat_history = load_all_messages()
# # To store jobId by chatId
user_jobs = dict()

welcome_message_authorized = """👋 Bonjour ! Je suis ton coach Lean. Envoie-moi un vocal après ta visite terrain, ou attends mes rappels !"""
welcome_message_unauthorized = """👋 Bonjour ! Je suis votre futur coach en lean management.\n
                                    Vous n'avez pas encore accès à mes services.\n
                                    Si vos souhaitez un accès tapez "/id" dans ce chat."""

# === IA ET OUTILS ===



# === HANDLERS ===
async def check_auth(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    session = LocalSession()
    try:
        user = session.query(User).filter_by(user_id=user_id).first()
        if not user:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="⛔️ Accès non autorisé. Envoyez /id pour obtenir votre identifiant et demander votre accès."
            )
            return False
        return True
    finally:
        session.close()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id # or update.effective_user.id ?
    if await check_auth(update, context):
        await context.bot.send_message(chat_id=chat_id, text=welcome_message_authorized)
        print("New authorized user with chat_id:", chat_id)
        # chat history update
        content = types.Content(role="model", parts=[types.Part(text=welcome_message_authorized)])
        users_chat_history[chat_id].append(content)
        save_message(chat_id=chat_id, content=content)
        # chats_history = load_data("chats_history.json")
        # chats_history[chat_id] = [types.Content(role="model", parts=[types.Part(text=welcome_message_authorized)])]
        # save_data(chats_history)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await update.message.voice.get_file()
    voice_path = f"voice_{update.message.from_user.id}.ogg"
    await file.download_to_drive(voice_path)

    # Placeholder: transcription à ajouter avec Whisper
    await context.bot.send_message(chat_id=update.effective_chat.id, text="🔊 Vocal reçu. J'analyserai bientôt son contenu (fonctionnalité en cours).")


async def get_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text(
        f"👤 Votre user_id est : {user_id}\n\n"
        "Transmettez-le à l'administrateur pour obtenir l'accès."
    )

# === INITIALISATION ===
if __name__ == '__main__':
    loop = asyncio.get_event_loop() # retrieve main loop
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Scheduler
    scheduler = BackgroundScheduler(jobstores={
        'default': SQLAlchemyJobStore(url='sqlite:///jobs.db')
    })
    scheduler.start()
    # App handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message_factory(users_chat_history, scheduler)))
    app.add_handler(CommandHandler("id", get_user_id))
    #app.add_handler(CommandHandler("list_reminders", list_reminders))

    print("🤖 Bot Lean Coach en cours d'exécution...")
    app.run_polling()
