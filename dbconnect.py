import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from dbmodel import Base, Document

DB_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@db:5432/knowledge_base")
engine = create_engine(DB_URL)

with engine.connect() as conn:
    # Enable the extension
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    conn.commit()

Base.metadata.create_all(engine)

def add_document(document: Document):
    with Session(engine) as session:
        session.add(document)
        session.commit()