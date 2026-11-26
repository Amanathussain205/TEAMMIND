# TeamMind

A multi-agent framework for team-personalized AI assistants (BS AI Final Year Project).
Each team (Development, Sales, Social Media) gets its own agent built from its own documents,
with team data isolated in code.

## Setup

Requires Python 3.12 (ChromaDB does not support 3.14).

```bash
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
copy .env.example .env   # then fill in the keys
```

## Run (Phase 1)

With the virtual environment activated:

```bash
uvicorn app.main:app --reload
streamlit run ui/streamlit_app.py
pytest
```

## Layout

| Folder | Contents |
|---|---|
| `app/core` | Config, JWT auth, database setup |
| `app/api` | FastAPI routers |
| `app/ingestion` | Loaders, splitter, indexer |
| `app/retrieval` | Team-scoped retrievers (`get_retriever(team_id)`) |
| `app/rag` | Basic RAG chain with sources and fallback |
| `app/profiles` | Team profile schema and extraction (Phase 2) |
| `app/agents` | LangGraph team agent, supervisor, tools (Phases 3-4) |
| `app/security` | Sanitizer, LLM guard, output validator (Phase 4) |
| `baselines` | Generic LLM and RAG-only baselines, frozen at v0.2 |
| `eval` | Judges and runner (Phase 5); `datasets/dev` (visible dev set), `datasets/test` (hidden test set), `datasets/tricks` (injection documents, never ingested); `results` |
| `data` | `company_description.md` (source of truth), `corpus/` (38 DOCX: `shared`, `dev`, `sales`, `social` + `manifest.csv`), `seed/` CSVs |
| `docs` | Non-code project documents: dataset fact register, readable question lists (never ingested) |
| `ui` | Streamlit app |
| `storage` | Chroma and SQLite files (git-ignored) |

Design choices are logged in [DECISIONS.md](DECISIONS.md).
