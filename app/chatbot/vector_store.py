import argparse

from langchain_chroma import Chroma
from langchain_core.documents import Document

from app.chatbot.config import chatbot_settings
from app.chatbot.embeddings import get_embeddings
from app.chatbot.policy_loader import load_policy_documents


def get_vector_store() -> Chroma:
    return Chroma(
        collection_name=chatbot_settings.collection_name,
        embedding_function=get_embeddings(),
        persist_directory=str(chatbot_settings.chroma_path),
        collection_metadata={"hnsw:space": "cosine"},
    )


def rebuild_policy_index() -> int:
    documents = load_policy_documents()
    store = get_vector_store()

    existing_ids = store.get(include=[])["ids"]
    if existing_ids:
        store.delete(ids=existing_ids)

    ids = [document.metadata["policy_id"] for document in documents]
    store.add_documents(documents=documents, ids=ids)
    from app.chatbot.bm25 import get_bm25_index

    get_bm25_index.cache_clear()
    return len(documents)


def retrieve_policies(
    question: str,
    *,
    top_k: int | None = None,
) -> list[Document]:
    cleaned_question = question.strip()
    if not cleaned_question:
        raise ValueError("Question cannot be empty")
    if len(cleaned_question) > chatbot_settings.max_question_length:
        raise ValueError(
            "Question exceeds the configured maximum length of "
            f"{chatbot_settings.max_question_length} characters"
        )

    result_limit = top_k or chatbot_settings.top_k
    return get_vector_store().similarity_search(
        cleaned_question,
        k=result_limit,
    )


def retrieve_policy_matches(
    question: str,
    *,
    top_k: int | None = None,
) -> list[tuple[Document, float]]:
    cleaned_question = question.strip()
    if not cleaned_question:
        raise ValueError("Question cannot be empty")
    if len(cleaned_question) > chatbot_settings.max_question_length:
        raise ValueError(
            "Question exceeds the configured maximum length of "
            f"{chatbot_settings.max_question_length} characters"
        )

    result_limit = top_k or chatbot_settings.top_k
    distance_matches = get_vector_store().similarity_search_with_score(
        cleaned_question,
        k=result_limit,
    )
    return [
        (document, max(0.0, min(1.0, 1.0 - distance)))
        for document, distance in distance_matches
    ]


def _main() -> None:
    parser = argparse.ArgumentParser(description="Manage the HR policy vector index")
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--query")
    args = parser.parse_args()

    if args.rebuild:
        count = rebuild_policy_index()
        print(f"Indexed {count} policy sections")

    if args.query:
        for document in retrieve_policies(args.query):
            print(
                f"{document.metadata['policy_id']}: "
                f"{document.metadata['title']}"
            )

    if not args.rebuild and not args.query:
        parser.error("Provide --rebuild and/or --query")


if __name__ == "__main__":
    _main()
