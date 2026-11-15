"""Employee expense claims with a direct-manager L1 and administrator L2 workflow."""

from datetime import datetime, timezone
from decimal import Decimal
import json

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.audit import record_audit_event
from app.database import get_db
from app.dependencies import get_current_user, require_roles
from app.encryption import get_employee_key_ring
from app.models import Employee, ExpenseClaim, ExpenseClaimApproval, ExpenseEntry
from app.models.role import Role
from app.models.user import User
from app.schemas.expense import ExpenseClaimCreate, ExpenseClaimRead, ExpenseClaimUpdate, ExpenseDecision


router = APIRouter(prefix="/expenses", tags=["Expenses"])
MAX_EXPENSE_ENTRIES = 5


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _role_name(db: Session, user: User) -> str:
    role = db.get(Role, user.role_id)
    return role.name if role is not None else ""


def _linked_employee_or_403(db: Session, user: User) -> Employee:
    if user.employee_id is None:
        raise HTTPException(403, "Your account is not linked to an employee record")
    employee = db.get(Employee, user.employee_id)
    if employee is None or employee.deleted_at is not None or employee.employment_status == "exited":
        raise HTTPException(403, "Your linked employee record is not active")
    return employee


def _claim_or_404(db: Session, claim_id: int) -> ExpenseClaim:
    claim = db.get(ExpenseClaim, claim_id)
    if claim is None:
        raise HTTPException(404, "Expense claim not found")
    return claim


def _entries(db: Session, claim_id: int) -> list[ExpenseEntry]:
    return db.scalars(select(ExpenseEntry).where(ExpenseEntry.claim_id == claim_id).order_by(ExpenseEntry.id)).all()


def _approvals(db: Session, claim_id: int) -> list[ExpenseClaimApproval]:
    return db.scalars(
        select(ExpenseClaimApproval)
        .where(ExpenseClaimApproval.claim_id == claim_id)
        .order_by(ExpenseClaimApproval.approval_level)
    ).all()


def _read_entry(entry: ExpenseEntry, ring) -> dict:
    try:
        receipt_image = ring.decrypt(json.loads(entry.receipt_data)) if entry.receipt_data else None
    except (KeyError, TypeError, ValueError):
        raise HTTPException(503, "Receipt data could not be decrypted with the configured keys") from None
    return {
        "id": entry.id,
        "expense_date": entry.expense_date,
        "category": entry.category,
        "description": entry.description,
        "requested_amount": entry.requested_amount,
        "approved_amount": entry.approved_amount,
        "receipt_image": receipt_image,
    }


def _read_claim(db: Session, claim: ExpenseClaim, ring) -> dict:
    entries = _entries(db, claim.id)
    return {
        "id": claim.id,
        "claimant_employee_id": claim.claimant_employee_id,
        "cost_center": claim.cost_center,
        "currency": claim.currency,
        "status": claim.status,
        "requested_total": sum((entry.requested_amount for entry in entries), Decimal("0.00")),
        "l1_approved_total": claim.l1_approved_total,
        "l2_approved_total": claim.l2_approved_total,
        "entries": [_read_entry(entry, ring) for entry in entries],
        "approvals": _approvals(db, claim.id),
        "created_at": claim.created_at,
        "updated_at": claim.updated_at,
    }


def _can_view_claim(db: Session, user: User, claim: ExpenseClaim) -> bool:
    role = _role_name(db, user)
    if user.employee_id is None:
        return False
    if user.employee_id == claim.claimant_employee_id:
        return True
    if claim.status == "draft":
        return False
    if role == "admin":
        return True
    claimant = db.get(Employee, claim.claimant_employee_id)
    return role == "employee" and claimant is not None and claimant.reporting_manager_id == user.employee_id


def _replace_entries(db: Session, claim: ExpenseClaim, data: ExpenseClaimCreate | ExpenseClaimUpdate, ring) -> None:
    entries = list(data.entries)
    if not 1 <= len(entries) <= MAX_EXPENSE_ENTRIES:
        raise HTTPException(422, f"A claim must contain between 1 and {MAX_EXPENSE_ENTRIES} expense entries")
    for entry in _entries(db, claim.id):
        db.delete(entry)
    db.flush()
    for entry in entries:
        db.add(
            ExpenseEntry(
                claim_id=claim.id,
                expense_date=entry.expense_date,
                category=entry.category,
                description=entry.description,
                requested_amount=entry.requested_amount,
                approved_amount=None,
                receipt_data=json.dumps(ring.encrypt(entry.receipt_image)) if entry.receipt_image else None,
            )
        )


@router.get("/claims", response_model=list[ExpenseClaimRead])
def list_expense_claims(
    db: Session = Depends(get_db),
    ring=Depends(get_employee_key_ring),
    current_user: User = Depends(get_current_user),
):
    role = _role_name(db, current_user)
    statement = select(ExpenseClaim).order_by(ExpenseClaim.updated_at.desc(), ExpenseClaim.id.desc())
    if role == "admin":
        claims = db.scalars(statement.where(ExpenseClaim.status != "draft")).all()
    else:
        manager = _linked_employee_or_403(db, current_user)
        claims = db.scalars(
            statement.where(
                or_(
                    ExpenseClaim.claimant_employee_id == manager.id,
                    and_(
                        ExpenseClaim.status != "draft",
                        ExpenseClaim.claimant_employee_id.in_(
                            select(Employee.id).where(Employee.reporting_manager_id == manager.id)
                        ),
                    ),
                )
            )
        ).all()
    return [_read_claim(db, claim, ring) for claim in claims]


@router.get("/claims/{claim_id}", response_model=ExpenseClaimRead)
def get_expense_claim(
    claim_id: int,
    db: Session = Depends(get_db),
    ring=Depends(get_employee_key_ring),
    current_user: User = Depends(get_current_user),
):
    claim = _claim_or_404(db, claim_id)
    if not _can_view_claim(db, current_user, claim):
        raise HTTPException(404, "Expense claim not found")
    return _read_claim(db, claim, ring)


@router.post("/claims", response_model=ExpenseClaimRead, status_code=201)
def create_expense_claim(
    data: ExpenseClaimCreate,
    db: Session = Depends(get_db),
    ring=Depends(get_employee_key_ring),
    current_user: User = Depends(require_roles("employee")),
):
    claimant = _linked_employee_or_403(db, current_user)
    now = _now()
    claim = ExpenseClaim(
        claimant_employee_id=claimant.id,
        cost_center=data.cost_center,
        currency=data.currency,
        status="draft",
        created_at=now,
        updated_at=now,
    )
    db.add(claim)
    db.flush()
    _replace_entries(db, claim, data, ring)
    db.commit()
    record_audit_event(db, event_type="expense.claim.created", actor_user_id=current_user.id, details={"claim_id": claim.id, "entry_count": len(data.entries)})
    db.commit()
    return _read_claim(db, claim, ring)


@router.patch("/claims/{claim_id}", response_model=ExpenseClaimRead)
def update_expense_claim(
    claim_id: int,
    data: ExpenseClaimUpdate,
    db: Session = Depends(get_db),
    ring=Depends(get_employee_key_ring),
    current_user: User = Depends(require_roles("employee")),
):
    claimant = _linked_employee_or_403(db, current_user)
    claim = _claim_or_404(db, claim_id)
    if claim.claimant_employee_id != claimant.id:
        raise HTTPException(404, "Expense claim not found")
    if claim.status != "draft":
        raise HTTPException(409, "Only draft expense claims can be edited")
    claim.cost_center = data.cost_center
    claim.currency = data.currency
    claim.updated_at = _now()
    _replace_entries(db, claim, data, ring)
    db.commit()
    record_audit_event(db, event_type="expense.claim.updated", actor_user_id=current_user.id, details={"claim_id": claim.id, "entry_count": len(data.entries)})
    db.commit()
    return _read_claim(db, claim, ring)


@router.delete("/claims/{claim_id}", status_code=204)
def delete_expense_claim(
    claim_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("employee")),
):
    claimant = _linked_employee_or_403(db, current_user)
    claim = _claim_or_404(db, claim_id)
    if claim.claimant_employee_id != claimant.id:
        raise HTTPException(404, "Expense claim not found")
    if claim.status != "draft":
        raise HTTPException(409, "Only draft expense claims can be deleted")
    for entry in _entries(db, claim.id):
        db.delete(entry)
    db.delete(claim)
    db.commit()
    record_audit_event(db, event_type="expense.claim.deleted", actor_user_id=current_user.id, details={"claim_id": claim_id})
    db.commit()
    return Response(status_code=204)


@router.post("/claims/{claim_id}/submit", response_model=ExpenseClaimRead)
def submit_expense_claim(
    claim_id: int,
    db: Session = Depends(get_db),
    ring=Depends(get_employee_key_ring),
    current_user: User = Depends(require_roles("employee")),
):
    claimant = _linked_employee_or_403(db, current_user)
    claim = _claim_or_404(db, claim_id)
    if claim.claimant_employee_id != claimant.id:
        raise HTTPException(404, "Expense claim not found")
    if claim.status != "draft":
        raise HTTPException(409, "Only draft expense claims can be submitted")
    if claimant.reporting_manager_id is None:
        raise HTTPException(422, "Assign a reporting manager before submitting an expense claim")
    claim.status = "submitted"
    claim.updated_at = _now()
    db.commit()
    record_audit_event(db, event_type="expense.claim.submitted", actor_user_id=current_user.id, details={"claim_id": claim.id})
    db.commit()
    return _read_claim(db, claim, ring)


def _apply_decision_entries(entries: list[ExpenseEntry], decision: ExpenseDecision) -> Decimal:
    if decision.action == "rejected":
        for entry in entries:
            entry.approved_amount = Decimal("0.00")
        return Decimal("0.00")
    amounts = decision.approved_amounts
    if amounts is None:
        amounts = [entry.requested_amount for entry in entries]
    if len(amounts) != len(entries):
        raise HTTPException(422, "Provide one approved amount for each expense entry")
    for entry, amount in zip(entries, amounts, strict=True):
        if amount > entry.requested_amount:
            raise HTTPException(422, "An approved amount cannot exceed the requested amount")
        entry.approved_amount = amount
    return sum(amounts, Decimal("0.00"))


@router.post("/claims/{claim_id}/l1-decision", response_model=ExpenseClaimRead)
def l1_decision(
    claim_id: int,
    decision: ExpenseDecision,
    db: Session = Depends(get_db),
    ring=Depends(get_employee_key_ring),
    current_user: User = Depends(require_roles("employee")),
):
    manager = _linked_employee_or_403(db, current_user)
    claim = _claim_or_404(db, claim_id)
    claimant = db.get(Employee, claim.claimant_employee_id)
    if claimant is None or claimant.reporting_manager_id != manager.id:
        raise HTTPException(404, "Expense claim awaiting your approval was not found")
    if claim.status != "submitted":
        raise HTTPException(409, "This claim is not awaiting L1 approval")
    approved_total = _apply_decision_entries(_entries(db, claim.id), decision)
    claim.l1_approved_total = approved_total
    claim.status = "l1_approved" if decision.action == "approved" else "l1_rejected"
    claim.updated_at = _now()
    db.add(ExpenseClaimApproval(claim_id=claim.id, approval_level=1, action=decision.action, approver_user_id=current_user.id, remarks=decision.remarks, approved_total=approved_total, decided_at=claim.updated_at))
    db.commit()
    record_audit_event(db, event_type="expense.claim.l1_decided", actor_user_id=current_user.id, details={"claim_id": claim.id, "action": decision.action})
    db.commit()
    return _read_claim(db, claim, ring)


@router.post("/claims/{claim_id}/l2-decision", response_model=ExpenseClaimRead)
def l2_decision(
    claim_id: int,
    decision: ExpenseDecision,
    db: Session = Depends(get_db),
    ring=Depends(get_employee_key_ring),
    current_user: User = Depends(require_roles("admin")),
):
    claim = _claim_or_404(db, claim_id)
    if current_user.employee_id == claim.claimant_employee_id:
        raise HTTPException(403, "You cannot approve your own expense claim")
    if claim.status != "l1_approved":
        raise HTTPException(409, "This claim is not awaiting L2 approval")
    approved_total = _apply_decision_entries(_entries(db, claim.id), decision)
    claim.l2_approved_total = approved_total
    claim.status = "l2_approved" if decision.action == "approved" else "l2_rejected"
    claim.updated_at = _now()
    db.add(ExpenseClaimApproval(claim_id=claim.id, approval_level=2, action=decision.action, approver_user_id=current_user.id, remarks=decision.remarks, approved_total=approved_total, decided_at=claim.updated_at))
    db.commit()
    record_audit_event(db, event_type="expense.claim.l2_decided", actor_user_id=current_user.id, details={"claim_id": claim.id, "action": decision.action})
    db.commit()
    return _read_claim(db, claim, ring)


@router.post("/claims/{claim_id}/reimburse", response_model=ExpenseClaimRead)
def mark_expense_claim_reimbursed(
    claim_id: int,
    db: Session = Depends(get_db),
    ring=Depends(get_employee_key_ring),
    current_user: User = Depends(require_roles("admin")),
):
    claim = _claim_or_404(db, claim_id)
    if claim.status != "l2_approved":
        raise HTTPException(409, "Only L2-approved claims can be marked reimbursed")
    claim.status = "reimbursed"
    claim.updated_at = _now()
    db.commit()
    record_audit_event(db, event_type="expense.claim.reimbursed", actor_user_id=current_user.id, details={"claim_id": claim.id})
    db.commit()
    return _read_claim(db, claim, ring)
