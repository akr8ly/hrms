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
    max_history: int = Field(default=10, ge=0, le=50)
    max_question_length: int = Field(default=500, ge=20, le=2000)
    llm_provider: Literal["openai", "ollama"] = "openai"
    llm_model: str = ""
    llm_api_key: SecretStr | None = None


chatbot_settings = ChatbotSettings()
