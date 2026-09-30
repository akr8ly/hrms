"""Read-only LangChain tools for exploring indexed HR policies."""

from langchain_core.documents import Document
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.chatbot.config import chatbot_settings
from app.chatbot.hybrid_search import retrieve_hybrid_policy_matches
from app.chatbot.policy_loader import load_policy_documents


CATEGORY_ALIASES = {
    "attendance": "attendance",
    "attendance policy": "attendance",
    "benefit": "benefits",
    "benefits": "benefits",
    "employee benefit": "benefits",
    "employee benefits": "benefits",
    "employee benefits policy": "benefits",
    "conduct": "code-of-conduct",
    "code of conduct": "code-of-conduct",
    "code of conduct policy": "code-of-conduct",
    "security": "information-security",
    "information security": "information-security",
    "information security policy": "information-security",
    "leave": "leave",
    "leaves": "leave",
    "leave policy": "leave",
    "payroll": "payroll",
    "payroll policy": "payroll",
    "salary": "payroll",
    "remote work": "remote-work",
    "remote work policy": "remote-work",
    "work from home": "remote-work",
    "wfh": "remote-work",
    "travel": "travel",
    "travel policy": "travel",
}


class SearchPoliciesInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    question: str = Field(min_length=1, max_length=500)


class CategoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    category: str = Field(min_length=2, max_length=50)


class PolicyIdInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    policy_id: str = Field(pattern=r"^POL-[A-Z]+-\d{3}$")

    @field_validator("policy_id", mode="before")
    @classmethod
    def normalize_policy_id(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value


def _policy_data(document: Document) -> dict[str, str]:
    return {
        "policy_id": str(document.metadata["policy_id"]),
        "title": str(document.metadata["title"]),
        "category": str(document.metadata["category"]),
        "category_title": str(document.metadata["category_title"]),
        "content": document.page_content,
    }


def search_policies(question: str) -> dict[str, object]:
    """Search HR policies using semantic and BM25 relevance."""
    matches = retrieve_hybrid_policy_matches(question)
    relevant = [
        match
        for match in matches
        if match.score >= chatbot_settings.min_relevance_score
    ]
    return {
        "query": question,
        "found": bool(relevant),
        "matches": [
            {
                **_policy_data(match.document),
                "hybrid_score": round(match.score, 4),
                "semantic_score": round(match.semantic_score, 4),
                "bm25_score": round(match.bm25_score, 4),
            }
            for match in relevant
        ],
    }


def list_policy_categories() -> dict[str, object]:
    """List available policy categories and their section counts."""
    category_counts: dict[str, dict[str, object]] = {}
    for document in load_policy_documents():
        category = str(document.metadata["category"])
        item = category_counts.setdefault(
            category,
            {
                "category": category,
                "title": str(document.metadata["category_title"]),
                "policy_count": 0,
            },
        )
        item["policy_count"] = int(item["policy_count"]) + 1
    return {
        "count": len(category_counts),
        "categories": sorted(
            category_counts.values(), key=lambda item: str(item["category"])
        ),
    }


def get_category_policies(category: str) -> dict[str, object]:
    """Return every policy section in one category."""
    normalized = " ".join(category.lower().replace("_", " ").split())
    for suffix in (" policies", " policy"):
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)].strip()
            break
    category_key = CATEGORY_ALIASES.get(normalized, normalized.replace(" ", "-"))
    policies = [
        _policy_data(document)
        for document in load_policy_documents()
        if document.metadata["category"] == category_key
    ]
    return {
        "category": category_key,
        "found": bool(policies),
        "count": len(policies),
        "policies": policies,
    }


def get_policy_by_id(policy_id: str) -> dict[str, object]:
    """Return one exact policy section by its indexed policy ID."""
    normalized = policy_id.strip().upper()
    document = next(
        (
            item
            for item in load_policy_documents()
            if item.metadata["policy_id"] == normalized
        ),
        None,
    )
    return {
        "policy_id": normalized,
        "found": document is not None,
        "policy": _policy_data(document) if document is not None else None,
    }


POLICY_TOOLS = (
    StructuredTool.from_function(
        func=search_policies,
        name="search_hr_policies",
        description=(
            "Search the indexed HR policies for sections relevant to an employee "
            "question. This tool only reads policy documents."
        ),
        args_schema=SearchPoliciesInput,
    ),
    StructuredTool.from_function(
        func=list_policy_categories,
        name="list_hr_policy_categories",
        description=(
            "List every available HR policy category and its policy count. "
            "This tool only reads policy documents."
        ),
    ),
    StructuredTool.from_function(
        func=get_category_policies,
        name="get_hr_policy_category",
        description=(
            "Get all policy sections from one HR policy category. "
            "This tool only reads policy documents."
        ),
        args_schema=CategoryInput,
    ),
    StructuredTool.from_function(
        func=get_policy_by_id,
        name="get_hr_policy_by_id",
        description=(
            "Get one exact HR policy section using an ID such as POL-LEAVE-001. "
            "This tool only reads policy documents."
        ),
        args_schema=PolicyIdInput,
    ),
)


def get_policy_tools() -> list[StructuredTool]:
    """Return a new list containing the registered read-only policy tools."""
    return list(POLICY_TOOLS)
