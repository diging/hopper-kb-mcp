from unstructured.partition.pdf import partition_pdf

import os
import time

import documents
import dbconnect
from dbmodel import Document


def get_pdf(title: str):
    document_list = documents.get_documents()[1]

    for doc in document_list:
        if doc['title'] == title and doc['doc_type'] == documents.DocumentTypes.PDF.value:
            return dbconnect.get_document_by_id(doc['id'])

    return None


def add_pdf(file: bytes, filename: str, title: str, url: str = None):

    file_path = _save_file(file, filename)

    elements = partition_pdf(filename=f"{file_path}")
    doc = get_pdf(title)

    if doc:
        return documents.update_document(doc, elements, title, documents.DocumentTypes.PDF.value, url)

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
