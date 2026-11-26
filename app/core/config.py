"""Settings loaded from .env (API keys, model names, storage paths)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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