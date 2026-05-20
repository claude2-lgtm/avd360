from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from app.templates_config import make_templates
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
import json

from app.models.database import (
    get_db, Evaluation, EvaluationAnswer, EvaluationStatus,
    Competency, CompetencyGroup, User, EvaluationCycle, CycleStatus
)
from app.services.auth import get_current_user_from_cookie, require_admin
from app.services.reports import get_competencies_for_position, aggregate_report_data
from app.services.pdf import generate_individual_report

router = APIRouter(prefix="/evaluations")
templates = make_templates()


@router.get("/{eval_id}", response_class=HTMLResponse)
async def evaluation_form(eval_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    ev = db.query(Evaluation).get(eval_id)
    if not ev:
        raise HTTPException(404)

    # Only evaluator or admin can access
    if ev.evaluator_id != user.id and user.role.value != "admin":
        raise HTTPException(403)

    if ev.status == EvaluationStatus.submitted:
        return RedirectResponse(f"/evaluations/{eval_id}/view", status_code=302)

    # Mark in_progress
    if ev.status == EvaluationStatus.pending:
        ev.status = EvaluationStatus.in_progress
        db.commit()

    # Get competencies for evaluatee's position
    competencies = get_competencies_for_position(db, ev.evaluatee.position or "")

    # Get existing answers
    existing = {a.competency_id: a for a in ev.answers}

    # Group by group name
    groups = {}
    for comp in competencies:
        g = comp.group.name if comp.group else "Geral"
        groups.setdefault(g, []).append(comp)

    return templates.TemplateResponse("evaluations/form.html", {
        "request": request,
        "current_user": user,
        "evaluation": ev,
        "groups": groups,
        "existing": existing,
        "is_self": ev.is_self_evaluation,
        "score_labels": {
            1: "Muito abaixo da expectativa",
            2: "Abaixo da expectativa",
            3: "Atende a expectativa",
            4: "Acima da expectativa",
            5: "Muito acima da expectativa",
        },
    })


@router.post("/{eval_id}/save")
async def save_evaluation(
    eval_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    ev = db.query(Evaluation).get(eval_id)
    if not ev or ev.evaluator_id != user.id:
        raise HTTPException(403)

    if ev.status == EvaluationStatus.submitted:
        raise HTTPException(400, detail="Avaliação já submetida.")

    form = await request.form()
    competencies = get_competencies_for_position(db, ev.evaluatee.position or "")

    for comp in competencies:
        score_key = f"score_{comp.id}"
        comment_key = f"comment_{comp.id}"
        score_val = form.get(score_key)
        comment_val = form.get(comment_key, "").strip()

        existing = db.query(EvaluationAnswer).filter(
            EvaluationAnswer.evaluation_id == eval_id,
            EvaluationAnswer.competency_id == comp.id,
        ).first()

        if existing:
            existing.score = float(score_val) if score_val else None
            existing.comment = comment_val or None
        else:
            ans = EvaluationAnswer(
                evaluation_id=eval_id,
                competency_id=comp.id,
                score=float(score_val) if score_val else None,
                comment=comment_val or None,
            )
            db.add(ans)

    ev.general_observations = form.get("general_observations", "").strip() or None
    ev.status = EvaluationStatus.in_progress
    db.commit()

    return RedirectResponse(f"/evaluations/{eval_id}?saved=1", status_code=302)


@router.post("/{eval_id}/submit")
async def submit_evaluation(
    eval_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    ev = db.query(Evaluation).get(eval_id)
    if not ev or ev.evaluator_id != user.id:
        raise HTTPException(403)

    if ev.status == EvaluationStatus.submitted:
        raise HTTPException(400, detail="Avaliação já submetida.")

    form = await request.form()
    competencies = get_competencies_for_position(db, ev.evaluatee.position or "")

    # Validate all scores filled
    missing = []
    for comp in competencies:
        score_val = form.get(f"score_{comp.id}")
        if not score_val:
            missing.append(comp.name)

    obs = form.get("general_observations", "").strip()
    if not obs:
        missing.append("Observações Gerais")

    if missing:
        existing = {a.competency_id: a for a in ev.answers}
        groups = {}
        for comp in competencies:
            g = comp.group.name if comp.group else "Geral"
            groups.setdefault(g, []).append(comp)
        return templates.TemplateResponse("evaluations/form.html", {
            "request": request,
            "current_user": user,
            "evaluation": ev,
            "groups": groups,
            "existing": existing,
            "is_self": ev.is_self_evaluation,
            "score_labels": {1: "Muito abaixo", 2: "Abaixo", 3: "Atende", 4: "Acima", 5: "Muito acima"},
            "error": f"Preencha todos os campos obrigatórios: {', '.join(missing[:3])}{'...' if len(missing) > 3 else ''}",
            "form_data": dict(form),
        })

    # Save all answers
    for comp in competencies:
        score_val = form.get(f"score_{comp.id}")
        comment_val = form.get(f"comment_{comp.id}", "").strip()
        existing = db.query(EvaluationAnswer).filter(
            EvaluationAnswer.evaluation_id == eval_id,
            EvaluationAnswer.competency_id == comp.id,
        ).first()
        if existing:
            existing.score = float(score_val)
            existing.comment = comment_val or None
        else:
            db.add(EvaluationAnswer(
                evaluation_id=eval_id,
                competency_id=comp.id,
                score=float(score_val),
                comment=comment_val or None,
            ))

    ev.general_observations = obs
    ev.status = EvaluationStatus.submitted
    ev.submitted_at = datetime.utcnow()
    db.commit()

    return RedirectResponse("/dashboard?msg=submitted", status_code=302)


@router.get("/{eval_id}/view", response_class=HTMLResponse)
async def view_evaluation(eval_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    ev = db.query(Evaluation).get(eval_id)
    if not ev:
        raise HTTPException(404)

    # Admin or evaluator can view
    if ev.evaluator_id != user.id and user.role.value != "admin":
        raise HTTPException(403)

    competencies = get_competencies_for_position(db, ev.evaluatee.position or "")
    answers = {a.competency_id: a for a in ev.answers}
    groups = {}
    for comp in competencies:
        g = comp.group.name if comp.group else "Geral"
        groups.setdefault(g, []).append(comp)

    return templates.TemplateResponse("evaluations/view.html", {
        "request": request,
        "current_user": user,
        "evaluation": ev,
        "groups": groups,
        "answers": answers,
        "score_labels": {
            1: "Muito abaixo da expectativa",
            2: "Abaixo da expectativa",
            3: "Atende a expectativa",
            4: "Acima da expectativa",
            5: "Muito acima da expectativa",
        },
    })


# ── Reports (admin only) ──────────────────────────────────────────────────

@router.get("/reports/cycle/{cycle_id}", response_class=HTMLResponse)
async def reports_list(cycle_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    cycle = db.query(EvaluationCycle).get(cycle_id)
    if not cycle:
        raise HTTPException(404)

    users_in_cycle = (
        db.query(User)
        .join(Evaluation, Evaluation.evaluatee_id == User.id)
        .filter(Evaluation.cycle_id == cycle_id)
        .distinct()
        .order_by(User.name)
        .all()
    )

    users_data = []
    for u in users_in_cycle:
        data = aggregate_report_data(db, u.id, cycle_id)
        users_data.append({
            "user": u,
            "summary": data["summary"],
            "comp_count": len(data["comp_scores"]),
        })

    return templates.TemplateResponse("admin/reports.html", {
        "request": request,
        "current_user": user,
        "cycle": cycle,
        "users_data": users_data,
    })


@router.get("/reports/{cycle_id}/{user_id}/pdf")
async def download_pdf(cycle_id: int, user_id: int, request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    data = aggregate_report_data(db, user_id, cycle_id)
    u = data["user"]
    cycle = data["cycle"]

    pdf_bytes = generate_individual_report(
        user_name=u.name,
        position=u.position or "—",
        department=u.department or "—",
        cycle_name=cycle.name if cycle else "—",
        summary=data["summary"],
        comp_scores=data["comp_scores"],
        evaluations=data["evaluations"],
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="AVD_{u.name.replace(" ", "_")}_{cycle_id}.pdf"'
        },
    )


@router.get("/reports/{cycle_id}/{user_id}", response_class=HTMLResponse)
async def view_report(cycle_id: int, user_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    data = aggregate_report_data(db, user_id, cycle_id)

    return templates.TemplateResponse("admin/report_detail.html", {
        "request": request,
        "current_user": user,
        "data": data,
        "cycle_id": cycle_id,
        "user_id": user_id,
    })
