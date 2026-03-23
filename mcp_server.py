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