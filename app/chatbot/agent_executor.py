"""Tool-calling HR policy agent with bounded, user-owned session memory."""

import argparse
import re
from functools import lru_cache

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

from app.chatbot.config import chatbot_settings
from app.chatbot.memory import create_chat_session, session_memory
from app.chatbot.model import get_chat_model
from app.chatbot.policy_loader import load_policy_documents
from app.chatbot.prompts import AGENT_SYSTEM_PROMPT, NO_POLICY_ANSWER
from app.chatbot.tools import get_policy_tools


POLICY_ID_PATTERN = re.compile(r"\[(POL-[A-Z]+-\d{3})\]")


@lru_cache(maxsize=1)
def get_policy_agent_executor():
    """Build and cache the LangChain tool-calling execution graph."""
    return create_agent(
        model=get_chat_model(),
        tools=get_policy_tools(),
        system_prompt=AGENT_SYSTEM_PROMPT,
        name="hr_policy_agent",
    )


def _prepare_messages(
    *,
    question: str,
    session_id: str | None,
    user_id: int | None,
) -> list[BaseMessage]:
    if (session_id is None) != (user_id is None):
        raise ValueError("session_id and user_id must be provided together")

    history: list[BaseMessage] = []
    if session_id is not None and user_id is not None:
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
    return [*history, HumanMessage(content=question)]


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
) -> dict[str, object]:
    """Run the policy agent until it returns a final answer."""
    cleaned_question = question.strip()
    if not cleaned_question:
        raise ValueError("question cannot be empty")
    if len(cleaned_question) > chatbot_settings.max_question_length:
        raise ValueError("question exceeds the configured length limit")

    input_messages = _prepare_messages(
        question=cleaned_question,
        session_id=session_id,
        user_id=user_id,
    )
    execution = get_policy_agent_executor().invoke(
        {"messages": input_messages},
        config={"recursion_limit": 12},
    )
    messages = list(execution.get("messages", []))
    answer = _final_answer(messages)
    sources = _cited_sources(answer)

    result: dict[str, object] = {
        "answer": answer,
        "sources": sources,
        "tools_used": _tools_used(messages),
    }
    if session_id is not None and user_id is not None:
        memory_answer = answer[: chatbot_settings.max_memory_message_length]
        session_memory.add_message(
            session_id=session_id,
            user_id=user_id,
            role="assistant",
            content=memory_answer,
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
    _print_result(answer_with_policy_agent(args.question))


if __name__ == "__main__":
    _main()
