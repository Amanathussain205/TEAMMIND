"""Split loaded sections into retrieval chunks with stable IDs."""

from collections import defaultdict

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
MIN_BODY_SIZE = 200
# Paragraphs first, then table rows / lines, then sentences, then words.
SEPARATORS = ["\n\n", "\n", ". ", " ", ""]


def _header(metadata: dict) -> str:
    return f"Document: {metadata['document_title']}\nSection: {metadata['section']}\n\n"


def split_documents(
    documents: list[Document],
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> list[Document]:
    """Split each section, repeat its header on every chunk and give every chunk a fixed ID.

    The ID is `<source>::s<section number>::c<chunk number>`, so re-indexing the same
    files produces the same IDs and overwrites chunks instead of duplicating them.
    """
    chunks: list[Document] = []
    section_counter: dict[str, int] = defaultdict(int)

    for document in documents:
        metadata = document.metadata
        header = _header(metadata)
        body = document.page_content.removeprefix(header)

        # The header is added back to every chunk, so the body gets what is left of the budget.
        body_size = max(chunk_size - len(header), MIN_BODY_SIZE)
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=body_size,
            chunk_overlap=min(chunk_overlap, body_size // 4),
            separators=SEPARATORS,
            keep_separator="end",
        )
        pieces = [piece.strip() for piece in splitter.split_text(body) if piece.strip()]

        source = metadata["source"]
        section_index = section_counter[source]
        section_counter[source] += 1

        for chunk_index, piece in enumerate(pieces):
            chunk_id = f"{source}::s{section_index:03d}::c{chunk_index:02d}"
            chunk_metadata = {
                **metadata,
                "section_index": section_index,
                "chunk_index": chunk_index,
                "chunk_count": len(pieces),
                "chunk_id": chunk_id,
            }
            chunks.append(Document(id=chunk_id, page_content=header + piece, metadata=chunk_metadata))

    return chunks


if __name__ == "__main__":
    import sys
    from collections import Counter
    from pathlib import Path

    # Lets `python splitter.py` work from inside app/ingestion as well as from the project root.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from app.ingestion.loaders import load_corpus

    sections = list(load_corpus())
    chunks = split_documents(sections)
    sizes = [len(c.page_content) for c in chunks]
    ids = [c.metadata["chunk_id"] for c in chunks]

    print(f"Sections: {len(sections)}  ->  Chunks: {len(chunks)}")
    print("Per collection:", dict(Counter(c.metadata["collection"] for c in chunks)))
    print("Confidential chunks:", sum(c.metadata["confidential"] for c in chunks))
    print(f"Chunk size (chars): min {min(sizes)}, max {max(sizes)}, avg {sum(sizes) // len(sizes)}")
    print("Sections split into more than one chunk:", sum(1 for c in chunks if c.metadata["chunk_index"] == 1))
    print("All chunk IDs unique:", len(ids) == len(set(ids)))

    multi = next((c for c in chunks if c.metadata["chunk_index"] == 1), None)
    if multi:
        print("\n--- Example: second chunk of a split section ---")
        print(multi.metadata["chunk_id"])
        print(multi.page_content)
