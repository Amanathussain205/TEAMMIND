"""Load the approved DOCX corpus into section-level LangChain Documents."""

import csv
from collections.abc import Iterator
from pathlib import Path

import docx
from docx.document import Document as DocxDocument
from docx.table import Table
from docx.text.paragraph import Paragraph
from langchain_core.documents import Document

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = REPO_ROOT / "data" / "corpus" / "manifest.csv"
TEXT_FIELDS = ["collection", "chroma_collection", "access", "document_title", "document_date", "writer", "classification", "doc_status"]
BOOL_FIELDS = ["illustrative_data", "has_confidential_paragraphs", "whole_document_restricted"]


def read_manifest(manifest_path: Path | str = DEFAULT_MANIFEST) -> list[dict]:
    """Read metadata rows, normalizing manifest boolean fields."""
    with open(manifest_path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        for key in BOOL_FIELDS:
            row[key] = row[key].strip().lower() == "yes"
    return rows


def _table_lines(table: Table) -> list[str]:
    rows = [[" ".join(cell.text.split()) for cell in row.cells] for row in table.rows]
    if len(rows) < 2:
        return [" | ".join(row) for row in rows if any(row)]
    header, body = rows[0], rows[1:]
    if [v.lower() for v in header] == ["field", "value"]:
        return [f"{r[0]}: {r[1]}" for r in body if len(r) > 1 and r[0]]
    return ["; ".join(f"{h}: {v}" for h, v in zip(header, row) if v) for row in body if any(row)]


def _iter_blocks(doc: DocxDocument) -> Iterator[tuple[str, str]]:
    for element in doc.element.body.iterchildren():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag == "p":
            para = Paragraph(element, doc)
            value = para.text.strip()
            if value:
                yield ("heading" if para.style.name == "Heading 2" else "para", value)
        elif tag == "tbl":
            lines = _table_lines(Table(element, doc))
            if lines:
                yield "table", "\n".join(lines)


def _make_doc(texts: list[str], heading: str, row: dict, confidential: bool) -> Document:
    metadata = {"source": row["source_file"], **{k: row[k] for k in TEXT_FIELDS}, **{k: row[k] for k in BOOL_FIELDS}}
    metadata.update(section=heading, confidential=confidential or row["whole_document_restricted"])
    return Document(page_content=f"Document: {row['document_title']}\nSection: {heading}\n\n" + "\n".join(texts), metadata=metadata)


def load_docx(path: Path | str, manifest_row: dict) -> Iterator[Document]:
    """Yield one Document per Heading 2 section; fail if the file has none."""
    count = 0
    for document in _iter_sections(path, manifest_row):
        count += 1
        yield document
    if count == 0:
        raise ValueError(f"No 'Heading 2' sections found in {path}")


def _iter_sections(path: Path | str, manifest_row: dict) -> Iterator[Document]:
    doc = docx.Document(str(path))
    heading: str | None = None
    buffer: list[str] = []

    def flush():
        nonlocal buffer
        if heading is not None and buffer:
            yield _make_doc(buffer, heading, manifest_row, False)
        buffer = []

    for kind, text in _iter_blocks(doc):
        if kind == "heading":
            yield from flush()
            heading = text
        elif heading is not None and kind == "para" and text.upper().startswith("CONFIDENTIAL"):
            yield from flush()
            yield _make_doc([text], heading, manifest_row, True)
        elif heading is not None:
            buffer.append(text)
    yield from flush()


def load_corpus(manifest_path: Path | str = DEFAULT_MANIFEST, collections: set[str] | None = None) -> Iterator[Document]:
    """Yield only allowlisted manifest files (never eval/docs/tricks)."""
    for row in read_manifest(manifest_path):
        if collections is not None and row["collection"] not in collections:
            continue
        path = REPO_ROOT / row["source_file"]
        if not path.is_file():
            raise FileNotFoundError(f"Listed in manifest but missing: {row['source_file']}")
        yield from load_docx(path, row)

if __name__ == "__main__":
    from collections import Counter

    documents = list(load_corpus())
    print(f"Loaded {len(documents)} sections")
    print("Per collection:", dict(Counter(d.metadata["collection"] for d in documents)))
    print("Confidential:", sum(d.metadata["confidential"] for d in documents))
    print("\n--- First section ---")
    print(documents[0].metadata)
    print(documents[0].page_content)