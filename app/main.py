from datetime import datetime, timezone

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth_api import router as auth_router
from app.database import get_db
from app.dependencies import require_roles
from app.employee_api import router as employee_router
from app.models.department import Department
from app.models.designation import Designation
from app.models.division import Division
from app.models.employee import Employee
from app.models.location import Location
from app.models.office_address import OfficeAddress
from app.schemas.department import DepartmentCreate, DepartmentRead, DepartmentUpdate
from app.schemas.designation import DesignationCreate, DesignationRead, DesignationUpdate
from app.schemas.division import DivisionCreate, DivisionRead, DivisionUpdate
from app.schemas.location import LocationCreate, LocationRead, LocationUpdate
from app.schemas.office_address import OfficeAddressCreate, OfficeAddressRead, OfficeAddressUpdate
from app.user_api import router as user_router


app = FastAPI(title="HRMS API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
masters = APIRouter(tags=["Masters"], dependencies=[Depends(require_roles("admin", "employee", "query"))])


def commit(db: Session, item, conflict_message: str):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, conflict_message) from None
    db.refresh(item)
    return item


def require_location(db: Session, location_id: int):
    if db.get(Location, location_id) is None:
        raise HTTPException(404, "Location not found")


def require_unreferenced(db: Session, model, field, item_id: int, message: str):
    if db.scalar(select(model.id).where(field == item_id).limit(1)) is not None:
        raise HTTPException(409, message)


def soft_delete(db: Session, item):
    item.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()


@app.get("/")
def home():
    return {"message": "HRMS API is running"}


@masters.post("/divisions", response_model=DivisionRead, status_code=201, dependencies=[Depends(require_roles("admin"))])
def create_division(data: DivisionCreate, db: Session = Depends(get_db)):
    item = Division(**data.model_dump())
    db.add(item)
    return commit(db, item, "Division code or name already exists")


@masters.get("/divisions", response_model=list[DivisionRead])
def get_divisions(db: Session = Depends(get_db)):
    return db.scalars(select(Division).order_by(Division.id)).all()


@masters.get("/divisions/{division_id}", response_model=DivisionRead)
def get_division(division_id: int, db: Session = Depends(get_db)):
    item = db.get(Division, division_id)
    if item is None:
        raise HTTPException(404, "Division not found")
    return item


@masters.patch("/divisions/{division_id}", response_model=DivisionRead, dependencies=[Depends(require_roles("admin"))])
def update_division(division_id: int, data: DivisionUpdate, db: Session = Depends(get_db)):
    item = db.get(Division, division_id)
    if item is None:
        raise HTTPException(404, "Division not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    return commit(db, item, "Division code or name already exists")


@masters.delete("/divisions/{division_id}", status_code=204, dependencies=[Depends(require_roles("admin"))])
def delete_division(division_id: int, db: Session = Depends(get_db)):
    item = db.get(Division, division_id)
    if item is None:
        raise HTTPException(404, "Division not found")
    require_unreferenced(db, Employee, Employee.division_id, division_id, "Division is assigned to an employee")
    soft_delete(db, item)


@masters.post("/departments", response_model=DepartmentRead, status_code=201, dependencies=[Depends(require_roles("admin"))])
def create_department(data: DepartmentCreate, db: Session = Depends(get_db)):
    item = Department(**data.model_dump())
    db.add(item)
    return commit(db, item, "Department code or name already exists")


@masters.get("/departments", response_model=list[DepartmentRead])
def get_departments(db: Session = Depends(get_db)):
    return db.scalars(select(Department).order_by(Department.id)).all()


@masters.get("/departments/{department_id}", response_model=DepartmentRead)
def get_department(department_id: int, db: Session = Depends(get_db)):
    item = db.get(Department, department_id)
    if item is None:
        raise HTTPException(404, "Department not found")
    return item


@masters.patch("/departments/{department_id}", response_model=DepartmentRead, dependencies=[Depends(require_roles("admin"))])
def update_department(department_id: int, data: DepartmentUpdate, db: Session = Depends(get_db)):
    item = db.get(Department, department_id)
    if item is None:
        raise HTTPException(404, "Department not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    return commit(db, item, "Department code or name already exists")


@masters.delete("/departments/{department_id}", status_code=204, dependencies=[Depends(require_roles("admin"))])
def delete_department(department_id: int, db: Session = Depends(get_db)):
    item = db.get(Department, department_id)
    if item is None:
        raise HTTPException(404, "Department not found")
    require_unreferenced(db, Employee, Employee.department_id, department_id, "Department is assigned to an employee")
    soft_delete(db, item)


@masters.post("/designations", response_model=DesignationRead, status_code=201, dependencies=[Depends(require_roles("admin"))])
def create_designation(data: DesignationCreate, db: Session = Depends(get_db)):
    item = Designation(**data.model_dump())
    db.add(item)
    return commit(db, item, "Designation code or name already exists")


@masters.get("/designations", response_model=list[DesignationRead])
def get_designations(db: Session = Depends(get_db)):
    return db.scalars(select(Designation).order_by(Designation.id)).all()


@masters.get("/designations/{designation_id}", response_model=DesignationRead)
def get_designation(designation_id: int, db: Session = Depends(get_db)):
    item = db.get(Designation, designation_id)
    if item is None:
        raise HTTPException(404, "Designation not found")
    return item


@masters.patch("/designations/{designation_id}", response_model=DesignationRead, dependencies=[Depends(require_roles("admin"))])
def update_designation(designation_id: int, data: DesignationUpdate, db: Session = Depends(get_db)):
    item = db.get(Designation, designation_id)
    if item is None:
        raise HTTPException(404, "Designation not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    return commit(db, item, "Designation code or name already exists")


@masters.delete("/designations/{designation_id}", status_code=204, dependencies=[Depends(require_roles("admin"))])
def delete_designation(designation_id: int, db: Session = Depends(get_db)):
    item = db.get(Designation, designation_id)
    if item is None:
        raise HTTPException(404, "Designation not found")
    require_unreferenced(db, Employee, Employee.designation_id, designation_id, "Designation is assigned to an employee")
    soft_delete(db, item)


@masters.post("/locations", response_model=LocationRead, status_code=201, dependencies=[Depends(require_roles("admin"))])
def create_location(data: LocationCreate, db: Session = Depends(get_db)):
    item = Location(**data.model_dump())
    db.add(item)
    return commit(db, item, "Location code or name already exists")


@masters.get("/locations", response_model=list[LocationRead])
def get_locations(db: Session = Depends(get_db)):
    return db.scalars(select(Location).order_by(Location.id)).all()


@masters.get("/locations/{location_id}", response_model=LocationRead)
def get_location(location_id: int, db: Session = Depends(get_db)):
    item = db.get(Location, location_id)
    if item is None:
        raise HTTPException(404, "Location not found")
    return item


@masters.patch("/locations/{location_id}", response_model=LocationRead, dependencies=[Depends(require_roles("admin"))])
def update_location(location_id: int, data: LocationUpdate, db: Session = Depends(get_db)):
    item = db.get(Location, location_id)
    if item is None:
        raise HTTPException(404, "Location not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    return commit(db, item, "Location code or name already exists")


@masters.delete("/locations/{location_id}", status_code=204, dependencies=[Depends(require_roles("admin"))])
def delete_location(location_id: int, db: Session = Depends(get_db)):
    item = db.get(Location, location_id)
    if item is None:
        raise HTTPException(404, "Location not found")
    require_unreferenced(db, Employee, Employee.location_id, location_id, "Location is assigned to an employee")
    require_unreferenced(db, OfficeAddress, OfficeAddress.location_id, location_id, "Location has an office address")
    soft_delete(db, item)


@masters.post("/office-addresses", response_model=OfficeAddressRead, status_code=201, dependencies=[Depends(require_roles("admin"))])
def create_office_address(data: OfficeAddressCreate, db: Session = Depends(get_db)):
    require_location(db, data.location_id)
    item = OfficeAddress(**data.model_dump())
    db.add(item)
    return commit(db, item, "Office address could not be created")


@masters.get("/office-addresses", response_model=list[OfficeAddressRead])
def get_office_addresses(db: Session = Depends(get_db)):
    return db.scalars(select(OfficeAddress).order_by(OfficeAddress.id)).all()


@masters.get("/office-addresses/{office_address_id}", response_model=OfficeAddressRead)
def get_office_address(office_address_id: int, db: Session = Depends(get_db)):
    item = db.get(OfficeAddress, office_address_id)
    if item is None:
        raise HTTPException(404, "Office address not found")
    return item


@masters.patch("/office-addresses/{office_address_id}", response_model=OfficeAddressRead, dependencies=[Depends(require_roles("admin"))])
def update_office_address(office_address_id: int, data: OfficeAddressUpdate, db: Session = Depends(get_db)):
    item = db.get(OfficeAddress, office_address_id)
    if item is None:
        raise HTTPException(404, "Office address not found")
    update_data = data.model_dump(exclude_unset=True)
    if "location_id" in update_data:
        require_location(db, update_data["location_id"])
    for field, value in update_data.items():
        setattr(item, field, value)
    return commit(db, item, "Office address could not be updated")


@masters.delete("/office-addresses/{office_address_id}", status_code=204, dependencies=[Depends(require_roles("admin"))])
def delete_office_address(office_address_id: int, db: Session = Depends(get_db)):
    item = db.get(OfficeAddress, office_address_id)
    if item is None:
        raise HTTPException(404, "Office address not found")
    require_unreferenced(db, Employee, Employee.office_address_id, office_address_id, "Office address is assigned to an employee")
    soft_delete(db, item)


app.include_router(masters)
app.include_router(user_router)
app.include_router(employee_router)
app.include_router(auth_router)
