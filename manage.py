from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, User, Message
from datetime import datetime

DATABASE_URL = "sqlite:///lean_bot.db"
engine = create_engine(DATABASE_URL)

def clear_messages_table():
    confirmation = input("Confirmer suppression de toutes les lignes de la table 'messages' ? (oui/non): ")
    try:
        if confirmation.lower() == "oui":
            engine = create_engine(DATABASE_URL)
            Session = sessionmaker(bind=engine)
            session = Session()

            deleted = session.query(Message).delete()
            session.commit()
            print(f"✅ {deleted} message(s) supprimé(s).")
        else:
            print("Action annulée.")
    finally:
        session.close()    

def drop_table(table_name: str):
    confirmation = input(f"⚠️ Confirmer suppression table {table_name} ? (oui/non): ")
    if confirmation.lower() == "oui":
        table = Base.metadata.tables[table_name]
        table.drop(engine)
        print(f"✅ Table {table_name} supprimée.")
    else:
        print("❌ Annulé.")

def add_user(user_id: int, username=None):
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        existing = session.query(User).filter_by(user_id=user_id).first()
        if existing:
            print("✅ Utilisateur déjà autorisé.")
        else:
            user = User(user_id=user_id, username=username, last_seen=datetime.utcnow())
            session.add(user)
            session.commit()
            print(f"✅ Utilisateur {user_id} ajouté avec succès.")
    finally:
        session.close() 

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "clear_messages_table":
            clear_messages_table()
        elif cmd == "drop_table":
            if len(sys.argv) == 3:
                table_name = str(sys.argv[2])
                drop_table(table_name)
            else:
                print("Usage : python manage.py drop_table <ustable_name>")
        elif cmd == "add_user":
            if len(sys.argv) >= 3:
                user_id = int(sys.argv[2])
                username = sys.argv[3] if len(sys.argv) > 3 else None
                add_user(user_id, username)
            else:
                print("Usage : python manage.py add_user <user_id> [username]")
        else:
            print("Commande inconnue.")
    else:
        print("Usage: python manage.py <commande>")