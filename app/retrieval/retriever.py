"""get_retriever(team_id): the single entry point to a team's Chroma collections.

A team searches its own collection plus `shared`, and nothing else. Superseded
documents are left out unless asked for. Every result carries its relevance score.
"""

from functools import lru_cache

from langchain_chroma import Chroma
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import ConfigDict

from app.ingestion.indexer import COLLECTIONS, get_embeddings, get_vector_store

TEAMS = {"dev", "sales", "social"}
SHARED = "shared"
NOT_SUPERSEDED = {"doc_status": {"$ne": "superseded"}}


@lru_cache
def _store(collection_name: str) -> Chroma:
    """Open each collection once and reuse it."""
    return get_vector_store(collection_name, _embeddings())


@lru_cache
def _embeddings():
    return get_embeddings()


class TeamRetriever(BaseRetriever):
    """Searches one team's collection plus `shared`, merged by relevance score."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    team_id: str
    k: int = 5
    include_superseded: bool = False

    @property
    def allowed_collections(self) -> set[str]:
        return {self.team_id, SHARED}

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> list[Document]:
        where = None if self.include_superseded else NOT_SUPERSEDED

        scored: list[tuple[Document, float]] = []
        for key in sorted(self.allowed_collections):
            scored += _store(COLLECTIONS[key]).similarity_search_with_relevance_scores(
                query, k=self.k, filter=where
            )

        scored.sort(key=lambda pair: pair[1], reverse=True)
        results = []
        for doc, score in scored[: self.k]:
            # Second line of defence: a chunk from another team must never come back.
            if doc.metadata.get("collection") not in self.allowed_collections:
                raise PermissionError(
                    f"Team '{self.team_id}' received a chunk from '{doc.metadata.get('collection')}'"
                )
            doc.metadata["score"] = round(score, 4)
            results.append(doc)
        return results


def get_retriever(team_id: str, k: int = 5, include_superseded: bool = False) -> TeamRetriever:
    """Return the retriever for one team. Raises ValueError for an unknown team."""
    if team_id not in TEAMS:
        raise ValueError(f"Unknown team '{team_id}'. Expected one of: {sorted(TEAMS)}")
    return TeamRetriever(team_id=team_id, k=k, include_superseded=include_superseded)


if __name__ == "__main__":
    # Same question to every team: only Sales should get the price list.
    question = "What is the monthly price of the ShelfSense Standard plan?"
    for team in sorted(TEAMS):
        print(f"\n=== {team}: {question}")
        for doc in get_retriever(team, k=3).invoke(question):
            m = doc.metadata
            print(f"  {m['score']:.3f}  [{m['collection']}] {m['document_title']} > {m['section']}")
