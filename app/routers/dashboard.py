from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from app.templates_config import make_templates
from sqlalchemy.orm import Session

from app.models.database import get_db, User, EvaluationCycle, Evaluation, EvaluationStatus, CycleStatus, UserRole
from app.services.auth import get_current_user_from_cookie
from app.services.reports import get_cycle_progress, get_user_cycle_progress

router = APIRouter()
templates = make_templates()


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    if user.role == UserRole.admin:
        return await admin_dashboard(request, db, user)
    else:
        return await collaborator_dashboard(request, db, user)


async def admin_dashboard(request: Request, db: Session, user: User):
    total_users = db.query(User).filter(User.is_active == True).count()
    total_cycles = db.query(EvaluationCycle).count()
    active_cycle = db.query(EvaluationCycle).filter(
        EvaluationCycle.status == CycleStatus.active
    ).first()

    cycle_stats = None
    if active_cycle:
        cycle_stats = get_cycle_progress(db, active_cycle.id)

    recent_cycles = db.query(EvaluationCycle).order_by(
        EvaluationCycle.created_at.desc()
    ).limit(5).all()

    users_pending = []
    if active_cycle:
        for u in db.query(User).filter(User.is_active == True).all():
            prog = get_user_cycle_progress(db, u.id, active_cycle.id)
            if prog["pending"] > 0:
                users_pending.append({"user": u, "progress": prog})

    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request,
        "current_user": user,
        "total_users": total_users,
        "total_cycles": total_cycles,
        "active_cycle": active_cycle,
        "cycle_stats": cycle_stats,
        "recent_cycles": recent_cycles,
        "users_pending": users_pending[:10],
    })


async def collaborator_dashboard(request: Request, db: Session, user: User):
    active_cycle = db.query(EvaluationCycle).filter(
        EvaluationCycle.status == CycleStatus.active
    ).first()

    my_evaluations = []
    progress = {"total": 0, "submitted": 0, "pending": 0, "pct": 0}

    if active_cycle:
        my_evaluations = db.query(Evaluation).filter(
            Evaluation.cycle_id == active_cycle.id,
            Evaluation.evaluator_id == user.id,
        ).all()
        progress = get_user_cycle_progress(db, user.id, active_cycle.id)

    return templates.TemplateResponse("admin/collaborator_dashboard.html", {
        "request": request,
        "current_user": user,
        "active_cycle": active_cycle,
        "my_evaluations": my_evaluations,
        "progress": progress,
    })
