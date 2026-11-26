"""Embed the corpus chunks and store them in one Chroma collection per team."""

from collections import defaultdict
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

from app.core.config import settings
from app.ingestion.loaders import REPO_ROOT, load_corpus
from app.ingestion.splitter import split_documents

# Manifest `collection` value -> Chroma collection name.
COLLECTIONS = {
    "shared": "shared",
    "dev": "team_dev",
    "sales": "team_sales",
    "social": "team_social",
}


def chroma_path() -> str:
    """Chroma folder, resolved from the project root so it doesn't depend on where you run from."""
    path = Path(settings.chroma_dir)
    return str(path if path.is_absolute() else REPO_ROOT / path)


def get_embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(model=settings.embedding_model, api_key=settings.openai_api_key)


def get_vector_store(collection_name: str, embeddings: OpenAIEmbeddings | None = None) -> Chroma:
    """Open (or create) one persistent Chroma collection."""
    return Chroma(
        collection_name=collection_name,
        embedding_function=embeddings or get_embeddings(),
        persist_directory=chroma_path(),
    )


def group_by_collection(chunks: list[Document]) -> dict[str, list[Document]]:
    groups: dict[str, list[Document]] = defaultdict(list)
    for chunk in chunks:
        key = chunk.metadata["collection"]
        if key not in COLLECTIONS:
            raise ValueError(f"Unknown collection '{key}' in {chunk.metadata['source']}")
        groups[COLLECTIONS[key]].append(chunk)
    return groups


def index_corpus(reset: bool = False) -> dict[str, int]:
    """Load, split, embed and store the whole corpus. Returns chunk counts per collection.

    Chunks are written with their fixed IDs, so running this again overwrites them
    instead of adding duplicates. Use reset=True after removing or renaming files,
    so chunks that no longer exist are deleted too.
    """
    chunks = split_documents(list(load_corpus()))
    groups = group_by_collection(chunks)
    embeddings = get_embeddings()

    counts: dict[str, int] = {}
    for name in COLLECTIONS.values():
        documents = groups.get(name, [])
        if not documents:
            raise ValueError(f"No chunks found for collection '{name}'")

        store = get_vector_store(name, embeddings)
        if reset:
            store.reset_collection()
        store.add_documents(documents, ids=[doc.id for doc in documents])

        stored = len(store.get(include=[])["ids"])
        if stored != len(documents):
            print(f"Warning: '{name}' holds {stored} chunks but the corpus has {len(documents)}. "
                  "Run with --reset to remove old chunks.")
        counts[name] = stored

    return counts


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Index the TeamMind corpus into Chroma.")
    parser.add_argument("--reset", action="store_true", help="empty each collection before indexing")
    args = parser.parse_args()

    counts = index_corpus(reset=args.reset)
    print(f"Indexed into {chroma_path()}")
    for name, count in counts.items():
        print(f"  {name:<12} {count} chunks")
    print(f"  {'total':<12} {sum(counts.values())} chunks")
