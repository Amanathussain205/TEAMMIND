"""API gate: the team always comes from a valid JWT, never from the client.

The RAG call is replaced with a fake, so these tests need no OpenAI key or index
and cost nothing. Retrieval isolation itself is covered by test_isolation.py.
"""

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

from app.api import chat as chat_api
from app.core.auth import ALGORITHM
from app.core.config import settings
from app.main import app
from app.rag.chain import RagAnswer

client = TestClient(app)


def login(username: str, password: str | None = None):
    return client.post("/auth/login", data={"username": username, "password": password or settings.demo_password})


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def token_for(username: str) -> str:
    return login(username).json()["access_token"]


def signed_token(**payload) -> str:
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


@pytest.fixture
def fake_rag(monkeypatch) -> list[str]:
    """Replace the RAG chain; record which team_id each call used."""
    calls: list[str] = []

    def fake_answer(question: str, team_id: str, **kwargs) -> RagAnswer:
        calls.append(team_id)
        return RagAnswer(team_id=team_id, question=question, answer="ok", answered=True,
                         fallback_reason=None, top_score=0.9, sources=[])

    monkeypatch.setattr(chat_api, "answer_question", fake_answer)
    return calls


# ---- login ----

def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_login_returns_token_and_user():
    response = login("ayesha")
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"] == {"user_id": "ayesha", "name": "Ayesha Malik", "team_id": "sales"}


def test_login_is_case_insensitive_for_username():
    assert login("  Ayesha ").status_code == 200


@pytest.mark.parametrize("username, password", [("ayesha", "wrong-password"), ("nobody", None), ("", None)])
def test_bad_login_is_rejected(username, password):
    assert login(username, password).status_code in (401, 422)


def test_me_returns_the_token_owner():
    response = client.get("/auth/me", headers=auth_header(token_for("bilal")))
    assert response.status_code == 200
    assert response.json()["team_id"] == "dev"


# ---- tokens ----

def test_chat_without_token_is_rejected(fake_rag):
    assert client.post("/chat", json={"question": "Hi"}).status_code == 401
    assert fake_rag == []


@pytest.mark.parametrize("token", [
    "not-a-jwt",
    jwt.encode({"sub": "ayesha", "team_id": "sales", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
               "a-different-secret-that-is-long-enough-for-hs256", algorithm=ALGORITHM),
])
def test_forged_token_is_rejected(token, fake_rag):
    assert client.post("/chat", json={"question": "Hi"}, headers=auth_header(token)).status_code == 401
    assert fake_rag == []


def test_expired_token_is_rejected(fake_rag):
    token = signed_token(sub="ayesha", team_id="sales", exp=datetime.now(timezone.utc) - timedelta(minutes=1))
    assert client.post("/chat", json={"question": "Hi"}, headers=auth_header(token)).status_code == 401


def test_token_with_changed_team_is_rejected(fake_rag):
    # Correctly signed, but claims a team the user is not in.
    token = signed_token(sub="ayesha", team_id="dev", exp=datetime.now(timezone.utc) + timedelta(hours=1))
    assert client.post("/chat", json={"question": "Hi"}, headers=auth_header(token)).status_code == 401
    assert fake_rag == []


# ---- chat ----

@pytest.mark.parametrize("username, team", [("bilal", "dev"), ("ayesha", "sales"), ("zara", "social")])
def test_chat_uses_the_team_from_the_token(username, team, fake_rag):
    response = client.post("/chat", json={"question": "What is our target?"}, headers=auth_header(token_for(username)))
    assert response.status_code == 200
    assert response.json()["team_id"] == team
    assert fake_rag == [team]


def test_client_cannot_choose_its_team(fake_rag):
    response = client.post("/chat", json={"question": "Roadmap?", "team_id": "dev"},
                           headers=auth_header(token_for("ayesha")))
    assert response.status_code == 422
    assert fake_rag == []


@pytest.mark.parametrize("question", ["", "   ", "x" * 2001])
def test_invalid_question_is_rejected(question, fake_rag):
    response = client.post("/chat", json={"question": question}, headers=auth_header(token_for("ayesha")))
    assert response.status_code == 422
    assert fake_rag == []
