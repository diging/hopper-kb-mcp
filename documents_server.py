from fastmcp import FastMCP

from decorators import require_api_key
import documents
import pdf_docs
import website_docs

from starlette.requests import Request
from starlette.responses import JSONResponse

import httpx
import json

documents_server = FastMCP("Documents Server")

@documents_server.custom_route("/list", methods=["GET"])
@require_api_key
async def get_documents(request: Request):
    """Return a paginated list of documents from the database.

    Query parameters accepted:
    - ``page``: 1-based page number (defaults to ``1``).
    - ``page_size``: Number of documents per page (defaults to ``10``).

    The function parses those parameters, calls ``documents.get_documents`` to
    fetch the results, and returns them wrapped in a JSON response. The route
    is protected by ``require_api_key``.

    Args:
        request (starlette.requests.Request): Incoming HTTP request.

    Returns:
        starlette.responses.JSONResponse: A JSON object containing the total count
        of documents, current page, page size, and a list of documents with their
        metadata and chunks.

    Raises:
        ValueError: If ``page`` or ``page_size`` cannot be parsed as integers.
    """
    try:
        page = int(request.query_params.get("page", 1))
    except ValueError:
        print("Invalid page parameter: {page}")  # Debugging output
        page = 1  # Default to page 1 if parsing fails

    try:
        page_size = int(request.query_params.get("page_size", 10))
    except ValueError:
        print("Invalid page_size parameter: {page_size}")  # Debugging output
        page_size = 10  # Default to 10 if parsing fails

    try:
        return_chunks = request.query_params.get("return_chunks", "true").lower() == "true"
    except Exception as e:
        print(f"Error parsing return_chunks parameter: {e}")
        return_chunks = True  # Default to True if parsing fails    

    count, results = documents.get_documents(page, page_size, return_chunks)

    return JSONResponse({"total": count, "page": page, "page_size": page_size, "documents": results})

@documents_server.custom_route("/website/add", methods=["POST"])
@require_api_key
async def add_website(request: Request):
    """HTTP endpoint to add a website into the ingestion pipeline.

    Reads the ``url`` query parameter from the incoming request, delegates the
    actual fetch/partition/embed/store work to ``documents.add_website``, and
    returns a JSON response indicating success or failure.

    The route is protected by ``require_api_key`` so callers must present a
    valid bearer token.

    Args:
        request (starlette.requests.Request): Incoming HTTP request. The URL to
            process should be provided as the ``url`` query parameter.

    Returns:
        starlette.responses.JSONResponse: Success message (HTTP 200) or an
        error JSON with an appropriate HTTP status code.
    """
    url = request.query_params.get("url")
    metadata = None
    if request.headers.get("content-type", "").startswith("application/json"):
        try:
            body = await request.json()
            if isinstance(body, dict):
                metadata = body.get("metadata")
        except json.JSONDecodeError:
            metadata = None
    try:
        website = website_docs.add_website(url, metadata=metadata)
        return JSONResponse(await _create_document_json(website))
    except httpx.HTTPError as e:
        print(e)
        return JSONResponse({"error": f"Website could not be accessed. Returned status: {e.response.status_code}"}, status_code=500)
    except Exception as e:
        print(e)
        return JSONResponse({"error": "An error occurred while processing the website."}, status_code=500)

@documents_server.custom_route("/pdf/add", methods=["POST"])
@require_api_key
async def add_pdf(request: Request):
    """HTTP endpoint to upload a PDF and add it to the ingestion pipeline.

    Expects a multipart/form-data POST with two fields:
    - ``file``: the uploaded PDF file
    - ``title``: the title to associate with the PDF

    The handler reads the uploaded file bytes and calls ``pdf_docs.add_pdf``
    to perform the actual PDF processing and storage.
    """
    form = await request.form()
    upload = form.get("file")
    title = form.get("title")
    url = form.get("url")
    metadata_raw = form.get("metadata")
    metadata = None
    if metadata_raw:
        try:
            metadata = json.loads(metadata_raw)
        except json.JSONDecodeError:
            return JSONResponse({"error": "'metadata' must be valid JSON."}, status_code=400)

    if upload is None or title is None:
        return JSONResponse({"error": "Missing 'file' or 'title' in form data."}, status_code=400)

    try:
        # Upload is a Starlette UploadFile; read bytes and pass to pdf_docs
        file_bytes = await upload.read()
        pdf = pdf_docs.add_pdf(file_bytes, upload.filename, title, url, metadata=metadata)
        return JSONResponse(await _create_document_json(pdf))
    except Exception as e:
        print(e)
        return JSONResponse({"error": "An error occurred while processing the PDF."}, status_code=500)
    
@documents_server.custom_route("/html/add", methods=["POST"])
@require_api_key
async def add_html(request: Request):
    """HTTP endpoint to upload a PDF and add it to the ingestion pipeline.

    Expects a multipart/form-data POST with two fields:
    - ``file``: the uploaded PDF file
    - ``title``: the title to associate with the PDF

    The handler reads the uploaded file bytes and calls ``pdf_docs.add_pdf``
    to perform the actual PDF processing and storage.
    """
    form = await request.form()
    upload = form.get("file")
    url = form.get("url")

    if upload is None or url is None:
        return JSONResponse({"error": "Missing 'file' or 'url' in form data."}, status_code=400)

    try:
        # Upload is a Starlette UploadFile; read bytes and pass to pdf_docs
        file_bytes = await upload.read()   
        doc = website_docs.add_html(file_bytes, url)
        return JSONResponse(await _create_document_json(doc))
    except Exception as e:
        print(e)
        return JSONResponse({"error": "An error occurred while processing the PDF."}, status_code=500)
    

@documents_server.custom_route("/{doc_id}", methods=["DELETE"])
@require_api_key
async def delete_document(request: Request):
    """Delete a document and all its chunks by ID.

    Expects a ``doc_id`` path parameter with the integer document ID.
    Returns a success message or 404 if the document does not exist.
    """
    try:
        doc_id = int(request.path_params.get("doc_id"))
    except ValueError:
        return JSONResponse({"error": "'doc_id' must be an integer."}, status_code=400)
    
    deleted = documents.delete_document(doc_id)
    if not deleted:
        return JSONResponse({"error": "Document not found."}, status_code=404)

    return JSONResponse({"success": True, "doc_id": doc_id})


async def _create_document_json(document):
    """Helper to convert a Document SQLAlchemy object into a JSON-serializable dict."""
    return {
        "doc_id": document.id,
        "title": document.title,
        "type": document.doc_type,
        "created_at": document.created_at.isoformat() if document.created_at else "",
        "modified_at": document.modified_at.isoformat() if document.modified_at else "",
        "url": document.url,
        "metadata": document.metadata_json,
    }