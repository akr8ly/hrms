import argparse
from functools import lru_cache

from langchain_core.documents import Document
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from app.chatbot.config import chatbot_settings
from app.chatbot.hybrid_search import retrieve_hybrid_policy_matches
from app.chatbot.memory import session_memory
from app.chatbot.policy_loader import load_policy_documents


SYSTEM_PROMPT = """You are the HRMS policy assistant.
Answer only from the POLICY CONTEXT supplied by the application.
Do not use general knowledge, assumptions, or invented rules.
If the context does not answer the question, reply exactly:
I couldn't find this in the HR policies.
Keep the answer concise and practical.
Cite every policy used by placing its policy ID in square brackets, for example
[POL-LEAVE-001]. Never cite a policy that is not in the supplied context.
Return only the final answer. Do not show analysis, reasoning, or planning.
"""

NO_POLICY_ANSWER = "I couldn't find this in the HR policies."

CATEGORY_ALIASES = {
    "attendance": ("attendance",),
    "benefits": ("benefit", "benefits"),
    "code-of-conduct": ("conduct", "code of conduct"),
    "information-security": ("security", "information security"),
    "leave": ("leave", "leaves"),
    "payroll": ("payroll", "salary"),
    "remote-work": ("remote work", "work from home", "wfh"),
    "travel": ("travel",),
}


@lru_cache(maxsize=1)
def get_chat_model() -> BaseChatModel:
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


def _format_context(documents: list[Document]) -> str:
    sections = []
    for document in documents:
        sections.append(
            "\n".join(
                (
                    f"Policy ID: {document.metadata['policy_id']}",
                    f"Title: {document.metadata['title']}",
                    f"Category: {document.metadata['category_title']}",
                    document.page_content,
                )
            )
        )
    return "\n\n---\n\n".join(sections)


def _overview_response(question: str) -> dict[str, object] | None:
    normalized = " ".join(question.lower().split())
    if "all" not in normalized or "polic" not in normalized:
        return None

    documents = load_policy_documents()
    requested_category = next(
        (
            category
            for category, aliases in CATEGORY_ALIASES.items()
            if any(alias in normalized for alias in aliases)
        ),
        None,
    )

    if requested_category is None:
        categories: dict[str, int] = {}
        for document in documents:
            title = str(document.metadata["category_title"])
            categories[title] = categories.get(title, 0) + 1
        category_lines = [
            f"- {title} ({count} sections)"
            for title, count in sorted(categories.items())
        ]
        return {
            "answer": (
                "The HRMS contains these policy categories:\n"
                + "\n".join(category_lines)
                + "\nAsk about one category to view all of its policies."
            ),
            "sources": [],
        }

    category_documents = [
        document
        for document in documents
        if document.metadata["category"] == requested_category
    ]
    answer_lines = []
    for document in category_documents:
        title, body = document.page_content.split("\n\n", maxsplit=1)
        answer_lines.append(
            f"- {title}: {body} [{document.metadata['policy_id']}]"
        )
    return {
        "answer": "\n".join(answer_lines),
        "sources": [
            {
                "policy_id": document.metadata["policy_id"],
                "title": document.metadata["title"],
                "category": document.metadata["category"],
            }
            for document in category_documents
        ],
    }


def create_chat_session(*, user_id: int, user_role: str) -> str:
    """Create a user-owned in-memory chatbot session."""
    return session_memory.create_session(user_id=user_id, user_role=user_role)


def _prepare_session(
    *,
    question: str,
    session_id: str | None,
    user_id: int | None,
) -> list[BaseMessage]:
    if (session_id is None) != (user_id is None):
        raise ValueError("session_id and user_id must be provided together")
    if session_id is None or user_id is None:
        return []

    history = session_memory.get_langchain_history(
        session_id=session_id,
        user_id=user_id,
    )
    session_memory.add_message(
        session_id=session_id,
        user_id=user_id,
        role="user",
        content=question,
    )
    return history


def _contextual_retrieval_question(
    question: str,
    history: list[BaseMessage],
) -> str:
    if not history:
        return question

    recent_context = "\n".join(
        str(message.content).strip() for message in history[-4:]
    )
    combined = f"Previous conversation:\n{recent_context}\nCurrent question:\n{question}"
    limit = chatbot_settings.max_question_length
    if len(combined) <= limit:
        return combined

    current_block = f"Current question:\n{question}"
    remaining = max(0, limit - len(current_block) - 1)
    return f"{recent_context[-remaining:]}\n{current_block}"[-limit:]


def _finish_result(
    result: dict[str, object],
    *,
    session_id: str | None,
    user_id: int | None,
) -> dict[str, object]:
    if session_id is None or user_id is None:
        return result

    answer = str(result["answer"])
    session_memory.add_message(
        session_id=session_id,
        user_id=user_id,
        role="assistant",
        content=answer,
    )
    return {**result, "session_id": session_id}


def answer_policy_question(
    question: str,
    *,
    session_id: str | None = None,
    user_id: int | None = None,
) -> dict[str, object]:
    cleaned_question = question.strip()
    if not cleaned_question:
        raise ValueError("question cannot be empty")
    if len(cleaned_question) > chatbot_settings.max_question_length:
        raise ValueError("question exceeds the configured length limit")

    history = _prepare_session(
        question=cleaned_question,
        session_id=session_id,
        user_id=user_id,
    )

    overview = _overview_response(cleaned_question)
    if overview is not None:
        return _finish_result(
            overview,
            session_id=session_id,
            user_id=user_id,
        )

    retrieval_question = _contextual_retrieval_question(
        cleaned_question,
        history,
    )
    matches = retrieve_hybrid_policy_matches(retrieval_question)
    documents = [
        match.document
        for match in matches
        if match.score >= chatbot_settings.min_relevance_score
    ]
    if not documents:
        return _finish_result(
            {"answer": NO_POLICY_ANSWER, "sources": []},
            session_id=session_id,
            user_id=user_id,
        )

    context = _format_context(documents)
    response = get_chat_model().invoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            *history,
            HumanMessage(
                content=(
                    f"POLICY CONTEXT:\n{context}\n\n"
                    f"EMPLOYEE QUESTION:\n{cleaned_question}"
                )
            ),
        ]
    )

    answer = response.content
    if not isinstance(answer, str):
        raise TypeError("The language model returned unsupported content")
    answer = answer.strip()
    if not answer:
        return _finish_result(
            {"answer": NO_POLICY_ANSWER, "sources": []},
            session_id=session_id,
            user_id=user_id,
        )
    if answer.rstrip(". ").casefold() == NO_POLICY_ANSWER.rstrip(". ").casefold():
        return _finish_result(
            {"answer": NO_POLICY_ANSWER, "sources": []},
            session_id=session_id,
            user_id=user_id,
        )

    result = {
        "answer": answer,
        "sources": [
            {
                "policy_id": document.metadata["policy_id"],
                "title": document.metadata["title"],
                "category": document.metadata["category"],
            }
            for document in documents
        ],
    }
    return _finish_result(
        result,
        session_id=session_id,
        user_id=user_id,
    )


def _print_result(result: dict[str, object]) -> None:
    print(result["answer"])
    sources = result["sources"]
    if sources:
        print("\nRetrieved sources:")
        for source in sources:
            print(f"- {source['policy_id']}: {source['title']}")


def _interactive_chat(*, user_id: int, user_role: str) -> None:
    session_id = create_chat_session(user_id=user_id, user_role=user_role)
    print(f"Policy chat started. Session: {session_id}")
    print("Type exit or quit to end the session.\n")
    while True:
        try:
            question = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if question.casefold() in {"exit", "quit"}:
            break
        if not question:
            continue
        result = answer_policy_question(
            question,
            session_id=session_id,
            user_id=user_id,
        )
        print("Assistant: ", end="")
        _print_result(result)
        print()


def _main() -> None:
    parser = argparse.ArgumentParser(description="Ask the local HR policy assistant")
    parser.add_argument("question", nargs="?")
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Keep one in-memory session open for follow-up questions",
    )
    parser.add_argument("--user-id", type=int, default=1)
    parser.add_argument("--user-role", default="employee")
    args = parser.parse_args()
    if args.interactive:
        _interactive_chat(user_id=args.user_id, user_role=args.user_role)
        return
    if not args.question:
        parser.error("question is required unless --interactive is used")
    _print_result(answer_policy_question(args.question))


if __name__ == "__main__":
    _main()
