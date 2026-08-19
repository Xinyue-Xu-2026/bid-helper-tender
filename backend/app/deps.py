from app.db import Database


def get_db():
    db = Database()
    db.init_schema()
    yield db
