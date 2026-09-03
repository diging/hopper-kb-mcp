# Endpoints

This application exposes a small document ingestion API under the /docs mount and an MCP server under the /mcp mount.

## Document API (/docs)

All routes under /docs are protected with an API key requirement.

- GET /docs/list — Return a paginated list of stored documents.
  - Required parameters: none.
  - Optional query parameters: page, page_size, return_chunks.
- POST /docs/website/add — Ingest a website by URL into the knowledge base.
  - Required parameters: url (query parameter).
  - Optional body field: metadata.
- POST /docs/pdf/add — Upload and ingest a PDF document.
  - Required parameters: file, title (multipart/form-data).
  - Optional form fields: url, metadata.
- POST /docs/pdf/update — Replace an existing PDF document by document ID.
  - Required parameters: doc_id, file, title (multipart/form-data).
  - Optional form fields: url, metadata.
- POST /docs/html/add — Upload and ingest an HTML document.
  - Required parameters: file, url (multipart/form-data).
  - Optional form field: metadata.
- GET /docs/{doc_id}/file — Download the original PDF file for a document.
  - Required parameters: doc_id (path parameter).
- DELETE /docs/{doc_id} — Delete a document and its associated chunks.
  - Required parameters: doc_id (path parameter).

## MCP API (/mcp)

The MCP endpoints expect JSON of the following format:

```
{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "method to call",
    "params": {
        "name": "...",
        "arguments": {
            "arg name": "arg value"
        }
    }
  }
```

Available endpoints:

- /mcp — Mount point for the FastMCP streamable HTTP interface. Initialize sessions via this endpoint to retrieve a token.
  - Required parameters: none.
- MCP tool: search(query) — Search the indexed knowledge base for relevant document chunks.
  - Required parameters: query - search query string
  - Method: tools/call
- MCP tool: datetime() — Return the current date and time.
  - Required parameters: none.
  - Method: tools/call
- MCP tool: get_document_chunks(id, query) — Retrieve chunks for a specific document and query.
  - Required parameters: id - of document, query - to search for.
  - Method: tools/call
- MCP resource: hopper://documents/{id} — Return document content for the built-in example documents.
  - Required parameters: id.
