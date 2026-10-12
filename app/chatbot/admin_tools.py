"""Admin-only, read-only aggregate employee analytics."""

from typing import Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select

from app.database import SessionLocal
from app.models.department import Department
from app.models.designation import Designation
from app.models.division import Division
from app.models.employee import Employee
from app.models.location import Location


ReportDimension = Literal[
    "department",
    "division",
    "designation",
    "location",
    "employment_status",
    "employment_type",
]


class EmployeeReportInput(BaseModel):
    """Only non-PII dimensions and filters accepted by the report tool."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    group_by: ReportDimension
    division_id: int | None = None
    department_id: int | None = None
    designation_id: int | None = None
    location_id: int | None = None
    employment_status: str | None = None
    employment_type: str | None = None


_MASTER_DIMENSIONS = {
    "department": (Department, Employee.department_id),
    "division": (Division, Employee.division_id),
    "designation": (Designation, Employee.designation_id),
    "location": (Location, Employee.location_id),
}


def _filters(data: EmployeeReportInput):
    conditions = [Employee.deleted_at.is_(None)]
    for name in (
        "division_id",
        "department_id",
        "designation_id",
        "location_id",
        "employment_status",
        "employment_type",
    ):
        value = getattr(data, name)
        if value is not None:
            conditions.append(getattr(Employee, name) == value)
    return conditions


def get_employee_analytics_report(**kwargs) -> dict[str, object]:
    """Aggregate active employee rows without reading encrypted PII columns."""
    data = EmployeeReportInput.model_validate(kwargs)
    conditions = _filters(data)

    with SessionLocal() as db:
        total = int(
            db.scalar(select(func.count(Employee.id)).where(*conditions)) or 0
        )

        if data.group_by in _MASTER_DIMENSIONS:
            model, employee_fk = _MASTER_DIMENSIONS[data.group_by]
            statement = (
                select(
                    model.id.label("id"),
                    model.code.label("code"),
                    model.name.label("name"),
                    func.count(Employee.id).label("count"),
                )
                .join(Employee, employee_fk == model.id)
                .where(model.deleted_at.is_(None), *conditions)
                .group_by(model.id, model.code, model.name)
                .order_by(model.name)
            )
            groups = [dict(row._mapping) for row in db.execute(statement)]
        else:
            column = getattr(Employee, data.group_by)
            statement = (
                select(column.label("value"), func.count(Employee.id).label("count"))
                .where(*conditions)
                .group_by(column)
                .order_by(column)
            )
            groups = [dict(row._mapping) for row in db.execute(statement)]

    return {
        "group_by": data.group_by,
        "total_employees": total,
        "groups": groups,
        "filters": data.model_dump(exclude_none=True, exclude={"group_by"}),
    }


EMPLOYEE_ANALYTICS_TOOL = StructuredTool.from_function(
    func=get_employee_analytics_report,
    name="get_employee_analytics_report",
    description=(
        "Admin-only read-only employee headcount report grouped by department, "
        "division, designation, location, employment status, or employment type. "
        "It never reads or returns employee PII."
    ),
    args_schema=EmployeeReportInput,
)


def get_admin_tools(user_role: str) -> list[StructuredTool]:
    """Expose employee analytics only to an authenticated administrator."""
    if user_role.strip().lower() != "admin":
        return []
    return [EMPLOYEE_ANALYTICS_TOOL]
