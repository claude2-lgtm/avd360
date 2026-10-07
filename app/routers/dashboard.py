from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from app.templates_config import make_templates
from sqlalchemy.orm import Session
from datetime import datetime

from app.models.database import get_db, User, EvaluationCycle, Evaluation, EvaluationStatus, CycleStatus, UserRole
from app.services.auth import get_current_user_from_cookie
from app.services.reports import get_cycle_progress, get_user_cycle_progress, get_position_averages

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


MANAGER_POSITIONS = ["Coordenador de Projetos", "Diretor Comercial", "Diretor de Projetos",
                     "Diretor de Gestão", "Diretor de Gestao", "Presidente"]


def _pending_by_evaluator(db: Session, cycle_id: int):
    """Evaluations not yet submitted in the cycle, grouped by who still has to fill them in."""
    pending = (
        db.query(Evaluation)
        .filter(Evaluation.cycle_id == cycle_id, Evaluation.status != EvaluationStatus.submitted)
        .all()
    )
    groups = {}
    for ev in pending:
        g = groups.setdefault(ev.evaluator_id, {"evaluator": ev.evaluator, "pending": [], "in_progress": 0})
        if ev.is_self_evaluation:
            kind = "Autoavaliação"
        elif ev.evaluator.position in MANAGER_POSITIONS:
            kind = "Como superior"
        else:
            kind = "Como par"
        g["pending"].append({"evaluation": ev, "evaluatee": ev.evaluatee, "kind": kind,
                           "started": ev.status == EvaluationStatus.in_progress})
        g["in_progress"] += ev.status == EvaluationStatus.in_progress
    for g in groups.values():
        g["pending"].sort(key=lambda i: (i["kind"] != "Autoavaliação", i["evaluatee"].name))
        g["total"] = db.query(Evaluation).filter(
            Evaluation.cycle_id == cycle_id, Evaluation.evaluator_id == g["evaluator"].id
        ).count()
        g["done"] = g["total"] - len(g["pending"])
    return sorted(groups.values(), key=lambda g: (-len(g["pending"]), g["evaluator"].name))


async def admin_dashboard(request: Request, db: Session, user: User):
    total_users = db.query(User).filter(User.is_active == True).count()
    total_cycles = db.query(EvaluationCycle).count()
    active_cycle = db.query(EvaluationCycle).filter(
        EvaluationCycle.status == CycleStatus.active
    ).first()

    # Cycle used by the averages and pending panels: chosen in the page, else the active one,
    # else the most recent non-draft cycle
    cycles = (
        db.query(EvaluationCycle)
        .filter(EvaluationCycle.status != CycleStatus.draft)
        .order_by(EvaluationCycle.created_at.desc())
        .all()
    )
    selected_cycle = active_cycle or (cycles[0] if cycles else None)
    requested = request.query_params.get("cycle_id")
    if requested and requested.isdigit():
        selected_cycle = next((c for c in cycles if c.id == int(requested)), selected_cycle)

    cycle_stats = get_cycle_progress(db, selected_cycle.id) if selected_cycle else None

    position_averages, company_avg, pending_groups = [], None, []
    days_left = None
    if selected_cycle:
        position_averages = list(get_position_averages(db, selected_cycle.id).values())
        people = sum(a["count"] for a in position_averages)
        if people:
            company_avg = sum(a["avg"] * a["count"] for a in position_averages) / people
        pending_groups = _pending_by_evaluator(db, selected_cycle.id)
        if selected_cycle.end_date and selected_cycle.status == CycleStatus.active:
            days_left = (selected_cycle.end_date.date() - datetime.now().date()).days

    recent_cycles = db.query(EvaluationCycle).order_by(
        EvaluationCycle.created_at.desc()
    ).limit(5).all()

    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request,
        "current_user": user,
        "total_users": total_users,
        "total_cycles": total_cycles,
        "active_cycle": active_cycle,
        "cycles": cycles,
        "selected_cycle": selected_cycle,
        "cycle_stats": cycle_stats,
        "recent_cycles": recent_cycles,
        "position_averages": position_averages,
        "company_avg": company_avg,
        "pending_groups": pending_groups,
        "pending_total": sum(len(g["pending"]) for g in pending_groups),
        "pending_in_progress": sum(g["in_progress"] for g in pending_groups),
        "days_left": days_left,
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
