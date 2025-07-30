from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime, timezone

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    chat_id = Column(Integer, primary_key=True)
    last_seen = Column(DateTime, default=datetime.now(timezone.utc))

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer)
    content = Column(String)  # Content object from google genai
    timestamp = Column(DateTime, default=datetime.now(timezone.utc))

class Reminder(Base):
    __tablename__ = "reminders"
    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer)
    message = Column(Text)
    run_at = Column(DateTime)