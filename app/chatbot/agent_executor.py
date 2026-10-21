"""Tool-calling HR policy agent with bounded, user-owned session memory."""

import argparse
import re
from functools import lru_cache

from langchain.agents import create_agent
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    ToolMessage,
)

from app.chatbot.config import chatbot_settings
from app.chatbot.admin_tools import get_admin_tools
from app.chatbot.memory import create_chat_session, session_memory
from app.chatbot.model import get_chat_model
from app.chatbot.moderation import (
    ContentModerationError,
    MODERATION_FALLBACK,
    sanitize_output_text,
    validate_input_text,
)
from app.chatbot.hybrid_search import retrieve_hybrid_policy_matches
from app.chatbot.policy_loader import load_policy_documents
from app.chatbot.prompts import (
    NO_POLICY_ANSWER,
    get_agent_system_prompt,
)
from app.chatbot.tools import get_policy_tools


POLICY_ID_PATTERN = re.compile(r"\[(POL-[A-Z]+-\d{3})\]")
_CLEAR_FOLLOW_UP_PATTERN = re.compile(
    r"^(?:how many(?: (?:days|hours|times))?(?: can i take)?|what about (?:it|that|this)|"
    r"does (?:it|that|this) apply|when can i take (?:it|that)|"
    r"and (?:what|how|when))\??$",
    re.IGNORECASE,
)
_ANALYTICS_PATTERN = re.compile(
    r"\b(?:headcount|employee count|employees? (?:are|work|exist)|"
    r"how many employees|workforce|staff count|division[- ]wise|"
    r"department[- ]wise|designation[- ]wise|location[- ]wise)\b",
    re.IGNORECASE,
)


@lru_cache(maxsize=3)
def get_policy_agent_executor(user_role: str = "employee"):
    """Build and cache the LangChain tool-calling execution graph."""
    role = user_role.strip().lower()
    if role not in {"admin", "employee", "query"}:
        raise ValueError("Unsupported chatbot role")
    return create_agent(
        model=get_chat_model(),
        tools=[*get_policy_tools(), *get_admin_tools(role)],
        system_prompt=get_agent_system_prompt(role),
        name="hr_policy_agent",
    )


def _prepare_messages(
    *,
    question: str,
    session_id: str | None,
    user_id: int | None,
    user_role: str,
) -> list[BaseMessage]:
    if (session_id is None) != (user_id is None):
        raise ValueError("session_id and user_id must be provided together")

    history: list[BaseMessage] = []
    if session_id is not None and user_id is not None:
        history = session_memory.get_langchain_history(
            session_id=session_id,
            user_id=user_id,
            user_role=user_role,
        )
        session_memory.add_message(
            session_id=session_id,
            user_id=user_id,
            role="user",
            content=question,
            user_role=user_role,
        )
    return [*history, HumanMessage(content=question)]


def _is_clear_follow_up(question: str) -> bool:
    """Allow history to clarify only short, explicitly referential questions."""
    normalized = " ".join(question.strip().split())
    return bool(_CLEAR_FOLLOW_UP_PATTERN.fullmatch(normalized))


def _current_policy_retrieval_question(
    question: str,
    history: list[BaseMessage],
) -> str:
    """Use the current turn unless a narrow follow-up needs its prior question."""
    if not history or not _is_clear_follow_up(question):
        return question

    prior_question = next(
        (
            _message_text(message)
            for message in reversed(history)
            if isinstance(message, HumanMessage)
        ),
        "",
    ).strip()
    if not prior_question:
        return question
    return f"{prior_question}\nFollow-up: {question}"


def _grounded_policy_answer(
    question: str,
    *,
    retrieval_question: str,
    user_role: str,
) -> dict[str, object]:
    """Answer from this turn's retrieved policy sections only."""
    matches = retrieve_hybrid_policy_matches(retrieval_question, top_k=10)
    documents = [
        match.document
        for match in matches
        if match.score >= chatbot_settings.min_relevance_score
    ]
    if not documents:
        return {
            "answer": NO_POLICY_ANSWER,
            "sources": [],
            "tools_used": ["search_hr_policies"],
        }

    # The agent sees only the current user question. The retrieved IDs below
    # form the hard boundary for the answer it may return.
    #
    # Local models can occasionally omit a final answer or citation after a
    # successful tool call. In that case, return the highest ranked retrieved
    # section verbatim instead of incorrectly claiming no policy was found.
    messages: list[BaseMessage] = []
    try:
        execution = get_policy_agent_executor(user_role).invoke(
            {"messages": [HumanMessage(content=question)]},
            config={"recursion_limit": 12},
        )
        messages = list(execution.get("messages", []))
        answer = sanitize_output_text(_final_answer(messages))
    except Exception:
        answer = NO_POLICY_ANSWER
    allowed_ids = {str(document.metadata["policy_id"]) for document in documents}
    cited_ids = set(POLICY_ID_PATTERN.findall(answer))
    if (
        answer.rstrip(". ").casefold() == NO_POLICY_ANSWER.rstrip(". ").casefold()
        or not cited_ids
        or not cited_ids.issubset(allowed_ids)
    ):
        return _retrieved_section_fallback(documents[0])

    document_by_id = {
        str(document.metadata["policy_id"]): document for document in documents
    }
    return {
        "answer": answer,
        "sources": [
            {
                "policy_id": policy_id,
                "title": str(document_by_id[policy_id].metadata["title"]),
                "category": str(document_by_id[policy_id].metadata["category"]),
            }
            for policy_id in dict.fromkeys(POLICY_ID_PATTERN.findall(answer))
        ],
        "tools_used": _tools_used(messages),
    }


def _retrieved_section_fallback(document) -> dict[str, object]:
    """Return the highest-ranked policy section when the model cannot cite it."""
    policy_id = str(document.metadata["policy_id"])
    section = str(document.page_content).strip()
    _, separator, body = section.partition("\n\n")
    answer_body = body.strip() if separator and body.strip() else section
    answer = sanitize_output_text(f"{answer_body} [{policy_id}]")
    return {
        "answer": answer,
        "sources": [
            {
                "policy_id": policy_id,
                "title": str(document.metadata["title"]),
                "category": str(document.metadata["category"]),
            }
        ],
        "tools_used": ["search_hr_policies"],
    }


def _is_admin_analytics_question(question: str, role: str) -> bool:
    return role == "admin" and bool(_ANALYTICS_PATTERN.search(question))


def _message_text(message: BaseMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    return " ".join(str(block) for block in content)


def _estimated_tokens(message: BaseMessage) -> int:
    """Use a conservative four-characters-per-token estimate."""
    return max(1, (len(_message_text(message)) + 3) // 4) + 8


def _trim_messages_to_token_budget(
    messages: list[BaseMessage],
) -> list[BaseMessage]:
    """Keep the newest complete messages within the configured input budget."""
    selected: list[BaseMessage] = []
    used_tokens = 0
    for message in reversed(messages):
        message_tokens = _estimated_tokens(message)
        if selected and used_tokens + message_tokens > chatbot_settings.max_input_tokens:
            break
        selected.append(message)
        used_tokens += message_tokens
    return list(reversed(selected))


def _final_answer(messages: list[BaseMessage]) -> str:
    for message in reversed(messages):
        if not isinstance(message, AIMessage) or message.tool_calls:
            continue
        content = message.content
        if isinstance(content, str) and content.strip():
            return content.strip()
        if isinstance(content, list):
            text = "".join(
                str(block.get("text", ""))
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            ).strip()
            if text:
                return text
    return NO_POLICY_ANSWER


def _cited_sources(answer: str) -> list[dict[str, str]]:
    if answer.rstrip(". ").casefold() == NO_POLICY_ANSWER.rstrip(". ").casefold():
        return []

    cited_ids = list(dict.fromkeys(POLICY_ID_PATTERN.findall(answer)))
    documents = {
        str(document.metadata["policy_id"]): document
        for document in load_policy_documents()
    }
    return [
        {
            "policy_id": policy_id,
            "title": str(documents[policy_id].metadata["title"]),
            "category": str(documents[policy_id].metadata["category"]),
        }
        for policy_id in cited_ids
        if policy_id in documents
    ]


def _tools_used(messages: list[BaseMessage]) -> list[str]:
    return list(
        dict.fromkeys(
            message.name
            for message in messages
            if isinstance(message, ToolMessage) and message.name
        )
    )


def answer_with_policy_agent(
    question: str,
    *,
    session_id: str | None = None,
    user_id: int | None = None,
    user_role: str = "employee",
) -> dict[str, object]:
    """Run the policy agent until it returns a final answer."""
    role = user_role.strip().lower()
    if (session_id is None) != (user_id is None):
        raise ValueError("session_id and user_id must be provided together")
    if session_id is not None and user_id is not None:
        session_memory.validate_identity(
            session_id=session_id,
            user_id=user_id,
            user_role=role,
        )
    try:
        cleaned_question = validate_input_text(question)
    except ContentModerationError:
        result: dict[str, object] = {
            "answer": MODERATION_FALLBACK,
            "sources": [],
            "tools_used": [],
        }
        if session_id is not None:
            result["session_id"] = session_id
        return result
    if not cleaned_question:
        raise ValueError("question cannot be empty")
    if len(cleaned_question) > chatbot_settings.max_question_length:
        raise ValueError("question exceeds the configured length limit")

    prepared_messages = _prepare_messages(
        question=cleaned_question,
        session_id=session_id,
        user_id=user_id,
        user_role=role,
    )
    history = prepared_messages[:-1]

    if _is_admin_analytics_question(cleaned_question, role):
        # Analytics is the only path that needs the tool-calling agent. Do not
        # give it old policy answers, which cannot be evidence for a report.
        execution = get_policy_agent_executor(role).invoke(
            {"messages": [HumanMessage(content=cleaned_question)]},
            config={"recursion_limit": 12},
        )
        messages = list(execution.get("messages", []))
        answer = sanitize_output_text(_final_answer(messages))
        result: dict[str, object] = {
            "answer": answer,
            "sources": _cited_sources(answer),
            "tools_used": _tools_used(messages),
        }
    else:
        # The current question determines retrieval. History may only clarify a
        # small set of explicit follow-ups and is never supplied to the model.
        result = _grounded_policy_answer(
            cleaned_question,
            retrieval_question=_current_policy_retrieval_question(
                cleaned_question,
                history,
            ),
            user_role=role,
        )
    if session_id is not None and user_id is not None:
        memory_answer = str(result["answer"])[
            : chatbot_settings.max_memory_message_length
        ]
        session_memory.add_message(
            session_id=session_id,
            user_id=user_id,
            role="assistant",
            content=memory_answer,
            user_role=role,
        )
        result["session_id"] = session_id
    return result


def _print_result(result: dict[str, object]) -> None:
    print(result["answer"])
    if result["sources"]:
        print("\nSources:")
        for source in result["sources"]:
            print(f"- {source['policy_id']}: {source['title']}")
    if result["tools_used"]:
        print("\nTools used: " + ", ".join(result["tools_used"]))


def _interactive_chat(*, user_id: int, user_role: str) -> None:
    session_id = create_chat_session(user_id=user_id, user_role=user_role)
    print(f"Policy agent started. Session: {session_id}")
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
        result = answer_with_policy_agent(
            question,
            session_id=session_id,
            user_id=user_id,
            user_role=user_role,
        )
        print("Agent: ", end="")
        _print_result(result)
        print()


def _main() -> None:
    parser = argparse.ArgumentParser(description="Run the HR policy tool agent")
    parser.add_argument("question", nargs="?")
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Keep one memory session open for follow-up questions",
    )
    parser.add_argument("--user-id", type=int, default=1)
    parser.add_argument("--user-role", default="employee")
    args = parser.parse_args()

    if args.interactive:
        _interactive_chat(user_id=args.user_id, user_role=args.user_role)
        return
    if not args.question:
        parser.error("question is required unless --interactive is used")
    _print_result(
        answer_with_policy_agent(args.question, user_role=args.user_role)
    )


if __name__ == "__main__":
    _main()
