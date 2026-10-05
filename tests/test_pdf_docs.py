import os
from unittest.mock import patch

from unstructured.documents.elements import NarrativeText

import dbconnect
import pdf_docs

FIRST = [NarrativeText("The annual report lists staffed beds for every rural hospital.")]
SECOND = [NarrativeText("The revised report adds neonatal intensive care capacity figures.")]


def test_save_file_writes_into_data_dir(data_dir):
    path = pdf_docs._save_file(b"%PDF-1.4 bytes", "report.pdf")

    assert os.path.dirname(path) == str(data_dir / "pdfs")
    assert os.path.basename(path).endswith("-report.pdf")
    with open(path, "rb") as f:
        assert f.read() == b"%PDF-1.4 bytes"


def test_save_file_works_when_folders_already_exist(data_dir):
    (data_dir / "pdfs").mkdir(parents=True)
    first = pdf_docs._save_file(b"a", "a.pdf")
    second = pdf_docs._save_file(b"b", "b.pdf")
    assert os.path.exists(first) and os.path.exists(second)


@patch("pdf_docs.partition_pdf", return_value=FIRST)
def test_add_pdf_saves_file_and_stores_document(mock_partition, data_dir):
    doc = pdf_docs.add_pdf(
        b"%PDF bytes", "report.pdf", "Annual report",
        url="https://example.com/report.pdf", metadata={"year": 2024},
    )

    stored = dbconnect.get_document_by_id(doc.id)
    assert (stored.title, stored.doc_type) == ("Annual report", "pdf")
    assert stored.url == "https://example.com/report.pdf"
    assert stored.metadata_json == {"year": 2024}
    assert stored.local_path.startswith(str(data_dir / "pdfs"))
    mock_partition.assert_called_once_with(filename=stored.local_path)
    assert [c.content for c in stored.chunks] == [FIRST[0].text]


@patch("pdf_docs.partition_pdf", return_value=SECOND)
def test_update_unknown_pdf_returns_none_without_saving(mock_partition, data_dir):
    assert pdf_docs.update_pdf(999, b"%PDF", "x.pdf", "x") is None
    mock_partition.assert_not_called()
    assert not (data_dir / "pdfs").exists()


@patch("pdf_docs.partition_pdf")
def test_update_pdf_replaces_chunks_and_file_in_place(mock_partition):
    mock_partition.return_value = FIRST
    original = pdf_docs.add_pdf(b"%PDF v1", "report.pdf", "Annual report")

    mock_partition.return_value = SECOND
    updated = pdf_docs.update_pdf(original.id, b"%PDF v2", "report-v2.pdf", "Revised report")

    assert updated.id == original.id
    stored = dbconnect.get_document_by_id(original.id)
    assert stored.title == "Revised report"
    assert [c.content for c in stored.chunks] == [SECOND[0].text]
    assert stored.local_path != original.local_path
    assert stored.local_path.endswith("-report-v2.pdf")
    with open(stored.local_path, "rb") as f:
        assert f.read() == b"%PDF v2"
    assert dbconnect.get_documents_count() == 1
