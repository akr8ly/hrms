from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class ChatbotSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env.chatbot",
        env_prefix="CHATBOT_",
        extra="ignore",
        hide_input_in_errors=True,
    )

    chroma_path: Path = Path("chroma_data")
    collection_name: str = Field(
        default="hrms_policies",
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9_-]+$",
    )
    top_k: int = Field(default=3, ge=1, le=10)
    min_relevance_score: float = Field(default=0.20, ge=0.0, le=1.0)
    hybrid_candidate_count: int = Field(default=10, ge=3, le=40)
    semantic_weight: float = Field(default=0.70, ge=0.0, le=1.0)
    bm25_weight: float = Field(default=0.30, ge=0.0, le=1.0)
    bm25_k1: float = Field(default=1.5, gt=0.0, le=3.0)
    bm25_b: float = Field(default=0.75, ge=0.0, le=1.0)
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    max_history: int = Field(default=10, ge=0, le=50)
    session_ttl_minutes: int = Field(default=15, ge=5, le=1440)
    max_memory_message_length: int = Field(default=4000, ge=100, le=10000)
    max_question_length: int = Field(default=500, ge=20, le=2000)
    llm_provider: Literal["openai", "ollama"] = "ollama"
    llm_model: str = "qwen3:4b"
    ollama_base_url: str = "http://127.0.0.1:11434"
    llm_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_answer_tokens: int = Field(default=4000, ge=100, le=8000)
    llm_api_key: SecretStr | None = None


chatbot_settings = ChatbotSettings()
