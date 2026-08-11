from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from app.templates_config import make_templates
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
import asyncio
import csv
import io

from app.models.database import (
    get_db, User, EvaluationCycle, CycleStatus, Evaluation,
    EvaluationAssignment, EvaluationStatus, UserRole, DEPARTMENTS
)
from app.services.auth import require_admin, get_current_user_from_cookie
from app.services.reports import get_cycle_progress
from app.services.email import notify_cycle_opened

router = APIRouter(prefix="/cycles")
templates = make_templates()


def auto_assign_evaluations(db: Session, cycle: EvaluationCycle):
    """
    Assignment logic:
    - Projetos dept (Consultor/Coordenador): manual only — skip auto
    - All other depts: everyone evaluates everyone in same dept
    - Self-evaluation: always created for everyone
    """
    users = db.query(User).filter(User.is_active == True).all()

    # Clear existing assignments
    db.query(EvaluationAssignment).filter(
        EvaluationAssignment.cycle_id == cycle.id
    ).delete()
    db.query(Evaluation).filter(Evaluation.cycle_id == cycle.id).delete()
    db.flush()

    created = set()

    def make_eval(evaluator_id, evaluatee_id, is_self=False):
        key = (evaluator_id, evaluatee_id)
        if key in created:
            return
        created.add(key)
        assign = EvaluationAssignment(
            cycle_id=cycle.id,
            evaluator_id=evaluator_id,
            evaluatee_id=evaluatee_id,
            is_self=is_self,
        )
        ev = Evaluation(
            cycle_id=cycle.id,
            evaluator_id=evaluator_id,
            evaluatee_id=evaluatee_id,
            is_self_evaluation=is_self,
            status=EvaluationStatus.pending,
        )
        db.add(assign)
        db.add(ev)

    # Self-evaluation for everyone
    for u in users:
        make_eval(u.id, u.id, is_self=True)

    # Dept-based cross-evaluation (skip Projetos — manual)
    by_dept = {}
    for u in users:
        if u.department and u.department != "Projetos":
            by_dept.setdefault(u.department, []).append(u)

    for dept, members in by_dept.items():
        for evaluator in members:
            for evaluatee in members:
                if evaluator.id != evaluatee.id:
                    make_eval(evaluator.id, evaluatee.id, is_self=False)

    db.commit()


@router.get("", response_class=HTMLResponse)
async def list_cycles(request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    cycles = db.query(EvaluationCycle).order_by(
        EvaluationCycle.created_at.desc()
    ).all()
    cycle_data = []
    for c in cycles:
        progress = get_cycle_progress(db, c.id)
        cycle_data.append({"cycle": c, "progress": progress})
    return templates.TemplateResponse("admin/cycles.html", {
        "request": request,
        "current_user": user,
        "cycle_data": cycle_data,
    })


@router.post("/create")
async def create_cycle(
    request: Request,
    name: str = Form(...),
    description: Optional[str] = Form(None),
    start_date: Optional[str] = Form(None),
    end_date: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    user = require_admin(request, db)

    def parse_date(s):
        if not s:
            return None
        try:
            return datetime.strptime(s, "%Y-%m-%d")
        except Exception:
            return None

    cycle = EvaluationCycle(
        name=name.strip(),
        description=description,
        status=CycleStatus.draft,
        start_date=parse_date(start_date),
        end_date=parse_date(end_date),
        created_by_id=user.id,
    )
    db.add(cycle)
    db.commit()
    return RedirectResponse(f"/cycles/{cycle.id}/assignments", status_code=302)


@router.get("/{cycle_id}/assignments", response_class=HTMLResponse)
async def manage_assignments(cycle_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    cycle = db.query(EvaluationCycle).get(cycle_id)
    if not cycle:
        raise HTTPException(404)

    users = db.query(User).filter(User.is_active == True).order_by(User.name).all()
    assignments = db.query(EvaluationAssignment).filter(
        EvaluationAssignment.cycle_id == cycle_id
    ).all()

    # Build matrix: evaluator -> set of evaluatee ids
    matrix = {}
    for a in assignments:
        matrix.setdefault(a.evaluator_id, set()).add(a.evaluatee_id)

    return templates.TemplateResponse("admin/assignments.html", {
        "request": request,
        "current_user": user,
        "cycle": cycle,
        "users": users,
        "matrix": matrix,
    })


@router.post("/{cycle_id}/assignments/auto")
async def auto_assign(cycle_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    cycle = db.query(EvaluationCycle).get(cycle_id)
    if not cycle:
        raise HTTPException(404)
    auto_assign_evaluations(db, cycle)
    return RedirectResponse(f"/cycles/{cycle_id}/assignments?msg=auto_assigned", status_code=302)


@router.post("/{cycle_id}/assignments/add")
async def add_assignment(
    cycle_id: int,
    request: Request,
    evaluator_id: int = Form(...),
    evaluatee_id: int = Form(...),
    db: Session = Depends(get_db),
):
    require_admin(request, db)
    cycle = db.query(EvaluationCycle).get(cycle_id)
    if not cycle:
        raise HTTPException(404)

    existing = db.query(EvaluationAssignment).filter(
        EvaluationAssignment.cycle_id == cycle_id,
        EvaluationAssignment.evaluator_id == evaluator_id,
        EvaluationAssignment.evaluatee_id == evaluatee_id,
    ).first()

    if not existing:
        is_self = evaluator_id == evaluatee_id
        assign = EvaluationAssignment(
            cycle_id=cycle_id,
            evaluator_id=evaluator_id,
            evaluatee_id=evaluatee_id,
            is_self=is_self,
        )
        ev = Evaluation(
            cycle_id=cycle_id,
            evaluator_id=evaluator_id,
            evaluatee_id=evaluatee_id,
            is_self_evaluation=is_self,
            status=EvaluationStatus.pending,
        )
        db.add(assign)
        db.add(ev)
        db.commit()

    return RedirectResponse(f"/cycles/{cycle_id}/assignments?msg=added", status_code=302)


@router.post("/{cycle_id}/assignments/remove")
async def remove_assignment(
    cycle_id: int,
    request: Request,
    evaluator_id: int = Form(...),
    evaluatee_id: int = Form(...),
    db: Session = Depends(get_db),
):
    require_admin(request, db)

    db.query(EvaluationAssignment).filter(
        EvaluationAssignment.cycle_id == cycle_id,
        EvaluationAssignment.evaluator_id == evaluator_id,
        EvaluationAssignment.evaluatee_id == evaluatee_id,
    ).delete()

    ev = db.query(Evaluation).filter(
        Evaluation.cycle_id == cycle_id,
        Evaluation.evaluator_id == evaluator_id,
        Evaluation.evaluatee_id == evaluatee_id,
        Evaluation.status == EvaluationStatus.pending,
    ).first()
    if ev:
        db.delete(ev)

    db.commit()
    return RedirectResponse(f"/cycles/{cycle_id}/assignments?msg=removed", status_code=302)


@router.post("/{cycle_id}/activate")
async def activate_cycle(cycle_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    cycle = db.query(EvaluationCycle).get(cycle_id)
    if not cycle:
        raise HTTPException(404)

    # Deactivate others
    db.query(EvaluationCycle).filter(
        EvaluationCycle.status == CycleStatus.active
    ).update({"status": CycleStatus.closed})

    cycle.status = CycleStatus.active
    cycle.reminder_sent = False
    db.commit()

    # Notify all users
    all_users = db.query(User).filter(User.is_active == True).all()
    end_date_str = cycle.end_date.strftime("%d/%m/%Y") if cycle.end_date else "—"
    asyncio.create_task(notify_cycle_opened(all_users, cycle.name, end_date_str))

    return RedirectResponse("/cycles?msg=activated", status_code=302)


@router.get("/{cycle_id}/export.csv")
async def export_cycle_csv(cycle_id: int, request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    cycle = db.query(EvaluationCycle).get(cycle_id)
    if not cycle:
        raise HTTPException(404)

    evaluations = db.query(Evaluation).filter(
        Evaluation.cycle_id == cycle_id,
        Evaluation.status == EvaluationStatus.submitted,
    ).all()

    buf = io.StringIO()
    buf.write("﻿")
    writer = csv.writer(buf)
    writer.writerow(["Avaliador", "Avaliado", "Competência", "Nota", "Comentário", "Enviado em"])
    for ev in evaluations:
        submitted = ev.submitted_at.strftime("%d/%m/%Y %H:%M") if ev.submitted_at else ""
        for a in ev.answers:
            writer.writerow([
                ev.evaluator.name, ev.evaluatee.name,
                a.competency.name if a.competency else "",
                a.score if a.score is not None else "",
                a.comment or "",
                submitted,
            ])

    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="avd360_ciclo_{cycle_id}.csv"'},
    )


@router.post("/{cycle_id}/close")
async def close_cycle(cycle_id: int, request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    cycle = db.query(EvaluationCycle).get(cycle_id)
    if cycle:
        cycle.status = CycleStatus.closed
        db.commit()
    return RedirectResponse("/cycles?msg=closed", status_code=302)


@router.post("/{cycle_id}/delete")
async def delete_cycle(cycle_id: int, request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    cycle = db.query(EvaluationCycle).get(cycle_id)
    if cycle:
        db.delete(cycle)
        db.commit()
    return RedirectResponse("/cycles?msg=deleted", status_code=302)
