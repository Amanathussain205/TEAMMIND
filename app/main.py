"""FastAPI app: creates the app and includes the routers.

Run from the project root:  uvicorn app.main:app --reload
Interactive docs:           http://127.0.0.1:8000/docs
"""

from fastapi import FastAPI

from app.api import auth, chat

app = FastAPI(
    title="TeamMind",
    version="0.1.0",
    description="Team-isolated RAG assistant. Log in with a demo user, then ask your team's documents.",
)

app.include_router(auth.router)
app.include_router(chat.router)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok"}
