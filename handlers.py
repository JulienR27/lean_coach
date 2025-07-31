import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ContextTypes
from google import genai
from google.genai import types
from db import engine, LocalSession, load_all_messages, save_message
from reminder_utils import schedule_reminder, list_reminders
from models import User

# === CONFIGURATION ===
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
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
welcome_message_unauthorized = """👋 Bonjour ! Je suis votre futur coach en lean management.\n
                                    Vous n'avez pas encore accès à mes services.\n
                                    Si vos souhaitez un accès tapez "/id" dans ce chat."""

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


def start_factory(users_chat_history):
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if await check_auth(update, context):
            chat_id = update.message.chat_id
            await context.bot.send_message(chat_id=chat_id, text=welcome_message)
            print("New authorized user with chat_id:", chat_id)
            # chat history update
            content = types.Content(role="model", parts=[types.Part(text=welcome_message)])
            users_chat_history[chat_id].append(content)
            save_message(chat_id=chat_id, content=content)
            # chats_history = load_data("chats_history.json")
            # chats_history[chat_id] = [types.Content(role="model", parts=[types.Part(text=welcome_message_authorized)])]
            # save_data(chats_history)
    return start_factory

def handle_message_factory(users_chat_history, scheduler):
    async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if await check_auth(update, context):
            user_input = update.message.text
            chat_id = update.effective_chat.id
            print("update.effective_chat.id : ", chat_id)
            # handling chat history
            content = types.Content(
                        role="user",
                        parts=[types.Part(text=user_input)]
                        )
            users_chat_history[chat_id].append(content)
            save_message(chat_id, content)
            # add tools
            config = types.GenerateContentConfig(
                        system_instruction=instruction,
                        tools=[tools],
                        )
            response = client.models.generate_content(
                    model="gemini-2.0-flash",
                    config=config,
                    contents=users_chat_history[chat_id]
            )
            # history update
            content = response.candidates[0].content
            users_chat_history[chat_id].append(content)
            save_message(chat_id, content)
            # function call handling
            parts = content.parts
            if call := parts[0].function_call:
                if call.name == "schedule_reminder":
                    args = call.args
                    reminder_date = schedule_reminder(**args, scheduler=scheduler, chat_id=chat_id, bot_token=TELEGRAM_BOT_TOKEN)
                    # Create a function response part
                    function_response_part = types.Part.from_function_response(
                                                name=call.name,
                                                response=reminder_date
                                                )  
                    users_chat_history[chat_id].append(types.Content(role="user", parts=[function_response_part]))
                    call_result_response = client.models.generate_content(
                        model="gemini-2.0-flash",
                        config=config,
                        contents=users_chat_history[chat_id],
                    )
                    # history update
                    content = call_result_response.candidates[0].content
                    users_chat_history[chat_id].append(content)
                    save_message(chat_id, content)
                    # response after function call
                    await context.bot.send_message(chat_id=chat_id, text=call_result_response.text)
            # Normal response
            else:
                await context.bot.send_message(chat_id=chat_id, text=parts[0].text)
            print(f"users_conversation_history for chat {chat_id}: \n", users_chat_history[chat_id])

    return handle_message


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