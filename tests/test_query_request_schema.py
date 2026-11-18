import unittest

from pydantic import ValidationError

from app.schemas.query_request import QueryRequestCreate


class QueryRequestSchemaTests(unittest.TestCase):
    def test_accepts_supported_query_categories(self):
        query = QueryRequestCreate.model_validate({
            "category": "reimbursement_report",
            "subject": "Claim approval status",
            "description": "Please confirm the current approval stage of my claim.",
            "related_reference": "Claim 25",
        })
        self.assertEqual(query.category, "reimbursement_report")

    def test_allows_an_expense_claim_only_for_reimbursement_queries(self):
        query = QueryRequestCreate.model_validate({
            "category": "reimbursement_report",
            "subject": "Claim approval status",
            "description": "Please confirm the current approval stage of my claim.",
            "expense_claim_id": 25,
        })
        self.assertEqual(query.expense_claim_id, 25)
        with self.assertRaises(ValidationError):
            QueryRequestCreate.model_validate({
                "category": "employee_related",
                "subject": "Employee request",
                "description": "Please investigate this employee-related request.",
                "expense_claim_id": 25,
            })

    def test_rejects_unknown_categories_and_extra_fields(self):
        payload = {
            "category": "payroll",
            "subject": "Payroll query",
            "description": "Please investigate this request.",
        }
        with self.assertRaises(ValidationError):
            QueryRequestCreate.model_validate(payload)
        with self.assertRaises(ValidationError):
            QueryRequestCreate.model_validate({**payload, "category": "employee_related", "internal_note": "not allowed"})


if __name__ == "__main__":
    unittest.main()
