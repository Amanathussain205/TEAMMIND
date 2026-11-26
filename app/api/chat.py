"""POST /chat -> answer with sources, scoped to the team_id from the JWT."""

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from app.api.auth import CurrentUser
from app.rag.chain import RagAnswer, answer_question

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    # extra="forbid": a client that sends its own team_id gets a 422, not silent trust.
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    question: str = Field(min_length=1, max_length=2000)


@router.post("/chat", response_model=RagAnswer)
def chat(request: ChatRequest, user: CurrentUser) -> RagAnswer:
    # The team is taken from the verified token, never from the request.
    return answer_question(request.question, team_id=user.team_id)
