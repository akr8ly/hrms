"""Small, deterministic safety boundary for chatbot text."""

import re

from app.chatbot.config import chatbot_settings


MODERATION_FALLBACK = (
    "I can help with HR policy questions, but I can't process abusive or "
    "derogatory language. Please rephrase respectfully."
)
UNSAFE_MODEL_OUTPUT_FALLBACK = (
    "I couldn't produce a safe final answer. Please try again."
)
PROMPT_INJECTION_FALLBACK = (
    "I can only help with approved HR policies and permitted aggregate reports."
)


class ContentModerationError(ValueError):
    """Raised when a user message violates the chatbot language policy."""


class PromptInjectionError(ValueError):
    """Raised when a user message attempts to override assistant controls."""


_PROHIBITED_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bf+u+c+k+(?:ing|ed|er|ers)?\b",
        r"\bs+h+i+t+(?:ty|head)?\b",
        r"\bb+i+t+c+h+(?:es)?\b",
        r"\bb+a+s+t+a+r+d+(?:s)?\b",
        r"\b(?:idiot|moron|retard(?:ed)?)\b",
        r"\b(?:you|they|he|she)\s+(?:are|is)\s+(?:stupid|useless|worthless)\b",
        r"\b(?:kill|hurt)\s+(?:yourself|himself|herself|them)\b",
    )
)

_PROMPT_INJECTION_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\b(?:ignore|disregard|override|bypass)\b.{0,80}\b(?:previous|prior|system|developer|all)\b.{0,80}\b(?:instruction|prompt|rule|policy)s?\b",
        r"\b(?:reveal|show|print|repeat|dump|extract)\b.{0,80}\b(?:system|developer|hidden)\b.{0,40}\b(?:prompt|instruction|message)s?\b",
        r"(?:<\s*/?system\s*>|###\s*(?:system|developer)|\[\s*(?:system|developer)\s*\])",
        r"\b(?:jailbreak|do anything now|dan mode)\b",
    )
)

_SYSTEM_OUTPUT_PATTERN = re.compile(
    r"(?:tool handover contract|you are the hrms assistant for an authenticated|"
    r"answer hr policy questions only from available read-only policy tools)",
    re.IGNORECASE,
)


_PLANNING_OUTPUT_PATTERN = re.compile(
    r"^(?:okay[,!.]?\s*)?(?:"
    r"the user\s+(?:is|asked|wants)|"
    r"let me\s+(?:think|check|process|approach)|"
    r"i need to\s+(?:check|think|use|call|find)|"
    r"first[, ]+i need to|"
    r"we need to\s+(?:check|use|call|find)"
    r")",
    re.IGNORECASE,
)


def contains_prohibited_language(text: str) -> bool:
    """Return whether text matches a configured abusive-language pattern."""
    return any(pattern.search(text) for pattern in _PROHIBITED_PATTERNS)


def contains_prompt_injection(text: str) -> bool:
    """Return whether text attempts to override assistant instructions."""
    return any(pattern.search(text) for pattern in _PROMPT_INJECTION_PATTERNS)


def validate_input_text(text: str) -> str:
    """Normalize a user message and reject unsafe instructions."""
    cleaned = text.strip()
    if contains_prompt_injection(cleaned):
        raise PromptInjectionError(PROMPT_INJECTION_FALLBACK)
    if contains_prohibited_language(cleaned):
        raise ContentModerationError(MODERATION_FALLBACK)
    return cleaned


def truncate_response_text(text: str, max_characters: int) -> str:
    """Shorten text at a natural boundary without exceeding the limit."""
    if len(text) <= max_characters:
        return text

    available = max_characters - 1
    candidate = text[:available].rstrip()
    sentence_ends = list(re.finditer(r"[.!?](?=\s|$)", candidate))
    if sentence_ends and sentence_ends[-1].end() >= available // 2:
        candidate = candidate[: sentence_ends[-1].end()]
    elif " " in candidate:
        candidate = candidate.rsplit(" ", 1)[0]
    return candidate.rstrip() + "…"


def sanitize_output_text(text: str) -> str:
    """Return a safe model/tool response, replacing unsafe output."""
    cleaned = text.strip()
    if "</think>" in cleaned:
        cleaned = cleaned.rsplit("</think>", 1)[1].strip()
    cleaned = re.sub(
        r"<think>.*?</think>",
        "",
        cleaned,
        flags=re.IGNORECASE | re.DOTALL,
    ).strip()
    if "<think>" in cleaned.lower():
        return UNSAFE_MODEL_OUTPUT_FALLBACK
    if contains_prohibited_language(cleaned):
        return MODERATION_FALLBACK
    if _SYSTEM_OUTPUT_PATTERN.search(cleaned) or _PLANNING_OUTPUT_PATTERN.search(cleaned):
        return UNSAFE_MODEL_OUTPUT_FALLBACK
    return truncate_response_text(
        cleaned,
        chatbot_settings.max_response_length,
    )
