import unittest
from datetime import date

from pydantic import ValidationError

from app.schemas.expense import ExpenseClaimCreate, ExpenseDecision


def entry():
    return {
        "expense_date": date.today(),
        "category": "travel",
        "description": "Taxi to client office",
        "requested_amount": "125.50",
    }


class ExpenseSchemaTests(unittest.TestCase):
    def test_claim_allows_at_most_five_entries_and_normalizes_currency(self):
        claim = ExpenseClaimCreate.model_validate({"cost_center": "TECH-OPS", "currency": "inr", "entries": [entry()] * 5})
        self.assertEqual(claim.currency, "INR")
        with self.assertRaises(ValidationError):
            ExpenseClaimCreate.model_validate({"cost_center": "TECH-OPS", "currency": "INR", "entries": [entry()] * 6})

    def test_rejection_requires_remarks(self):
        with self.assertRaises(ValidationError):
            ExpenseDecision.model_validate({"action": "rejected"})
        decision = ExpenseDecision.model_validate({"action": "rejected", "remarks": "Missing supporting document"})
        self.assertEqual(decision.action, "rejected")


if __name__ == "__main__":
    unittest.main()
