import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache

from langchain_core.documents import Document

from app.chatbot.config import chatbot_settings
from app.chatbot.policy_loader import load_policy_documents


TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*", re.IGNORECASE)
STOP_WORDS = {
    "a",
    "about",
    "an",
    "and",
    "are",
    "at",
    "be",
    "been",
    "being",
    "can",
    "could",
    "did",
    "do",
    "does",
    "explain",
    "for",
    "from",
    "how",
    "i",
    "if",
    "in",
    "is",
    "it",
    "its",
    "me",
    "my",
    "of",
    "on",
    "or",
    "should",
    "tell",
    "that",
    "the",
    "these",
    "this",
    "those",
    "to",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
    "would",
    "you",
    "your",
}


def tokenize(text: str) -> list[str]:
    return [
        token
        for match in TOKEN_PATTERN.finditer(text)
        if (token := match.group(0).lower()) not in STOP_WORDS
    ]


@dataclass(frozen=True, slots=True)
class BM25Match:
    document: Document
    score: float


class BM25PolicyIndex:
    def __init__(self, documents: list[Document]) -> None:
        if not documents:
            raise ValueError("BM25 requires at least one policy document")

        self.documents = documents
        self.term_frequencies: list[Counter[str]] = []
        self.document_lengths: list[int] = []
        document_frequencies: Counter[str] = Counter()

        for document in documents:
            metadata_text = " ".join(
                str(document.metadata.get(field, ""))
                for field in (
                    "policy_id",
                    "title",
                    "category",
                    "category_title",
                )
            )
            tokens = tokenize(f"{metadata_text} {document.page_content}")
            frequencies = Counter(tokens)
            self.term_frequencies.append(frequencies)
            self.document_lengths.append(len(tokens))
            document_frequencies.update(frequencies.keys())

        self.document_count = len(documents)
        self.average_document_length = (
            sum(self.document_lengths) / self.document_count
        )
        self.inverse_document_frequencies = {
            term: math.log(
                1
                + (
                    self.document_count
                    - document_frequency
                    + 0.5
                )
                / (document_frequency + 0.5)
            )
            for term, document_frequency in document_frequencies.items()
        }

    def search(self, query: str, *, limit: int) -> list[BM25Match]:
        query_terms = tokenize(query)
        if not query_terms:
            return []

        matches = [
            BM25Match(document=document, score=self._score(index, query_terms))
            for index, document in enumerate(self.documents)
        ]
        return sorted(matches, key=lambda match: match.score, reverse=True)[:limit]

    def _score(self, document_index: int, query_terms: list[str]) -> float:
        frequencies = self.term_frequencies[document_index]
        document_length = self.document_lengths[document_index]
        score = 0.0

        for term in query_terms:
            term_frequency = frequencies.get(term, 0)
            if not term_frequency:
                continue
            inverse_document_frequency = self.inverse_document_frequencies.get(
                term,
                0.0,
            )
            length_normalization = 1 - chatbot_settings.bm25_b + (
                chatbot_settings.bm25_b
                * document_length
                / self.average_document_length
            )
            numerator = term_frequency * (chatbot_settings.bm25_k1 + 1)
            denominator = term_frequency + (
                chatbot_settings.bm25_k1 * length_normalization
            )
            score += inverse_document_frequency * numerator / denominator

        return score


@lru_cache(maxsize=1)
def get_bm25_index() -> BM25PolicyIndex:
    return BM25PolicyIndex(load_policy_documents())
