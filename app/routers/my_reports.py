from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from app.models.database import get_db, Evaluation, EvaluationCycle, EvaluationStatus
from app.services.auth import get_current_user_from_cookie
from app.services.reports import aggregate_report_data
from app.services.pdf import generate_report_from_data
from app.templates_config import make_templates

# Collaborators see only their own reports, for any cycle in which they received a submitted evaluation
router = APIRouter(prefix="/my-reports")
templates = make_templates()


def _my_cycles(db: Session, user_id: int):
    return (
        db.query(EvaluationCycle)
        .join(Evaluation, Evaluation.cycle_id == EvaluationCycle.id)
        .filter(
            Evaluation.evaluatee_id == user_id,
            Evaluation.status == EvaluationStatus.submitted,
        )
        .distinct()
        .order_by(EvaluationCycle.created_at.desc())
        .all()
    )


def _get_my_report(db: Session, user, cycle_id: int):
    if cycle_id not in {c.id for c in _my_cycles(db, user.id)}:
        raise HTTPException(404)
    return aggregate_report_data(db, user.id, cycle_id)


@router.get("", response_class=HTMLResponse)
async def my_reports(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    reports = []
    for cycle in _my_cycles(db, user.id):
        data = aggregate_report_data(db, user.id, cycle.id)
        reports.append({
            "cycle": cycle,
            "summary": data["summary"],
            "benchmark": data["position_benchmark"],
        })

    return templates.TemplateResponse("my_reports.html", {
        "request": request,
        "current_user": user,
        "reports": reports,
    })


@router.get("/{cycle_id}", response_class=HTMLResponse)
async def my_report_detail(cycle_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    data = _get_my_report(db, user, cycle_id)

    return templates.TemplateResponse("admin/report_detail.html", {
        "request": request,
        "current_user": user,
        "data": data,
        "cycle_id": cycle_id,
        "user_id": user.id,
        "self_view": True,
    })


@router.get("/{cycle_id}/pdf")
async def my_report_pdf(cycle_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    data = _get_my_report(db, user, cycle_id)

    return Response(
        content=generate_report_from_data(data),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="AVD_{user.name.replace(" ", "_")}_{cycle_id}.pdf"'
        },
    )
