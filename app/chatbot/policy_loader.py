import re
from pathlib import Path

from langchain_core.documents import Document


POLICIES_DIRECTORY = Path(__file__).resolve().parent / "policies"
POLICY_HEADING = re.compile(
    r"^##\s+(?P<policy_id>POL-[A-Z]+-\d{3}):\s+(?P<title>.+?)\s*$"
)


class PolicyFormatError(ValueError):
    """Raised when a policy Markdown file does not follow the indexed format."""


def load_policy_documents(
    policies_directory: Path = POLICIES_DIRECTORY,
) -> list[Document]:
    if not policies_directory.is_dir():
        raise PolicyFormatError(
            f"Policy directory does not exist: {policies_directory}"
        )

    policy_files = sorted(policies_directory.glob("*-policy.md"))
    if not policy_files:
        raise PolicyFormatError(
            f"No policy Markdown files found in: {policies_directory}"
        )

    documents: list[Document] = []
    policy_ids: set[str] = set()

    for policy_file in policy_files:
        file_documents = parse_policy_file(policy_file)
        for document in file_documents:
            policy_id = document.metadata["policy_id"]
            if policy_id in policy_ids:
                raise PolicyFormatError(
                    f"Duplicate policy ID found: {policy_id}"
                )
            policy_ids.add(policy_id)
            documents.append(document)

    return documents


def parse_policy_file(policy_file: Path) -> list[Document]:
    content = policy_file.read_text(encoding="utf-8")
    lines = content.splitlines()
    category_title = _find_category_title(lines, policy_file)
    category = policy_file.stem.removesuffix("-policy")
    documents: list[Document] = []
    current: dict[str, str | list[str]] | None = None

    for line_number, line in enumerate(lines, start=1):
        match = POLICY_HEADING.match(line)
        if match:
            if current is not None:
                documents.append(
                    _build_document(current, policy_file, category, category_title)
                )
            current = {
                "policy_id": match.group("policy_id"),
                "title": match.group("title").strip(),
                "body": [],
            }
            continue

        if line.startswith("## "):
            raise PolicyFormatError(
                f"Invalid policy heading in {policy_file.name}:{line_number}. "
                "Expected '## POL-CATEGORY-001: Title'."
            )

        if current is not None:
            body = current["body"]
            assert isinstance(body, list)
            body.append(line)

    if current is not None:
        documents.append(
            _build_document(current, policy_file, category, category_title)
        )

    if not documents:
        raise PolicyFormatError(
            f"No indexed policy sections found in: {policy_file.name}"
        )

    return documents


def _find_category_title(lines: list[str], policy_file: Path) -> str:
    for line in lines:
        if line.startswith("# "):
            title = line[2:].strip()
            if title:
                return title
    raise PolicyFormatError(
        f"Missing '# Category Policy' heading in: {policy_file.name}"
    )


def _build_document(
    section: dict[str, str | list[str]],
    policy_file: Path,
    category: str,
    category_title: str,
) -> Document:
    policy_id = section["policy_id"]
    title = section["title"]
    body_lines = section["body"]
    assert isinstance(policy_id, str)
    assert isinstance(title, str)
    assert isinstance(body_lines, list)

    body = "\n".join(body_lines).strip()
    if not body:
        raise PolicyFormatError(
            f"Policy section {policy_id} has no content in {policy_file.name}"
        )

    return Document(
        page_content=f"{title}\n\n{body}",
        metadata={
            "policy_id": policy_id,
            "title": title,
            "category": category,
            "category_title": category_title,
            "source": policy_file.name,
        },
    )


if __name__ == "__main__":
    loaded_documents = load_policy_documents()
    loaded_categories = sorted(
        {document.metadata["category"] for document in loaded_documents}
    )
    print(f"Loaded {len(loaded_documents)} policy sections")
    print(f"Categories: {', '.join(loaded_categories)}")
