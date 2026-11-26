"""Phase 1 gate: no team can retrieve another team's chunks.

Questions come from the visible dev eval set (eval/datasets/dev). The file is only
read here as test input; it is never ingested.

Needs the Chroma index (python -m app.ingestion.indexer --reset) and an OpenAI key.
Run with: pytest
"""

import json

import pytest

from app.ingestion.indexer import COLLECTIONS, get_vector_store
from app.ingestion.loaders import REPO_ROOT, load_corpus
from app.retrieval.retriever import SHARED, TEAMS, get_retriever

EVAL_FILE = REPO_ROOT / "eval" / "datasets" / "dev" / "teammind_eval_v1.1.jsonl"
K = 10  # retrieve more than the app will use, to make leaks easier to catch


def _cross_team_questions() -> list[dict]:
    """Questions where a team asks about another team's data (not shared)."""
    with EVAL_FILE.open(encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    return [
        r for r in rows
        if r["asker_team"] in TEAMS and r["target_collection"] not in (r["asker_team"], SHARED)
    ]


CROSS_TEAM = _cross_team_questions()


def _allowed(team: str) -> set[str]:
    return {team, SHARED}


@pytest.fixture(scope="session", autouse=True)
def index_is_built():
    for name in COLLECTIONS.values():
        if not get_vector_store(name).get(limit=1)["ids"]:
            pytest.fail(f"Collection '{name}' is empty. Run: python -m app.ingestion.indexer --reset")


@pytest.fixture(scope="session")
def allowed_text() -> dict[str, str]:
    """All text each team may legitimately see (its own documents + shared), lowercased."""
    text = {team: [] for team in TEAMS}
    for doc in load_corpus():
        for team in TEAMS:
            if doc.metadata["collection"] in _allowed(team):
                text[team].append(doc.page_content.lower())
    return {team: "\n".join(parts) for team, parts in text.items()}


def test_eval_set_has_cross_team_questions():
    assert len(CROSS_TEAM) >= 40, f"Expected about 44 cross-team questions, found {len(CROSS_TEAM)}"


@pytest.mark.parametrize("row", CROSS_TEAM, ids=[r["id"] for r in CROSS_TEAM])
def test_cross_team_question_does_not_leak(row, allowed_text):
    team = row["asker_team"]
    docs = get_retriever(team, k=K).invoke(row["question"])
    assert docs, "Retriever returned nothing"

    # 1. Every chunk comes from the asking team's own collection or shared.
    foreign = {d.metadata["collection"] for d in docs} - _allowed(team)
    assert not foreign, f"{team} received chunks from {foreign}"

    # 2. No canary appears in the retrieved text. A canary is a forbidden fact that
    #    exists nowhere in this team's allowed documents, so seeing it means a leak.
    canaries = [f for f in row["forbidden_facts"] if f.lower() not in allowed_text[team]]
    context = "\n".join(d.page_content.lower() for d in docs)
    leaked = [f for f in canaries if f.lower() in context]
    assert not leaked, f"{team} retrieved forbidden facts: {leaked}"


@pytest.mark.parametrize("team", sorted(TEAMS))
@pytest.mark.parametrize("query", [
    "confidential",
    "salary and compensation",
    "discount and price list",
    "security incident register",
    "paid campaign budget",
])
def test_broad_queries_stay_inside_team(team, query):
    docs = get_retriever(team, k=20).invoke(query)
    foreign = {d.metadata["collection"] for d in docs} - _allowed(team)
    assert not foreign, f"{team} received chunks from {foreign} for '{query}'"


def test_superseded_hidden_by_default():
    docs = get_retriever("sales", k=20).invoke("ShelfSense Price List 2025")
    assert all(d.metadata["doc_status"] != "superseded" for d in docs)


def test_superseded_available_when_asked():
    docs = get_retriever("sales", k=20, include_superseded=True).invoke("ShelfSense Price List 2025")
    assert any(d.metadata["doc_status"] == "superseded" for d in docs)


@pytest.mark.parametrize("bad_team", ["shared", "admin", "", "Dev", "team_dev"])
def test_unknown_team_is_rejected(bad_team):
    with pytest.raises(ValueError):
        get_retriever(bad_team)
