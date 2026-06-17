from unstructured.partition.pdf import partition_pdf

import os
import time

import documents

def add_pdf(file: bytes, filename: str, title: str, url: str = None, metadata: dict | None = None):

    file_path = _save_file(file, filename)

    elements = partition_pdf(filename=f"{file_path}")

    return documents.add_document(
        elements, title, documents.DocumentTypes.PDF.value, url, metadata=metadata, local_path=file_path,
    )


def update_pdf(doc_id: int, file: bytes, filename: str, title: str, url: str = None, metadata: dict | None = None):
    """Update an existing PDF document by id: re-partition the new file and
    replace its chunks in place. Returns None if no document has that id."""

    existing_doc = documents.get_document_by_id(doc_id)
    if existing_doc is None:
        return None

    file_path = _save_file(file, filename)

    elements = partition_pdf(filename=f"{file_path}")

    existing_doc.local_path = file_path
    return documents.update_document(
        existing_doc, elements, title, documents.DocumentTypes.PDF.value, url, metadata=metadata,
    )


def _save_file(file: bytes, filename: str) -> str:
    """Helper to save an uploaded file to disk and return the file path."""

    # for whatever reason, makedirs refused to create the subfolder,
    # so two steps it is.
    data_path = f"{os.environ.get("DATA_DIR", "./data")}"
    try:
        os.mkdir(data_path)
    except Exception as e:
        print("data folder exists, skipping creation.")

    pdf_path = os.path.join(data_path, "pdfs")
    try:
        os.mkdir(pdf_path)
    except Exception as e:
        print("pdfs folder exists, skipping creation.")

    file_path = f"{pdf_path}/{time.time()}-{filename}"
    with open(file_path, "wb") as f:
        f.write(file)

    return file_path
