from unstructured.partition.md import partition_md
import httpx, re

import documents

def add_website(url: str, metadata: dict | None = None):
    """
    Fetch a website, create document chunks, embed them, and store the document.

    This function downloads the page at ``url``, extracts the HTML ``<title>`` as the
    document title, partitions the page content into markdown elements, groups and
    cleans those elements, then chunks them by title. For each meaningful chunk it
    computes a vector embedding via the global ``model`` and creates a
    ``DocumentChunk`` which is appended to a ``Document``. The resulting document is
    persisted using ``dbconnect.add_document``.

    Args:
        url (str): The full URL of the website page to index.

    Returns:
        None: The function has side effects (saves to the database) and does not
        return a value.

    Raises:
        httpx.HTTPError: If the HTTP request for ``url`` fails.
        Exception: Propagates errors from partitioning, embedding, or database
            operations so callers can handle or log them as needed.

    Notes:
        - Chunks shorter than about 20 characters are skipped.
        - Embeddings are created with ``model.embed`` and stored in
          ``DocumentChunk.content_vector``.
    """
    headers = {"User-Agent": "HopperKbBot/1.0.0"}
    response = httpx.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Fetched {url} with status code {response.status_code}")  
        response.raise_for_status()
        
    return _create_doc(response.content, url, metadata=metadata)

def add_html(byesfile: bytes, url: str, metadata: dict | None = None):
    return _create_doc(byesfile, url, metadata=metadata)

def _create_doc(content, url, metadata: dict | None = None):
    content_str = content.decode('utf-8')
    match = re.search(r'<title>(.*?)</title>', content_str, re.IGNORECASE | re.DOTALL)
    title = match.group(1).strip() if match else "No Title Found"

    elements = partition_md(text=content)
    existing_doc = documents.get_document_by_url(url)
    if existing_doc:
        return documents.update_document(
            existing_doc, elements, title, documents.DocumentTypes.WEBSITE.value, url, metadata=metadata,
        )

    return documents.add_document(
        elements, title, documents.DocumentTypes.WEBSITE.value, url, metadata=metadata,
    )