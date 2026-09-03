from fastembed import TextEmbedding

from sqlalchemy import select
from sqlalchemy.orm import Session

from dbmodel import DocumentChunk
import dbconnect

model = TextEmbedding() # using BAAI/bge-small-en-v1.5

def search(query: str, document_id: int = None) -> dict:
    """
    Search for relevant document chunks based on a query.

    This function takes a search query, computes its embedding using the global
    ``model``, and then performs a similarity search against the document chunks
    stored in the database. The search results are returned as a dictionary
    containing the most relevant chunks along with their metadata.

    Args:
        query (str): The search query string.

    Returns:
        dict: A dictionary containing the search results, which includes the
        relevant document chunks and their associated metadata.

    Raises:
        Exception: Propagates any exceptions that occur during embedding or database
            operations so callers can handle or log them as needed.
    """
    query_embedding = list(model.embed(query))[0]
    results = dbconnect.search_documents(query_embedding, document_id)
    
    return results