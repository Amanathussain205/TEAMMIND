"""Demo users and JWTs. The token carries user_id and team_id.

Phase 1 uses hard-coded demo users on purpose (DECISIONS.md, 2026-11-17). They move
to PostgreSQL with hashed passwords in December; only `authenticate` changes then.
team_id always comes from the user record here, never from the client.
"""

import hmac
from datetime import datetime, timedelta, timezone

import jwt
from pydantic import BaseModel

from app.core.config import settings

ALGORITHM = "HS256"


class User(BaseModel):
    user_id: str
    name: str
    team_id: str


# Two demo users per team, named after people in the corpus. All share DEMO_PASSWORD.
DEMO_USERS = [
    User(user_id="bilal", name="Bilal Qureshi", team_id="dev"),
    User(user_id="hira", name="Hira Javed", team_id="dev"),
    User(user_id="ayesha", name="Ayesha Malik", team_id="sales"),
    User(user_id="kamran", name="Kamran Shah", team_id="sales"),
    User(user_id="zara", name="Zara Ahmed", team_id="social"),
    User(user_id="noor", name="Noor Fatima", team_id="social"),
]
USERS = {user.user_id: user for user in DEMO_USERS}


class InvalidToken(Exception):
    """The token is missing, expired, tampered with, or names an unknown user."""


def authenticate(username: str, password: str) -> User | None:
    """Return the user if the username and password are correct, else None."""
    user = USERS.get(username.strip().lower())
    if user is None:
        return None
    if not hmac.compare_digest(password.encode(), settings.demo_password.encode()):
        return None
    return user


def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user.user_id,
        "team_id": user.team_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def user_from_token(token: str) -> User:
    """Verify the token and return its user. Raises InvalidToken on any problem."""
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[ALGORITHM], options={"require": ["sub", "exp"]}
        )
    except jwt.PyJWTError as error:
        raise InvalidToken(str(error)) from error

    user = USERS.get(payload["sub"])
    # The team in the token must still match the user's team on the server.
    if user is None or payload.get("team_id") != user.team_id:
        raise InvalidToken("Unknown user or team mismatch")
    return user
