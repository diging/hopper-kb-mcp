from fastmcp import FastMCP

from decorators import require_api_key
import documents

from starlette.requests import Request
from starlette.responses import JSONResponse

import httpx

documents_server = FastMCP("Documents Server")

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
    try:
        documents.add_website(url)
        return JSONResponse({"message": "Website added successfully."})
    except httpx.HTTPError as e:
        print(e)
        return JSONResponse({"error": "Website could not be accessed."}, status_code=500)
    except Exception as e:
        print(e)
        return JSONResponse({"error": "An error occurred while processing the website."}, status_code=500)

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

    count, results = documents.get_documents(page, page_size)

    return JSONResponse({"total": count, "page": page, "page_size": page_size, "documents": results})
