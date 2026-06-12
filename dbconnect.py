import os
from sqlalchemy import create_engine, text, select, func
from sqlalchemy.orm import Session, selectinload

from dbmodel import Base, Document, DocumentChunk

POSTGRES_USER = os.environ["POSTGRES_USER"]
POSTGRES_PASSWORD = os.environ["POSTGRES_PASSWORD"]
POSTGRES_HOST = os.environ["POSTGRES_HOST"]
POSTGRES_PORT = os.environ["POSTGRES_PORT"]
POSTGRES_DB = os.environ["POSTGRES_DB"]
DB_URL = f"postgresql+psycopg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
engine = create_engine(DB_URL)

NUM_OF_SEARCH_RESULTS = int(os.environ.get("NUM_OF_DB_SEARCH_RESULTS", 20))

with engine.connect() as conn:
    # Enable the extension
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    conn.commit()

Base.metadata.create_all(engine)

# apply column additions idempotently
with engine.connect() as conn:
    conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS metadata_json JSONB"))
    conn.commit()

def add_document(document: Document):
    with Session(engine, expire_on_commit=False) as session:
        session.add(document)
        session.commit()

def update_document(document: Document):
    with Session(engine, expire_on_commit=False) as session:
        # Re-ingesting a document must REPLACE chunks.
        #  Delete all existing chunks for this document first, 
        # then merge the parent (which inserts the new ones)
        session.query(DocumentChunk).filter(
            DocumentChunk.document_id == document.id
        ).delete(synchronize_session=False)
        merged = session.merge(document)
        session.commit()
        return merged

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
            .limit(NUM_OF_SEARCH_RESULTS)).all()
        
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
    """Delete a document and its chunks by ID. Returns True if found and deleted.

    Also removes the original file from disk when local_path is set. A
    failed file removal does not roll back the DB delete — the row is
    gone either way; we just log so the disk leak is recoverable.
    """
    with Session(engine) as session:
        doc = session.get(Document, document_id)
        if doc is None:
            return False
        local_path = doc.local_path
        session.delete(doc)
        session.commit()

    if local_path and os.path.exists(local_path):
        try:
            os.remove(local_path)
        except OSError as e:
            print(f"Failed to remove file {local_path} for doc {document_id}: {e}")
            return False

    return True
