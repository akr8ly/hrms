import unittest
from types import SimpleNamespace

from fastapi import HTTPException

from app.org_structure_api import _reporting_manager_or_403
from app.schemas.user import CurrentUserRead


class FakeDatabase:
    def __init__(self, direct_report_id: int | None):
        self.direct_report_id = direct_report_id
        self.manager = SimpleNamespace(id=7, deleted_at=None, employment_status="active")

    def get(self, _model, _employee_id):
        return self.manager

    def scalar(self, _statement):
        return self.direct_report_id


class ReportingManagerPermissionTests(unittest.TestCase):
    def test_only_an_employee_with_a_direct_report_is_a_reporting_manager(self):
        user = SimpleNamespace(employee_id=7)
        manager = _reporting_manager_or_403(FakeDatabase(direct_report_id=9), user)
        self.assertEqual(manager.id, 7)

    def test_employee_without_a_direct_report_cannot_manage_team_members(self):
        user = SimpleNamespace(employee_id=7)
        with self.assertRaises(HTTPException) as error:
            _reporting_manager_or_403(FakeDatabase(direct_report_id=None), user)
        self.assertEqual(error.exception.status_code, 403)

    def test_current_user_contract_exposes_reporting_manager_flag(self):
        current_user = CurrentUserRead(
            id=1,
            username="manager",
            role_id=2,
            employee_id=7,
            approval_status="approved",
            role="employee",
            is_reporting_manager=True,
        )
        self.assertTrue(current_user.is_reporting_manager)


if __name__ == "__main__":
    unittest.main()
