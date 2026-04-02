from unstructured.partition.pdf import partition_pdf

import os
import time

import documents
from dbmodel import Document


def get_pdf(title: str):

    document_list = documents.get_documents()[1]
    print(document_list)

    for doc in document_list:
        print(doc)
        if doc['title'] == title and doc['doc_type'] == documents.DocumentTypes.PDF.value:
            return Document(title=doc['title'], url=doc['url'], doc_type=documents.DocumentTypes.PDF.value, created_at=doc['created_at'], modified_at=doc['modified_at'], chunks=doc['chunks'])

    return None


def add_pdf(file: bytes, filename: str, title: str, url: str = None):

    file_path = _save_file(file, filename)

    elements = partition_pdf(filename=f"{file_path}")
    doc = get_pdf(title)

    if doc:
        print("updating")
        return documents.update_document(doc, elements, title, documents.DocumentTypes.PDF.value, url)

    print("adding")
    return documents.add_document(elements, title, documents.DocumentTypes.PDF.value, url)


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
