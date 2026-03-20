
import httpx, re
from markdownify import markdownify as md

from unstructured.partition.md import partition_md
from unstructured.cleaners.core import clean, group_broken_paragraphs
from unstructured.chunking.title import chunk_by_title

from dbmodel import Document, DocumentChunk, DocumentTypes
import dbconnect

from fastembed import TextEmbedding

model = TextEmbedding()

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
          ``DocumentChunk.concent_vector``.
    """
    response = httpx.get(url)
    match = re.search(r'<title>(.*?)</title>', response.text, re.IGNORECASE | re.DOTALL)
    title = match.group(1).strip() if match else "No Title Found"
    
    chunks = _calculate_chunks(response.content, url)
    
    document = Document(title=title, url=url, role=DocumentTypes.WEBSITE.value)
    
    for i, chunk in enumerate(chunks):
        embeddings = list(model.embed(chunk["text"]))
        chunk_record = DocumentChunk(order_index=i, content=chunk["text"], concent_vector=embeddings[0], metadata_json=chunk["metadata"])
        document.chunks.append(chunk_record)

    dbconnect.add_document(document)
    

def _calculate_chunks(content: str, url: str):
    """Partition raw page content into cleaned, titled chunks ready for embedding.

    This helper takes the raw page ``content`` (HTML or markdown) and the original
    ``url`` and performs the following steps:
    - Partition the content into markdown elements using ``partition_md``.
    - Group and chunk elements by title with ``chunk_by_title`` (configurable
      thresholds are used in the function).
    - Clean and group broken paragraphs, skipping chunks that are too short to be
      meaningful.
    - Return a list of payload dictionaries suitable for embedding and storage.

    Args:
        content (str|bytes): Page content to partition. ``partition_md`` accepts
            either a string or bytes; callers typically pass ``response.content``.
        url (str): The source URL — added to each chunk's metadata as ``source``.

    Returns:
        list[dict]: A list of chunk dictionaries with the shape::

            {
                "id": "file-<n>",
                "text": ["paragraph 1", "paragraph 2", ...],
                "metadata": {
                    "source": url,
                    "type": chunk.category,
                    "page_number": <int>,
                }
            }

    Raises:
        Exception: Propagates errors from partitioning, chunking, or cleaning
            operations to allow callers to handle failures.

    Notes:
        - Chunks with very short text (fewer than ~20 items/characters) are
          skipped to avoid indexing noise.
        - The function uses ``chunk_by_title`` with thresholds tuned for
          reasonably-sized chunks (max 2000 chars, new after 1500 chars).
    """
    elements = partition_md(text=content)
    processed_chunks = []

    chunks = chunk_by_title(
        elements, 
        max_characters=2000, 
        new_after_n_chars=1500,
        combine_text_under_n_chars=500  # Merges tiny snippets into the bigger chunk
    )

    for i, chunk in enumerate(chunks):
        # for some reason these do not get stripped out otherwise
        text_content = chunk.text.replace("\\r", " ").replace("\\t", " ").replace("\\n", " ")
        text_content = clean(text_content, extra_whitespace=True, dashes=True)
        text_content = list(group_broken_paragraphs(text_content))

        # Skip elements that are too short to be meaningful for search
        if len(text_content) < 20:
            continue
        
        # 3. Create the payload structure
        # Most vector DBs expect: 'id', 'vector' (added later), and 'metadata'
        chunk_json = {
            "id": f"file-{i}",
            "text": text_content,  # This is what you will send to your embedding model
            "metadata": {
                "source": url,
                "type": chunk.category,  # e.g., 'Title', 'NarrativeText', 'ListItem'
                "page_number": chunk.metadata.page_number if chunk.metadata.page_number else 1,
            }
        }
        
        processed_chunks.append(chunk_json)

    return processed_chunks