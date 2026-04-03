import os
from sqlalchemy import create_engine, text, select, func
from sqlalchemy.orm import Session, selectinload

from dbmodel import Base, Document, DocumentChunk

DB_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@db:5432/knowledge_base")
engine = create_engine(DB_URL)

with engine.connect() as conn:
    # Enable the extension
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    conn.commit()

Base.metadata.create_all(engine)

def add_document(document: Document):
    with Session(engine, expire_on_commit=False) as session:
        session.add(document)
        session.commit()

def update_document(document: Document):
    with Session(engine, expire_on_commit=False) as session:
        session.merge(document)
        session.commit()

def get_document_by_url(url: str) -> Document | None:
    with Session(engine, expire_on_commit=False) as session:
        stmt = (
            select(Document)
            .options(selectinload(Document.chunks))
            .where(Document.url == url)
        )
        
        return session.scalars(stmt).first()

def get_document_by_id(id: int) -> Document | None:
    with Session(engine, expire_on_commit=False) as session:
        stmt = (
            select(Document)
            .options(selectinload(Document.chunks))
            .where(Document.id == id)
        )
        
        return session.scalars(stmt).first()

def search_documents(query_vector: list) -> list[DocumentChunk]:

    # For Cosine Distance: 0.0 is identical, 1.0 is orthogonal (unrelated), 2.0 is opposite.
    # A common strict threshold is 0.3 to 0.4.
    DISTANCE_THRESHOLD = 0.4

    with Session(engine) as session:
        # Use cosine_distance (Cosine Similarity)
        # We order by distance (ascending) and limit to top 5 results
        query_results = session.scalars(select(DocumentChunk)
            .where(DocumentChunk.content_vector.cosine_distance(query_vector) < DISTANCE_THRESHOLD)
            .order_by(DocumentChunk.content_vector.cosine_distance(query_vector))
            .limit(6)).all()
        
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

def get_documents(offset, page_size):
    """
    This function retrieves documents from the database based on the provided offset and page size.
     
    Args:
        offset (int): The number of documents to skip.
        page_size (int): The number of documents to include in each page.
    Returns:
        list[Document]: A list of documents along with their chunks.
    """
    with Session(engine) as session:
        stmt = (
            select(Document)
            .options(selectinload(Document.chunks))
            .order_by(Document.id) # Consistency is key for pagination
            .limit(page_size)
            .offset(offset)
        )
        
        return session.scalars(stmt).all()
    
def get_documents_count():
    """Returns the total count of documents in the database."""
    with Session(engine) as session:
        count = session.execute(select(func.count()).select_from(Document)).scalar()
        return count

def delete_document(document_id: int) -> bool:
    """Delete a document and its chunks by ID. Returns True if found and deleted."""
    with Session(engine) as session:
        doc = session.get(Document, document_id)
        if doc is None:
            return False
        session.delete(doc)
        session.commit()
        return True
