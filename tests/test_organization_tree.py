import unittest

from datetime import date

from pydantic import ValidationError

from app.org_structure_api import TEAM_UPDATE_FIELDS, TeamMemberCreate, build_organisation_tree, validate_reporting_line


class OrganisationTreeTests(unittest.TestCase):
    def test_groups_people_by_division_and_department_and_nests_reports(self):
        result = build_organisation_tree(
            divisions=[{"id": 1, "code": "TECH", "name": "Technology"}],
            departments=[{"id": 10, "code": "DEV", "name": "Development"}],
            designations=[
                {"id": 1, "code": "MGR", "name": "Department Manager"},
                {"id": 2, "code": "ENG", "name": "Software Engineer"},
            ],
            employees=[
                {"id": 1, "employee_code": "MGR001", "first_name": "Maya", "last_name": "Rao", "division_id": 1, "department_id": 10, "designation_id": 1, "reporting_manager_id": None},
                {"id": 2, "employee_code": "ENG001", "first_name": "Aarav", "last_name": "Shah", "division_id": 1, "department_id": 10, "designation_id": 2, "reporting_manager_id": 1},
            ],
        )
        self.assertEqual(result["name"], "Company")
        division = result["divisions"][0]
        self.assertEqual(division["employee_count"], 2)
        department = division["departments"][0]
        self.assertEqual(department["name"], "Development")
        manager = department["employees"][0]
        self.assertEqual(manager["designation"], "Department Manager")
        self.assertEqual(manager["direct_reports"][0]["name"], "Aarav Shah")

    def test_cross_department_manager_does_not_duplicate_an_employee(self):
        result = build_organisation_tree(
            divisions=[{"id": 1, "code": "TECH", "name": "Technology"}],
            departments=[
                {"id": 10, "code": "DEV", "name": "Development"},
                {"id": 11, "code": "QA", "name": "Quality"},
            ],
            designations=[{"id": 1, "code": "ENG", "name": "Software Engineer"}],
            employees=[
                {"id": 1, "employee_code": "ENG001", "first_name": "Maya", "last_name": "Rao", "division_id": 1, "department_id": 10, "designation_id": 1, "reporting_manager_id": None},
                {"id": 2, "employee_code": "ENG002", "first_name": "Aarav", "last_name": "Shah", "division_id": 1, "department_id": 11, "designation_id": 1, "reporting_manager_id": 1},
            ],
        )
        departments = result["divisions"][0]["departments"]
        quality = next(item for item in departments if item["code"] == "QA")
        self.assertEqual(quality["employees"][0]["name"], "Aarav Shah")
        self.assertEqual(quality["employees"][0]["direct_reports"], [])
        self.assertEqual(quality["employees"][0]["external_reports_to"], "Maya Rao · Development")

    def test_reporting_line_rejects_self_reference_and_cycles(self):
        with self.assertRaisesRegex(ValueError, "own reporting manager"):
            validate_reporting_line(
                employee_id=1,
                manager_id=1,
                manager_by_employee_id={1: None},
            )

    def test_team_member_request_rejects_client_controlled_organisation_fields(self):
        payload = {
            "employee_code": "ENG003",
            "first_name": "Nina",
            "last_name": "Das",
            "date_of_birth": date(2000, 1, 1),
            "personal_email": "nina@example.com",
            "work_email": "nina@hrms.example.com",
            "phone_number": "9876543210",
            "residential_address": "Mumbai",
            "date_of_joining": date(2024, 1, 1),
            "employment_type": "permanent",
            "designation_id": 1,
            "reporting_manager_id": 999,
        }
        with self.assertRaises(ValidationError):
            TeamMemberCreate.model_validate(payload)
        self.assertNotIn("reporting_manager_id", TEAM_UPDATE_FIELDS)
        self.assertNotIn("employment_status", TEAM_UPDATE_FIELDS)

        with self.assertRaisesRegex(ValueError, "reporting cycle"):
            validate_reporting_line(
                employee_id=1,
                manager_id=2,
                manager_by_employee_id={1: None, 2: 3, 3: 1},
            )


if __name__ == "__main__":
    unittest.main()
