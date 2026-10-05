# Endpoints

This application exposes a small document ingestion API under the `/docs` mount and an MCP server under the `/mcp` mount. For architecture, workflows and configuration, see [DOCUMENTATION.md](DOCUMENTATION.md).

Base URL in local development: `http://localhost:8002`, set by `WEB_PORT` in `.env`.

## Authentication

Every endpoint on both mounts requires a JWT issued by Hopper's OpenID Connect provider:

```
Authorization: Bearer <jwt>
```

- `/docs/*`: a missing or invalid token returns `403 {"error": "Forbidden"}`.
- `/mcp`: a missing or invalid token returns FastMCP's standard `401` response.

See [DOCUMENTATION.md → Authentication](DOCUMENTATION.md#authentication) for how to obtain a token.

## Document API (/docs)

All routes under /docs are protected with an API key requirement: the JWT bearer token described above.

Documents returned by the add and update endpoints share this shape:

```json
{
  "doc_id": 12,
  "title": "Hand Hygiene Guidelines",
  "type": "pdf",
  "created_at": "2026-06-16T18:22:05.123456+00:00",
  "modified_at": "2026-06-16T18:22:05.123456+00:00",
  "url": null,
  "metadata": {"publisher": "State", "date_published": "2023-09", "...": "..."}
}
```

Errors are returned as `{"error": "<message>"}` with a 4xx or 5xx status.

### GET /docs/list — Return a paginated list of stored documents.
- Required parameters: none.
- Optional query parameters:
  - `page`: 1-based, default `1`
  - `page_size`: default `10`
  - `return_chunks`: `true` or `false`, default `true`. When `false`, each document's `chunks` is an empty list.
- Documents are ordered by id. Invalid `page` or `page_size` values fall back to their defaults.
- Response:

  ```json
  {
    "total": 42,
    "page": 1,
    "page_size": 10,
    "documents": [
      {
        "id": 12,
        "title": "Hand Hygiene Guidelines",
        "url": null,
        "doc_type": "pdf",
        "created_at": "...",
        "modified_at": "...",
        "metadata": {"...": "..."},
        "chunks": [
          {"order_index": 0, "content": "...", "metadata": {"source": null, "type": "CompositeElement", "page_number": 1}}
        ]
      }
    ]
  }
  ```

### POST /docs/website/add — Ingest a website by URL into the knowledge base.
- Required parameters: `url` (query parameter).
- Optional body field: `metadata`, sent as a JSON body `{"metadata": {...}}`. An empty body is allowed.
- The server fetches the URL (without following redirects), extracts the `<title>`, chunks and embeds the content. **If a document with the same URL already exists, it's updated in place** (same `doc_id`, chunks replaced) instead of duplicated.
- Responses: `200` with the document; `400` for an invalid JSON body; `500` if the site returned a non-200 status (`"Website could not be accessed. Returned status: <code>"`) or processing failed.
- Example:

  ```bash
  curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
       -d '{"metadata": {"publisher": "CDC"}}' \
       "http://localhost:8002/docs/website/add?url=https://www.cdc.gov/handwashing/"
  ```

### POST /docs/pdf/add — Upload and ingest a PDF document.
- Required parameters: `file`, `title` (multipart/form-data).
- Optional form fields: `url`; `metadata` as a JSON-encoded string.
- The file is stored as `$DATA_DIR/pdfs/<timestamp>-<filename>` and partitioned page by page, so chunk metadata includes `page_number`. **Every call creates a new document**; PDFs aren't de-duplicated.
- Responses: `200` with the document; `400` if `file`/`title` is missing or `metadata` isn't valid JSON; `500` on processing errors.
- Example:

  ```bash
  curl -X POST -H "Authorization: Bearer $TOKEN" \
       -F file=@guideline.pdf -F title="Hand Hygiene Guidelines" \
       -F metadata='{"publisher": "State", "date_published": "2023"}' \
       http://localhost:8002/docs/pdf/add
  ```

### POST /docs/pdf/update — Replace an existing PDF document by document ID.
- Required parameters: `doc_id`, `file`, `title` (multipart/form-data).
- Optional form fields: `url`, `metadata`. Existing metadata is kept if `metadata` is omitted.
- Re-partitions the new file and replaces all chunks while keeping the same `doc_id`.
- Responses: `200` with the document; `400` for missing fields, a non-integer `doc_id` or invalid `metadata`; `404` `"Document not found."`; `500` on processing errors.

### POST /docs/html/add — Upload and ingest an HTML document.
- Required parameters: `file`, `url` (multipart/form-data).
- Optional form field: `metadata`.
- Use this for pages the server can't fetch itself. The HTML is processed like a website, and the `url` is the de-duplication key: an existing document with the same URL is updated in place.
- Responses: `200` with the document; `400` for missing fields or invalid `metadata`; `500` on processing errors.

### GET /docs/{doc_id}/file — Download the original PDF file for a document.
- Required parameters: `doc_id` (path parameter).
- Response: `200` with the PDF (`application/pdf`, with the stored file name in `Content-Disposition`).
- Errors: `400` for a non-integer id; `404 {"error": "Document not found."}`; `404 {"error": "file_unavailable"}` when the document isn't a PDF or has no stored file.

### DELETE /docs/{doc_id} — Delete a document and its associated chunks.
- Required parameters: `doc_id` (path parameter).
- Also removes the stored PDF file from disk, if there is one.
- Response: `200 {"success": true, "doc_id": 12}`.
- Errors: `400` for a non-integer id; `404 {"error": "Document not found."}`. A 404 is also returned if the row was deleted but the file couldn't be removed.

## MCP API (/mcp)

```
Authorization: Bearer <jwt>
Content-Type: application/json
Accept: application/json, text/event-stream
```

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

- /mcp — Mount point for the FastMCP streamable HTTP interface. Initialize sessions via this endpoint to get an MCP session id.
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

### Tool: `search(query: str)`

Semantic search across all documents. The query is embedded and compared with every chunk by cosine distance. Only chunks with a distance **below 0.4** are returned, closest first, up to `NUM_OF_DB_SEARCH_RESULTS` (default 20). An empty `results` list means nothing was relevant enough.

Request:

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {"name": "search", "arguments": {"query": "hand hygiene compliance"}}
}
```

The tool returns (in the MCP result's structured content, and as JSON text in `content[0].text`):

```json
{
  "results": [
    {
      "title": "Hand Hygiene Guidelines",
      "url": null,
      "chunk": "Hand hygiene compliance should be monitored ...",
      "id": "12-3",
      "document_id": 12,
      "order_index": 3,
      "metadata": {"source": null, "type": "CompositeElement", "page_number": 4}
    }
  ]
}
```

- `id` is the chunk id (`<document_id>-<order_index>`). `document_id` is the id Hopper uses to match results to its own resources.
- `url` is the source URL for websites. It's usually `null` for PDFs uploaded by Hopper.
- `metadata.page_number` is the PDF page the chunk came from. It's always `1` for websites.

### Tool: `get_document_chunks(id: int, query: str)`

Same search as `search`, restricted to one document (`document_id = id`). Returns the same `{"results": [...]}` shape. Use it to find the most relevant passages and page numbers within a document that's already known to be relevant.

### Resource: `hopper://documents/{id}`

Proof-of-concept resource: returns the static HTML in `documents/DOC1.html` when `id` is `DOC1`, and `documents/DOC2.html` for any other id. It isn't connected to the knowledge base database.
