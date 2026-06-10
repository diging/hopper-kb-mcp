from unstructured.partition.pdf import partition_pdf

import os
import time

import documents

def add_pdf(file: bytes, filename: str, title: str, url: str = None, metadata: dict | None = None):

    file_path = _save_file(file, filename)

    elements = partition_pdf(filename=f"{file_path}")

    existing_doc = documents.get_document_by_title_and_type(
        title, documents.DocumentTypes.PDF.value
    )
    if existing_doc:
        existing_doc.local_path = file_path
        return documents.update_document(
            existing_doc, elements, title, documents.DocumentTypes.PDF.value, url, metadata=metadata,
        )

    return documents.add_document(
        elements, title, documents.DocumentTypes.PDF.value, url, metadata=metadata, local_path=file_path,
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
