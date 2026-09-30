import argparse
from dataclasses import dataclass

from langchain_core.documents import Document

from app.chatbot.bm25 import get_bm25_index
from app.chatbot.config import chatbot_settings
from app.chatbot.vector_store import retrieve_policy_matches


@dataclass(frozen=True, slots=True)
class HybridPolicyMatch:
    document: Document
    score: float
    semantic_score: float
    bm25_score: float


def retrieve_hybrid_policy_matches(
    question: str,
    *,
    top_k: int | None = None,
) -> list[HybridPolicyMatch]:
    result_limit = top_k or chatbot_settings.top_k
    candidate_count = max(
        result_limit,
        chatbot_settings.hybrid_candidate_count,
    )

    semantic_matches = retrieve_policy_matches(
        question,
        top_k=candidate_count,
    )
    bm25_matches = get_bm25_index().search(
        question,
        limit=candidate_count,
    )

    semantic_by_id = {
        str(document.metadata["policy_id"]): max(0.0, min(1.0, score))
        for document, score in semantic_matches
    }
    maximum_bm25 = max(
        (match.score for match in bm25_matches),
        default=0.0,
    )
    bm25_by_id = {
        str(match.document.metadata["policy_id"]): (
            match.score / maximum_bm25 if maximum_bm25 > 0 else 0.0
        )
        for match in bm25_matches
    }

    documents_by_id = {
        str(document.metadata["policy_id"]): document
        for document, _ in semantic_matches
    }
    documents_by_id.update(
        {
            str(match.document.metadata["policy_id"]): match.document
            for match in bm25_matches
        }
    )

    total_weight = chatbot_settings.semantic_weight + chatbot_settings.bm25_weight
    if total_weight <= 0:
        raise ValueError("At least one hybrid retrieval weight must be positive")

    matches = []
    for policy_id, document in documents_by_id.items():
        semantic_score = semantic_by_id.get(policy_id, 0.0)
        bm25_score = bm25_by_id.get(policy_id, 0.0)
        combined_score = (
            chatbot_settings.semantic_weight * semantic_score
            + chatbot_settings.bm25_weight * bm25_score
        ) / total_weight
        matches.append(
            HybridPolicyMatch(
                document=document,
                score=combined_score,
                semantic_score=semantic_score,
                bm25_score=bm25_score,
            )
        )

    return sorted(matches, key=lambda match: match.score, reverse=True)[:result_limit]


def _main() -> None:
    parser = argparse.ArgumentParser(description="Test hybrid policy retrieval")
    parser.add_argument("question")
    args = parser.parse_args()

    for match in retrieve_hybrid_policy_matches(args.question):
        print(
            f"{match.document.metadata['policy_id']} | "
            f"hybrid={match.score:.3f} | "
            f"semantic={match.semantic_score:.3f} | "
            f"bm25={match.bm25_score:.3f} | "
            f"{match.document.metadata['title']}"
        )


if __name__ == "__main__":
    _main()
