import documents
from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import JWTVerifier

import os
import searchdocs

mcp_server = FastMCP("Hopper KB", 
        auth = JWTVerifier(
            jwks_uri=os.environ.get("JWKS_ENDPOINT", ""),
            issuer=os.environ.get("ISSUER_URL", "http://localhost:8000"),
            algorithm=os.environ.get("JWT_ALGORITHM", "RS256")
        )
    )

@mcp_server.tool()
def search(query: str) -> dict:
    """Find relevant documents"""
    search_results = searchdocs.search(query)

    print(f"Found {len(search_results)} relevant chunks for query: '{query}'")  # Debugging output
        
    return {
        "results": search_results
    }

@mcp_server.tool()
def datetime() -> str:
    """Get the current date and time."""
    from datetime import datetime
    return datetime.now().isoformat()

@mcp_server.tool()
def get_document_chunks(id: int) -> dict:
    """Get the chunks of a document."""
    doc = documents.get_document_by_id(int(id))
    if not doc:
        raise ValueError("Document not found")
    
    doc_json = { 
        "id": doc.id,
        "title": doc.title,
        "url": doc.url,
        "doc_type": doc.doc_type,
        "created_at": doc.created_at.isoformat() if doc.created_at else "",
        "modified_at": doc.modified_at.isoformat() if doc.modified_at else "",
        "metadata": doc.metadata_json,
        "chunks": [
            {
                "order_index": c.order_index,
                "content": c.content,
                "metadata": c.metadata_json
            }
            for c in doc.chunks 
        ] if doc.chunks else []
    }
    return doc_json


@mcp_server.resource("hopper://documents/{id}")
def get_document(id: str) -> str:
    """Get a document"""
    if id == "DOC1":
        with open('documents/DOC1.html', 'r') as file:
            content = file.read()
    else:
        with open('documents/DOC2.html', 'r') as file:
            content = file.read()
    return content