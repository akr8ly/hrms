"""Private query applications for query users and read-only admin review."""

from datetime import datetime, timezone
from io import BytesIO
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.audit import record_audit_event
from app.database import get_db
from app.dependencies import require_roles
from app.models.query_request import QueryRequest
from app.models.user import User
from app.schemas.query_request import AdminQueryRequestRead, QueryRequestCreate, QueryRequestRead


router = APIRouter(prefix="/queries", tags=["Queries"])

QUERY_CATEGORY_LABELS = {
    "employee_related": "Employee related",
    "application_usage": "Application usage",
    "reimbursement_report": "Reimbursement report",
    "llm_calls": "HR assistant / LLM",
}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _admin_rows(db: Session):
    return db.execute(
        select(QueryRequest, User.username)
        .join(User, User.id == QueryRequest.requester_user_id)
        .order_by(QueryRequest.updated_at.desc(), QueryRequest.id.desc())
    ).all()


def _admin_row(db: Session, query_id: int):
    row = db.execute(
        select(QueryRequest, User.username)
        .join(User, User.id == QueryRequest.requester_user_id)
        .where(QueryRequest.id == query_id)
    ).first()
    if row is None:
        raise HTTPException(404, "Query request was not found")
    return row


def _admin_read(request: QueryRequest, sender: str) -> dict:
    return {
        "id": request.id,
        "category": request.category,
        "subject": request.subject,
        "description": request.description,
        "related_reference": request.related_reference,
        "status": request.status,
        "created_at": request.created_at,
        "updated_at": request.updated_at,
        "sender": sender,
    }


def _pdf_text(value: object) -> str:
    return escape(str(value)).replace("\n", "<br/>")


def build_query_report(rows, generated_at: datetime | None = None) -> bytes:
    """Build a printable, read-only PDF report for the admin query queue."""
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="HRMS Query Report",
        author="HRMS",
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle("QueryReportTitle", parent=styles["Title"], textColor=colors.HexColor("#172554"), fontSize=19, leading=23, spaceAfter=4)
    subtitle = ParagraphStyle("QueryReportSubtitle", parent=styles["Normal"], textColor=colors.HexColor("#64748b"), fontSize=9, leading=13, spaceAfter=15)
    heading = ParagraphStyle("QueryReportHeading", parent=styles["Heading3"], textColor=colors.HexColor("#1e3a5f"), fontSize=11, leading=14, spaceAfter=7)
    label = ParagraphStyle("QueryReportLabel", parent=styles["Normal"], textColor=colors.HexColor("#64748b"), fontSize=8, leading=10)
    value = ParagraphStyle("QueryReportValue", parent=styles["Normal"], textColor=colors.HexColor("#0f172a"), fontSize=9, leading=12)
    description = ParagraphStyle("QueryReportDescription", parent=value, leading=14)
    generated = generated_at or _now()
    story = [
        Paragraph("HRMS Query Report", title),
        Paragraph(f"Generated {generated.strftime('%d %b %Y, %I:%M %p UTC')} | {len(rows)} request{'s' if len(rows) != 1 else ''}", subtitle),
    ]
    if not rows:
        story.append(Paragraph("No query requests were available when this report was generated.", value))
    for request, sender in rows:
        fields = [
            [Paragraph("Subject", label), Paragraph(_pdf_text(request.subject), value)],
            [Paragraph("Sender", label), Paragraph(_pdf_text(sender), value)],
            [Paragraph("Query", label), Paragraph(_pdf_text(QUERY_CATEGORY_LABELS.get(request.category, request.category)), value)],
            [Paragraph("Reference", label), Paragraph(_pdf_text(request.related_reference or "-"), value)],
            [Paragraph("Date", label), Paragraph(request.created_at.strftime("%d %b %Y"), value)],
            [Paragraph("Timestamp", label), Paragraph(request.created_at.strftime("%I:%M %p UTC"), value)],
        ]
        metadata = Table(fields, colWidths=[31 * mm, 127 * mm], hAlign="LEFT")
        metadata.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#dbe3ee")),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(KeepTogether([
            Paragraph(f"Query {request.id}", heading),
            metadata,
            Spacer(1, 7),
            Paragraph("Description", label),
        ]))
        story.extend([Paragraph(_pdf_text(request.description), description), Spacer(1, 15)])
    document.build(story)
    return buffer.getvalue()


@router.get("/requests", response_model=list[QueryRequestRead])
def list_my_query_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("query")),
):
    """Return only requests created by the signed-in query user."""
    return db.scalars(
        select(QueryRequest)
        .where(QueryRequest.requester_user_id == current_user.id)
        .order_by(QueryRequest.updated_at.desc(), QueryRequest.id.desc())
    ).all()


@router.post("/requests", response_model=QueryRequestRead, status_code=201)
def create_query_request(
    data: QueryRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("query")),
):
    """Submit a structured request without exposing employee data or raw LLM logs."""
    now = _now()
    request = QueryRequest(
        requester_user_id=current_user.id,
        category=data.category,
        subject=data.subject,
        description=data.description,
        related_reference=data.related_reference,
        status="submitted",
        created_at=now,
        updated_at=now,
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    record_audit_event(
        db,
        event_type="query.request.created",
        actor_user_id=current_user.id,
        details={"query_request_id": request.id, "category": request.category},
    )
    db.commit()
    return request


@router.get("/admin/requests", response_model=list[AdminQueryRequestRead])
def list_admin_query_requests(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_roles("admin")),
):
    """Review every query without changing the original user-submitted content."""
    return [_admin_read(request, sender) for request, sender in _admin_rows(db)]


@router.get("/admin/report.pdf", response_class=Response)
def download_admin_query_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    """Download a PDF report containing immutable query details for admin review."""
    report = build_query_report(_admin_rows(db))
    record_audit_event(
        db,
        event_type="query.report.downloaded",
        actor_user_id=current_user.id,
        details={"format": "pdf"},
    )
    db.commit()
    filename = f"hrms-query-report-{_now().strftime('%Y%m%d-%H%M%S')}.pdf"
    return Response(
        content=report,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/admin/requests/{query_id}/report.pdf", response_class=Response)
def download_single_query_report(
    query_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    """Download one immutable query request as a PDF report."""
    row = _admin_row(db, query_id)
    report = build_query_report([row])
    record_audit_event(
        db,
        event_type="query.report.downloaded",
        actor_user_id=current_user.id,
        details={"format": "pdf", "query_request_id": query_id},
    )
    db.commit()
    filename = f"hrms-query-{query_id}-{_now().strftime('%Y%m%d-%H%M%S')}.pdf"
    return Response(
        content=report,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
