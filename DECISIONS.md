# Design decisions

One line per decision: date, decision, reason. This log becomes the methodology chapter.

| Date | Decision | Reason |
|---|---|---|
| 2026-11-17 | Python 3.12 with venv + pip; exact versions pinned in requirements.txt | ChromaDB breaks on Python 3.14; pip matches the course, pinning keeps installs reproducible |
| 2026-11-17 | One LangGraph graph configured by `team_id`, not three separate agents | One design to build, test and evaluate |
| 2026-11-17 | Team isolation enforced in code: `team_id` from the JWT, `get_retriever(team_id)` is the only path to a collection | Prompt-only isolation leaks; code isolation is testable |
| 2026-11-17 | One persistent Chroma collection per team (`team_dev`, `team_sales`, `team_social`) | Physical separation of team data |
| 2026-11-17 | Chunking: RecursiveCharacterTextSplitter, 800 chars / 150 overlap (to be tuned) | Common starting point for short office documents |
| 2026-11-17 | Cheap LLM (gpt-4o-mini) + text-embedding-3-small, via `init_chat_model` | Low cost; provider can be swapped |
| 2026-11-17 | Phase 1 loads PDF and TXT only; DOCX and MD in Phase 2 | Keep Phase 1 small enough to finish by Nov 30 |
| 2026-11-17 | Phase 1 login uses hard-coded demo users | Auth is not the research contribution; real users later if time allows |
| 2026-11-17 | Chat memory only through the LangGraph SQLite checkpointer (Phase 3), no separate chat-history table | Avoid building memory twice |
| 2026-11-17 | Planned: RAG-only baseline uses one shared collection for all teams | Gives the leakage metric a meaningful comparison (to confirm before the Dec freeze) |
| 2026-11-19 | LLM is GPT-6 Luna (replaces gpt-4o-mini); embeddings stay text-embedding-3-small | Better answer quality for the budget; one embedding model everywhere, changing it means re-indexing |
| 2026-11-22 | Dataset v1.1 lives in `data/corpus/{shared,dev,sales,social}` (38 DOCX) with `data/corpus/manifest.csv` as the metadata source | One place for all team data; folder names match `team_id`s and collections |
| 2026-11-22 | Phase 1 loaders must read DOCX (supersedes the 2026-11-17 "PDF and TXT only" row) | The whole corpus is DOCX |
| 2026-11-22 | Fourth collection `shared` (company overview), readable by every team; `get_retriever(team_id)` searches the team collection + `shared` | Company-wide facts belong to no single team |
| 2026-11-22 | Confidential chunks: each "CONFIDENTIAL —" paragraph and every chunk of a RESTRICTED document gets `confidential=true`; used only for the owning team, never in cross-team answers or client-facing drafts | Makes leakage measurable at chunk level |
| 2026-11-22 | Superseded documents (`doc_status=superseded` in the manifest) are excluded from retrieval by default | They are deliberate distractors with old values |
| 2026-11-22 | `eval/datasets/dev` (222 questions, visible) is for tuning; `eval/datasets/test` (teammates' hidden questions) is for the final results only | Avoid tuning on the questions used for the final score |
| 2026-11-22 | `eval/`, `docs/` and `eval/datasets/tricks` are never ingested | Test material must not leak into the knowledge base |
| 2026-11-26 | Chunking: one Document per `Heading 2` section, then RecursiveCharacterTextSplitter (800 / 150) only for long sections; the `Document:` / `Section:` header is repeated on every chunk | Sections are already small (avg ~390 chars); every chunk keeps its document and section context |
| 2026-11-26 | Fixed chunk IDs `<source>::sNNN::cNN`; the indexer upserts by ID and `--reset` removes stale chunks | Re-indexing never duplicates chunks |
| 2026-11-26 | Chroma collections use cosine distance (`hnsw:space = cosine`) | Default L2 gave negative relevance scores (518 of 766 in one test run); cosine keeps them in 0–1 so a threshold is meaningful. Ranking is unchanged |
| 2026-11-26 | Two-stage fallback: score threshold 0.30 as an off-topic guard (no LLM call), then a grounded prompt whose "not in context" reply is detected in code | In-scope (0.48–0.78) and unanswerable (0.40–0.69) top scores overlap, so a threshold alone cannot separate them; all unanswerable questions were caught by the second stage |
| 2026-11-26 | No database in Phase 1: six hard-coded demo users (two per team); PostgreSQL arrives in December for users, profiles, chat history and the LangGraph checkpointer (supersedes the 2026-11-17 SQLite checkpointer row) | Nothing in v0.1 needs storage; PostgreSQL is what the proposal names and later phases need |
| 2026-11-26 | `/chat` takes only the question; `team_id` comes from the verified JWT, and a request that sends its own `team_id` is rejected (422) | The client can never choose its team |
| 2026-11-26 | `.env` is loaded into the process environment by `app/core/config.py` | Libraries such as LangSmith read the environment directly |
| 2026-11-26 | v0.1 evaluation is scored in plain code (key-fact match, retrieval hit, "said unknown", canary leak check); an LLM judge comes in December | Free and repeatable; strict text match undercounts correct answers worded differently |
| 2026-11-26 | v0.1 baseline (`eval/results/eval_2026-11-26_1528.json`, 36 questions): in-scope 14/18 strict (all 4 misses were wording), key-fact recall 81%, retrieval hit 94%; out-of-scope 6/6 said unknown; cross-team 0/12 leaks | First measured baseline; December changes must beat it |
