import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import (ApplicationBuilder, CommandHandler,
                          MessageHandler, ContextTypes, filters)
from apscheduler.schedulers.background import BackgroundScheduler
import asyncio
from google import genai
from google.genai import types
from db import init_db
from models import User, Message, Reminder
from db_utils import content_to_json, content_from_json
from db import load_all_messages, save_message
#from google.api_core import retry

# === CONFIGURATION ===
load_dotenv()
# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
#Loading messages history
init_db()
users_conversation_history = load_all_messages()
# # To store jobId by chatId
user_jobs = dict()
# Google GenAI
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
client = genai.Client(api_key=GOOGLE_API_KEY)
# is_retriable = lambda e: (isinstance(e, genai.errors.APIError) and e.code in {429, 503})
# if not hasattr(genai.models.Models.generate_content, '__wrapped__'):
#   genai.models.Models.generate_content = retry.Retry(
#       predicate=is_retriable)(genai.models.Models.generate_content)
instruction = """"Tu es un coach lean. Tu coaches les dirigeants / managers pour leur démarche de lean management.
            Tu es en mesure de répondre à toutes les interrogations concernant les démarches à effectuer mais aussi,
            sur demande de l'utilisateur, de planifier les gemba walks en préparant un reminder automatiques qui contiendra
            les différentes questions à poser aux équipes métiers lors de ce gemba walk.
            Tu utiliseras pour cela la fonction "schedule_reminder", qui prend en argument le moment du reminder ainsi que le message de préparation à l'entretien 
            que tu auras rédigé et qui inclura les différentes questions à poser.
            Pour générer ces questions, tu utiliseras toutes les informations que t'auras donné au préalable l'utilisateur lors 
            de la conversation ainsi que tes compétences en la matière.
            Tu lui proposeras de planifier un rappel à la date de son souhait. Il n'est pas utile de préciser le message de rappel que tu enverras.
            Après les gemba walks, l'utilisateur pourra t'envoyer un résumé (en texte ou vocal) du déroulé et des réponses aux questions et
            tu pourras l'aider à faire un débrief de ce dernier et à envisager la suite à donner, avec, par exemple, les actions à mener.
            """
            # Génère 5 questions utiles à poser lors d'une visite terrain (Gemba Walk), en lien avec l'amélioration continue, 
            # la résolution de problèmes et l'implication des équipes."""
welcome_message = """👋 Bonjour ! Je suis ton coach Lean. Envoie-moi un vocal après ta visite terrain, ou attends mes rappels !"""

# === IA ET OUTILS ===
schedule_reminder_declaration = {
                    "name": "schedule_reminder",
                    "description": "Planifie un rappel lean pour plus tard",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "time_minutes": {
                                "type": "integer",
                                "description": "Temps en minutes avant le rappel"
                            },
                            "message": {
                                "type": "string",
                                "description": "Message à envoyer"
                            }
                        },
                        "required": ["time_minutes", "message"]
                    }
                }

tools = types.Tool(function_declarations=[schedule_reminder_declaration])

def schedule_reminder(time_minutes: int, message: str, scheduler, chat_id, context, loop):
    """Schedule the reminder at the given time.
    Args: 
    - time_minutes : time in minutes before the reminder
    - message : content of the message sent with the reminder (advices about the questions to ask and objectives to achieve)
    """
    reminder_date = datetime.now() + timedelta(minutes=int(time_minutes))
    
    def send_reminder():
        asyncio.run_coroutine_threadsafe(
            context.bot.send_message(chat_id=chat_id, text=message),
            loop  # boucle passée depuis le main thread  
        )
    # add job
    job = scheduler.add_job(
            send_reminder,
            trigger='date', 
            run_date=reminder_date
            )
    # Store job ID
    if chat_id not in user_jobs:
        user_jobs[chat_id] = []
    user_jobs[chat_id].append(job.id)
    # Start the scheduler
    if not scheduler.running:
        scheduler.start()
    return {"reminder_date": str(reminder_date)}


# === HANDLERS ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id # or update.effective_user.id ?
    print("New active user:", chat_id)
    await context.bot.send_message(chat_id=chat_id, text=welcome_message)
    # chat history update
    content = types.Content(role="model", parts=[types.Part(text=welcome_message)])
    users_conversation_history[chat_id].append(content)
    save_message(chat_id=chat_id, content=content)
    # chats_history = load_data("chats_history.json")
    # chats_history[chat_id] = [types.Content(role="model", parts=[types.Part(text=welcome_message)])]
    # save_data(chats_history)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    chat_id = update.effective_chat.id
    print("update.effective_chat.id : ", chat_id)
    # handling chat history
    content = types.Content(
                role="user",
                parts=[types.Part(text=user_input)]
                )
    users_conversation_history[chat_id].append(content)
    save_message(chat_id, content)
    # add tools
    config = types.GenerateContentConfig(
                system_instruction=instruction,
                tools=[tools],
                )
    response = client.models.generate_content(
            model="gemini-2.0-flash",
            config=config,
            contents=users_conversation_history[chat_id]
    )
    # history update
    content = response.candidates[0].content
    users_conversation_history[chat_id].append(content)
    save_message(chat_id, content)
    # function call handling
    parts = content.parts
    if call := parts[0].function_call:
        if call.name == "schedule_reminder":
            args = call.args
            reminder_date = schedule_reminder(**args, scheduler=scheduler, chat_id=chat_id, context=context, loop=loop)
            # Create a function response part
            function_response_part = types.Part.from_function_response(
                                        name=call.name,
                                        response=reminder_date
                                        )  
            users_conversation_history[chat_id].append(types.Content(role="user", parts=[function_response_part]))
            call_result_response = client.models.generate_content(
                model="gemini-2.0-flash",
                config=config,
                contents=users_conversation_history[chat_id],
            )
            # history update
            content = call_result_response.candidates[0].content
            users_conversation_history[chat_id].append(content)
            save_message(chat_id, content)
            # response after function call
            await context.bot.send_message(chat_id=chat_id, text=call_result_response.text)
    # Normal response
    else:
        await context.bot.send_message(chat_id=chat_id, text=parts[0].text)
    print(f"users_conversation_history for chat {chat_id}: \n", users_conversation_history[chat_id])


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await update.message.voice.get_file()
    voice_path = f"voice_{update.message.from_user.id}.ogg"
    await file.download_to_drive(voice_path)

    # Placeholder: transcription à ajouter avec Whisper
    await context.bot.send_message(chat_id=update.effective_chat.id, text="🔊 Vocal reçu. J'analyserai bientôt son contenu (fonctionnalité en cours).")

async def list_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    jobs = user_jobs.get(chat_id, [])
    active_jobs = []
    for job_id in jobs:
        job = scheduler.get_job(job_id)
        if job and job.next_run_time:  # on s'assure que le job est encore planifié
            active_jobs.append(job)

    if not active_jobs:
        await context.bot.send_message(chat_id=chat_id, text="❌ Aucun rappel programmé.")
        return
    
    messages = []
    for job in active_jobs:
        if job:
            run_time = job.next_run_time.strftime("%Y-%m-%d %H:%M:%S")
            messages.append(f"🕒 Rappel prévu à : {run_time}")
    await context.bot.send_message(chat_id=chat_id, text="\n".join(messages))

# === INITIALISATION ===
if __name__ == '__main__':
    loop = asyncio.get_event_loop() # retrieve main loop
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Scheduler
    scheduler = BackgroundScheduler()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.add_handler(CommandHandler("list_reminders", list_reminders))

    print("🤖 Bot Lean Coach en cours d'exécution...")
    app.run_polling()
