import os
from sqlalchemy import create_engine, text, select
from sqlalchemy.orm import Session

from dbmodel import Base, Document, DocumentChunk

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

def search_documents(query_vector: list) -> list[DocumentChunk]:
    with Session(engine) as session:
        # Use l2_distance (Euclidean) or cosine_distance
        # We order by distance (ascending) and limit to top 5 results
        query_results = session.scalars(select(DocumentChunk)
            .order_by(DocumentChunk.content_vector.l2_distance(query_vector))
            .limit(5)).all()
        
        results = []
        for chunk in query_results:
            results.append({
                "title": chunk.document.title,
                "url": chunk.document.url,
                "chunk": chunk.content,
                "id": f"{chunk.document.id}-{chunk.order_index}",
                "document_id": chunk.document_id,
                "order_index": chunk.order_index,
            })
        
        return results
    
    return []