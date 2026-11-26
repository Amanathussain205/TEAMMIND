"""Settings loaded from .env (API keys, model names, storage paths)."""

from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

# Put every .env value (including LANGSMITH_*) into the process environment, so
# libraries like LangSmith see them too. .env wins over stale terminal values.
load_dotenv(ENV_FILE, override=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    openai_api_key: str
    llm_model: str
    embedding_model: str = "text-embedding-3-small"

    jwt_secret: str
    jwt_expire_minutes: int = 480

    chroma_dir: str = "storage/chroma"
    sqlite_path: str = "storage/teammind.db"

    corpus_dir: str = "data/corpus"
    manifest_path: str = "data/corpus/manifest.csv"


settings = Settings() # type: ignore
