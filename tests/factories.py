"""Helpers that seed the test database directly."""

import dbconnect
from dbmodel import Document, DocumentChunk


def store_document(title="Doc", url=None, doc_type="website", chunks=(), metadata=None, local_path=None):
    """Persist a Document with chunks given as (content, vector) pairs."""
    document = Document(
        title=title, url=url, doc_type=doc_type, metadata_json=metadata, local_path=local_path,
    )
    for i, (content, vector) in enumerate(chunks):
        document.chunks.append(DocumentChunk(
            order_index=i, content=content, content_vector=vector,
            metadata_json={"source": url, "page_number": 1},
        ))
    dbconnect.add_document(document)
    return document
