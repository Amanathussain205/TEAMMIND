"""Starter evaluation: run a balanced sample of the dev eval set through the RAG chain.

Run from the project root:   python -m eval.run_eval
Results are saved to:        eval/results/eval_<date>_<time>.json

Every check is plain code (no LLM judge), so grading costs nothing.
- in_scope:     the answer contains every key fact, and a correct source was retrieved
- out_of_scope: TeamMind says it doesn't know instead of guessing
- cross_team:   no canary (another team's protected fact) in the answer or the retrieved text
"""

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime

from app.core.config import settings
from app.ingestion.loaders import REPO_ROOT, load_corpus
from app.rag.chain import SCORE_THRESHOLD, TOP_K, answer_question
from app.retrieval.retriever import SHARED, TEAMS

EVAL_FILE = REPO_ROOT / "eval" / "datasets" / "dev" / "teammind_eval_v1.1.jsonl"
RESULTS_DIR = REPO_ROOT / "eval" / "results"
DASHES = str.maketrans({"–": "-", "—": "-", "−": "-", "’": "'", "‘": "'"})


def normalize(text: str) -> str:
    """Lowercase, unify dashes and quotes, collapse whitespace, drop markdown bold."""
    text = text.translate(DASHES).replace("**", "").lower()
    return re.sub(r"\s+", " ", text).strip()


def spread(items: list, n: int) -> list:
    """Pick n items spread evenly across the list, so the sample covers many documents."""
    if len(items) <= n:
        return items
    step = len(items) / n
    return [items[int(i * step)] for i in range(n)]


def category(row: dict) -> str:
    if row["target_collection"] not in (row["asker_team"], SHARED):
        return "cross_team"
    return row["type"]


def select_questions(rows: list[dict], in_scope: int, cross: int) -> list[dict]:
    selected = []
    for team in sorted(TEAMS):
        own = [r for r in rows if r["asker_team"] == team]
        selected += spread([r for r in own if category(r) == "in_scope"], in_scope)
        selected += [r for r in own if category(r) == "out_of_scope"]
        selected += spread([r for r in own if category(r) == "cross_team"], cross)
    return selected


def allowed_text() -> dict[str, str]:
    """Everything each team may legitimately see, used to tell canaries from allowed facts."""
    parts: dict[str, list[str]] = {team: [] for team in TEAMS}
    for doc in load_corpus():
        for team in TEAMS:
            if doc.metadata["collection"] in (team, SHARED):
                parts[team].append(normalize(doc.page_content))
    return {team: "\n".join(text) for team, text in parts.items()}


def score(row: dict, result, allowed: dict[str, str]) -> dict:
    answer = normalize(result.answer)
    sources = {s.source for s in result.sources}
    kind = category(row)
    record = {"category": kind, "answered": result.answered, "fallback_reason": result.fallback_reason}

    if kind == "in_scope":
        facts = [normalize(f) for f in row["key_facts"]]
        found = [f for f in facts if f in answer]
        record.update(
            key_fact_recall=round(len(found) / len(facts), 3) if facts else None,
            missing_facts=[f for f in facts if f not in found],
            correct=result.answered and len(found) == len(facts),
            retrieval_hit=bool(sources & set(row["acceptable_sources"])),
        )
    elif kind == "out_of_scope":
        record.update(correct=not result.answered)
    else:  # cross_team
        team_text = allowed[row["asker_team"]]
        # A canary is a forbidden fact this team can't see anywhere, so finding it means a leak.
        canaries = [f for f in row["forbidden_facts"] if normalize(f) not in team_text]
        leaked = [f for f in canaries if normalize(f) in answer]
        foreign = sorted({s.collection for s in result.sources} - {row["asker_team"], SHARED})
        record.update(canaries_checked=len(canaries), leaked=leaked, foreign_collections=foreign,
                      correct=not leaked and not foreign)
    return record


def summarize(records: list[dict]) -> dict:
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        groups[r["category"]].append(r)

    def rate(rows: list[dict], key: str) -> float | None:
        values = [r[key] for r in rows if r.get(key) is not None]
        return round(sum(values) / len(values), 3) if values else None

    inscope = groups["in_scope"]
    return {
        "questions": len(records),
        "in_scope": {"n": len(inscope), "correct": rate(inscope, "correct"),
                     "key_fact_recall": rate(inscope, "key_fact_recall"),
                     "retrieval_hit_rate": rate(inscope, "retrieval_hit")},
        "out_of_scope": {"n": len(groups["out_of_scope"]), "said_unknown": rate(groups["out_of_scope"], "correct")},
        "cross_team": {"n": len(groups["cross_team"]), "no_leak": rate(groups["cross_team"], "correct"),
                       "leaks": sum(1 for r in groups["cross_team"] if not r["correct"])},
        "by_team": {team: rate([r for r in records if r["asker_team"] == team], "correct") for team in sorted(TEAMS)},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the TeamMind starter evaluation.")
    parser.add_argument("--in-scope", type=int, default=6, help="in-scope questions per team")
    parser.add_argument("--cross", type=int, default=4, help="cross-team questions per team")
    args = parser.parse_args()

    with EVAL_FILE.open(encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    questions = select_questions(rows, args.in_scope, args.cross)
    allowed = allowed_text()

    print(f"Running {len(questions)} questions...")
    records = []
    for i, row in enumerate(questions, start=1):
        result = answer_question(row["question"], row["asker_team"])
        record = {
            "id": row["id"], "asker_team": row["asker_team"], "target": row["target_collection"],
            "type": row["type"], "question": row["question"], "gold_answer": row["gold_answer"],
            "answer": result.answer, "top_score": result.top_score,
            "sources": [s.model_dump() for s in result.sources],
            **score(row, result, allowed),
        }
        records.append(record)
        mark = "PASS" if record["correct"] else "FAIL"
        print(f"  [{i:>2}/{len(questions)}] {mark}  {row['id']}  {record['category']:<12} {row['asker_team']}")

    summary = summarize(records)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_file = RESULTS_DIR / f"eval_{datetime.now():%Y-%m-%d_%H%M}.json"
    out_file.write_text(json.dumps({
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "config": {"llm_model": settings.llm_model, "embedding_model": settings.embedding_model,
                   "top_k": TOP_K, "score_threshold": SCORE_THRESHOLD, "dataset": EVAL_FILE.name},
        "summary": summary,
        "results": records,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    def pct(value: float | None) -> str:
        return "-" if value is None else f"{value:.0%}"

    s = summary
    print("\n" + "=" * 60)
    print(f"In-scope      {s['in_scope']['n']:>3} q   correct {pct(s['in_scope']['correct'])}   "
          f"key facts {pct(s['in_scope']['key_fact_recall'])}   retrieval hit {pct(s['in_scope']['retrieval_hit_rate'])}")
    print(f"Out-of-scope  {s['out_of_scope']['n']:>3} q   said unknown {pct(s['out_of_scope']['said_unknown'])}")
    print(f"Cross-team    {s['cross_team']['n']:>3} q   no leak {pct(s['cross_team']['no_leak'])}   leaks {s['cross_team']['leaks']}")
    print("By team:      " + "   ".join(f"{t} {pct(v)}" for t, v in s["by_team"].items()))
    print(f"\nSaved: {out_file.relative_to(REPO_ROOT)}")

    failures = [r for r in records if not r["correct"]]
    if failures:
        print("\nFailures:")
        for r in failures:
            detail = r.get("missing_facts") or r.get("leaked") or r.get("foreign_collections") or r.get("fallback_reason") or ""
            print(f"  {r['id']} ({r['category']}): {r['question']}")
            print(f"     answer: {r['answer'][:160]}")
            print(f"     detail: {detail}")


if __name__ == "__main__":
    main()
