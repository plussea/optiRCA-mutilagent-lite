from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "OptiRCA Lite"
    host: str = "127.0.0.1"
    port: int = 8010
    data_dir: Path = Path("data")
    upload_dir: Path = Path("data/uploads")
    database_path: Path = Path("data/optirc_lite.db")
    lancedb_path: Path = Path("data/lancedb")
    lancedb_table: str = "knowledge"
    embedding_dimension: int = 64
    graph_path: Path = Path("data/knowledge_graph.json")

    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_timeout_seconds: float = 30.0


settings = Settings()
