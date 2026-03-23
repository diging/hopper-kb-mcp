from fastmcp import FastMCP

import searchdocs

mcp_server = FastMCP("MCP")

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