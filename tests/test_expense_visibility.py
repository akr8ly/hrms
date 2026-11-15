import unittest
from types import SimpleNamespace

from app.expense_api import _can_view_claim
from app.models import Employee
from app.models.role import Role


class FakeDatabase:
    def __init__(self, role_name: str, claimant_manager_id: int | None = None):
        self.role = SimpleNamespace(name=role_name)
        self.claimant = SimpleNamespace(reporting_manager_id=claimant_manager_id)

    def get(self, model, _identifier):
        if model is Role:
            return self.role
        if model is Employee:
            return self.claimant
        return None


def claim(status: str, claimant_employee_id: int = 10):
    return SimpleNamespace(status=status, claimant_employee_id=claimant_employee_id)


def user(role_id: int, employee_id: int | None):
    return SimpleNamespace(role_id=role_id, employee_id=employee_id)


class ExpenseVisibilityTests(unittest.TestCase):
    def test_draft_is_visible_to_its_claimant(self):
        self.assertTrue(_can_view_claim(FakeDatabase("employee"), user(2, 10), claim("draft")))

    def test_draft_is_hidden_from_l1_manager_and_l2_admin(self):
        self.assertFalse(_can_view_claim(FakeDatabase("employee", claimant_manager_id=7), user(2, 7), claim("draft")))
        self.assertFalse(_can_view_claim(FakeDatabase("admin"), user(1, 1), claim("draft")))

    def test_submitted_claim_is_visible_to_manager_and_admin(self):
        submitted = claim("submitted")
        self.assertTrue(_can_view_claim(FakeDatabase("employee", claimant_manager_id=7), user(2, 7), submitted))
        self.assertTrue(_can_view_claim(FakeDatabase("admin"), user(1, 1), submitted))


if __name__ == "__main__":
    unittest.main()
