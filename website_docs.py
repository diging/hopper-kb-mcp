from unstructured.partition.md import partition_md
import httpx, re

import documents

def add_website(url: str):
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
    match = re.search(r'<title>(.*?)</title>', response.text, re.IGNORECASE | re.DOTALL)
    title = match.group(1).strip() if match else "No Title Found"
    
    elements = partition_md(text=response.content)
    existing_doc = documents.get_document_by_url(url)
    if existing_doc:
        return documents.update_document(existing_doc, elements, title, documents.DocumentTypes.WEBSITE.value, url)
    
    return documents.add_document(elements, title, documents.DocumentTypes.WEBSITE.value, url)
    

