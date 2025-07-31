from telegram import Bot
from telegram import Update
from telegram.ext import ContextTypes
from datetime import datetime, timedelta
import asyncio


def send_reminder(chat_id: int, message: str, bot_token: str):
    bot = Bot(token=bot_token)
    # Create a new asyncio loop in this thread (to avoid "RuntimeWarning: coroutine 'Bot.send_message' was never awaited")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(bot.send_message(chat_id=chat_id, text=message))
    loop.close()


def schedule_reminder(time_minutes: int, message: str, scheduler, chat_id: int, bot_token: str):
    """Schedule the reminder at the given time.
    Args: 
    - time_minutes : time in minutes before the reminder
    - message : content of the message sent with the reminder (advices about the questions to ask and objectives to achieve)
    """
    reminder_date = datetime.now() + timedelta(minutes=int(time_minutes))
    
    # add job
    job = scheduler.add_job(
            func=send_reminder,
            trigger='date', 
            run_date=reminder_date,
            args=[chat_id, message, bot_token],
            id=f"reminder_{chat_id}_{int(reminder_date.timestamp())}"
            )
    # # Store job ID
    # if chat_id not in user_jobs:
    #     user_jobs[chat_id] = []
    # user_jobs[chat_id].append(job.id)
    # Start the scheduler
    # if not scheduler.running:
    #     scheduler.start()
    return {"reminder_date": str(reminder_date)}


async def list_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE, scheduler, user_jobs):
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