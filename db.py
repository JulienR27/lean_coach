from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from models import Base, Message
from db_utils import content_to_json, content_from_json
from collections import defaultdict

engine = create_engine("sqlite:///lean_bot.db")
LocalSession = scoped_session(sessionmaker(bind=engine))

def init_db():
    Base.metadata.create_all(engine)

def load_all_messages():
    users_conversation_history = defaultdict(list)
    local_session = LocalSession()
    try:
        messages = local_session.query(Message).order_by(Message.chat_id, Message.timestamp).all()
        for msg in messages:
            try:
                content = content_from_json(msg.content)
                users_conversation_history[msg.chat_id].append(content)
            except Exception as e:
                print(f"[Error] Message {msg.id} corrupted : {e}")
    finally:
        local_session.close()
    return users_conversation_history

def save_message(chat_id, content):
    local_session = LocalSession()
    try:
        new_msg = Message(chat_id=chat_id, content=content_to_json(content))
        local_session.add(new_msg)
        local_session.commit()
    finally:
        local_session.close()