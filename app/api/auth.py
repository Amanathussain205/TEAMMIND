"""POST /auth/login -> JWT with user_id and team_id. GET /auth/me -> the current user."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel

from app.core.auth import (
    InvalidToken,
    User,
    authenticate,
    create_access_token,
    user_from_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# Lets the "Authorize" button in /docs log in with a username and password.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

UNAUTHORIZED = {"WWW-Authenticate": "Bearer"}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: User


@router.post("/login", response_model=TokenResponse)
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()]) -> TokenResponse:
    user = authenticate(form.username, form.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect username or password", headers=UNAUTHORIZED)
    return TokenResponse(access_token=create_access_token(user), user=user)


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> User:
    """Dependency for protected endpoints: the user (and team) come only from the token."""
    try:
        return user_from_token(token)
    except InvalidToken:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token", headers=UNAUTHORIZED)


CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("/me", response_model=User)
def me(user: CurrentUser) -> User:
    return user
