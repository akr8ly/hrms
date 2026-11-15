import unittest

from langchain_core.messages import AIMessage, HumanMessage

from app.chatbot.agent_executor import (
    _category_listing_answer,
    _requested_category_listing,
)


class CategoryListingTests(unittest.TestCase):
    def test_explicit_category_listing_returns_every_category_section(self):
        category = _requested_category_listing(
            "List all available code of conduct policies with their IDs and titles.",
            [],
        )
        self.assertEqual(category, "code-of-conduct")

        result = _category_listing_answer(category)
        self.assertEqual(result["tools_used"], ["get_hr_policy_category"])
        self.assertGreaterEqual(len(result["sources"]), 1)
        self.assertTrue(all(item["category"] == category for item in result["sources"]))
        for source in result["sources"]:
            self.assertIn(f"[{source['policy_id']}] {source['title']}", result["answer"])

    def test_referential_listing_uses_the_previous_policy_category(self):
        history = [
            HumanMessage(content="Can you tell me all the code of conduct policies?"),
            AIMessage(content="Reporting concerns are covered by [POL-CONDUCT-005]."),
        ]
        category = _requested_category_listing(
            "List all available policies with their policy IDs and titles in that category.",
            history,
        )
        self.assertEqual(category, "code-of-conduct")

    def test_all_of_them_uses_the_immediately_prior_cited_category(self):
        category = _requested_category_listing(
            "all of them",
            [AIMessage(content="Conflicts of interest are covered by [POL-CONDUCT-002].")],
        )
        self.assertEqual(category, "code-of-conduct")


if __name__ == "__main__":
    unittest.main()
