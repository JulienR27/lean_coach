import json
import os
from datetime import datetime
import asyncio
from google.genai import types
from google.genai.types import Content

def save_data(data, filename):
    with open(filename, "w") as f:
        json.dump(data, f, indent=2, default=str)

def save_chats_history_data(users_chat_history, filename="chats_history_data.json"):
    data = {
            str(k): [c.to_dict() for c in v] for k, v in users_chat_history.items()
        }
    save_data(data, filename)

def save_jobs_data(stored_jobs, filename="jobs_data.json"):
    data = {"jobs": stored_jobs }
    save_data(data, filename)


def load_data(filename):
    data = dict()
    if os.path.exists(filename):
        with open(filename, "r") as f:
            data = json.load(f)
            data = {
                int(k): [types.Content.from_dict(c) for c in v]
                for k, v in data.items()
            }
        
        return data


def content_to_json(content: Content) -> str:
    return json.dumps(content.to_json_dict())

def content_from_json(json_string: str) -> Content:
    content_dict = json.loads(json_string)
    return Content(**content_dict)


def reprogram_jobs(stored_jobs, scheduler, context, loop):
    for job in stored_jobs:
        chat_id = job["chat_id"]
        message = job["message"]
        run_time = datetime.fromisoformat(job["reminder_time"])

        if run_time > datetime.now():
            scheduler.add_job(
                lambda chat_id=chat_id, message=message: asyncio.run_coroutine_threadsafe(
                    context.bot.send_message(chat_id=chat_id, text=message),
                    loop
                ),
                trigger='date',
                run_date=run_time
            )