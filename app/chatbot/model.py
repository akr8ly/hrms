"""Shared language-model construction for chatbot workflows."""

from functools import lru_cache

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_ollama import ChatOllama

from app.chatbot.config import chatbot_settings


@lru_cache(maxsize=1)
def get_chat_model() -> BaseChatModel:
    """Build and cache the configured local chat model."""
    if chatbot_settings.llm_provider != "ollama":
        raise ValueError(
            "The local policy assistant currently requires "
            "CHATBOT_LLM_PROVIDER=ollama"
        )

    return ChatOllama(
        model=chatbot_settings.llm_model,
        base_url=chatbot_settings.ollama_base_url,
        temperature=chatbot_settings.llm_temperature,
        num_predict=chatbot_settings.max_answer_tokens,
        reasoning=True,
        validate_model_on_init=True,
    )
