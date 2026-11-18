import unittest

from app.query_api import _expense_query_bucket


class ExpenseQueryRoutingTests(unittest.TestCase):
    def test_approved_bucket_only_contains_final_or_finance_approved_claims(self):
        self.assertEqual(_expense_query_bucket("l2_approved"), "approved")
        self.assertEqual(_expense_query_bucket("reimbursed"), "approved")

    def test_pending_bucket_keeps_unlinked_and_in_progress_claims(self):
        for status in (None, "draft", "submitted", "l1_approved", "l1_rejected", "l2_rejected"):
            with self.subTest(status=status):
                self.assertEqual(_expense_query_bucket(status), "pending")


if __name__ == "__main__":
    unittest.main()
