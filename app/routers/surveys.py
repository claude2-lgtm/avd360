from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from app.templates_config import make_templates
from sqlalchemy.orm import Session
from datetime import datetime
import re
import csv
import io

from app.models.database import (
    get_db, SurveyForm, SurveyQuestion, SurveyQuestionType,
    SurveyResponse, SurveyAnswer, EvaluationStatus, User,
)
from app.services.auth import get_current_user_from_cookie, require_admin
from app.services.surveys_data import (
    SCALE_LABELS, SCALE_RANGES, current_period,
    br_to_utc, utc_to_br_input, utc_to_br_display,
)

router = APIRouter(prefix="/surveys")
templates = make_templates()


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "formulario"


def _deadline_status(form: SurveyForm, now: datetime = None):
    """None se o formulário está dentro do prazo (ou sem prazo definido);
    caso contrário, uma mensagem explicando por que está fechado."""
    now = now or datetime.utcnow()
    if form.opens_at and now < form.opens_at:
        return f"Esta pesquisa abre em {utc_to_br_display(form.opens_at)} (horário de Brasília)."
    if form.closes_at and now > form.closes_at:
        return f"O prazo desta pesquisa encerrou em {utc_to_br_display(form.closes_at)} (horário de Brasília)."
    return None


# ── Preenchimento (colaborador) ─────────────────────────────────────────────

@router.get("", response_class=HTMLResponse)
async def surveys_list(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    period = current_period()
    forms = db.query(SurveyForm).filter(SurveyForm.is_active == True).order_by(SurveyForm.created_at).all()

    cards = []
    for form in forms:
        resp = db.query(SurveyResponse).filter(
            SurveyResponse.form_id == form.id,
            SurveyResponse.user_id == user.id,
            SurveyResponse.period == period,
        ).first()
        cards.append({
            "key": form.key,
            "title": form.title,
            "description": form.description,
            "status": resp.status.value if resp else "pending",
            "closed_msg": None if (resp and resp.status == EvaluationStatus.submitted) else _deadline_status(form),
        })

    return templates.TemplateResponse("surveys/list.html", {
        "request": request,
        "current_user": user,
        "period": period,
        "cards": cards,
    })


# ── Gerenciamento de formulários (admin) ────────────────────────────────────
# IMPORTANTE: estas rotas /manage/* precisam vir ANTES de /{survey_type}
# no arquivo, senão o FastAPI tentaria casar "/surveys/manage" com o
# parâmetro dinâmico survey_type.

@router.get("/manage", response_class=HTMLResponse)
async def manage_list(request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    forms = db.query(SurveyForm).order_by(SurveyForm.created_at).all()

    forms_data = []
    for f in forms:
        resp_count = db.query(SurveyResponse).filter(
            SurveyResponse.form_id == f.id,
            SurveyResponse.status == EvaluationStatus.submitted,
        ).count()
        forms_data.append({
            "form": f, "question_count": len(f.questions), "response_count": resp_count,
            "opens_at_display": utc_to_br_display(f.opens_at),
            "closes_at_display": utc_to_br_display(f.closes_at),
        })

    return templates.TemplateResponse("surveys/manage_list.html", {
        "request": request,
        "current_user": user,
        "forms_data": forms_data,
    })


@router.get("/manage/new", response_class=HTMLResponse)
async def manage_new_form(request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    return templates.TemplateResponse("surveys/manage_new.html", {
        "request": request,
        "current_user": user,
    })


@router.post("/manage/new")
async def manage_create_form(request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    form_data = await request.form()
    title = (form_data.get("title") or "").strip()
    description = (form_data.get("description") or "").strip()
    opens_at = br_to_utc(form_data.get("opens_at"))
    closes_at = br_to_utc(form_data.get("closes_at"))

    if not title:
        return templates.TemplateResponse("surveys/manage_new.html", {
            "request": request,
            "current_user": user,
            "error": "O título é obrigatório.",
        }, status_code=400)

    if opens_at and closes_at and opens_at > closes_at:
        return templates.TemplateResponse("surveys/manage_new.html", {
            "request": request,
            "current_user": user,
            "error": "O prazo de encerramento precisa ser depois do início.",
        }, status_code=400)

    base_key = _slugify(title)
    key = base_key
    i = 2
    while db.query(SurveyForm).filter(SurveyForm.key == key).first():
        key = f"{base_key}-{i}"
        i += 1

    form = SurveyForm(
        key=key, title=title, description=description or None,
        is_active=True, opens_at=opens_at, closes_at=closes_at,
        created_by_id=user.id,
    )
    db.add(form)
    db.commit()
    db.refresh(form)

    return RedirectResponse(f"/surveys/manage/{form.id}/edit?created=1", status_code=302)


@router.get("/manage/{form_id}/edit", response_class=HTMLResponse)
async def manage_edit_form(form_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    form = db.query(SurveyForm).get(form_id)
    if not form:
        raise HTTPException(404)

    return templates.TemplateResponse("surveys/manage_edit.html", {
        "request": request,
        "current_user": user,
        "form": form,
        "created": request.query_params.get("created"),
        "opens_at_input": utc_to_br_input(form.opens_at),
        "closes_at_input": utc_to_br_input(form.closes_at),
    })


@router.post("/manage/{form_id}/edit")
async def manage_update_form(form_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    form = db.query(SurveyForm).get(form_id)
    if not form:
        raise HTTPException(404)

    form_data = await request.form()
    title = (form_data.get("title") or "").strip()
    description = (form_data.get("description") or "").strip()
    opens_at = br_to_utc(form_data.get("opens_at"))
    closes_at = br_to_utc(form_data.get("closes_at"))

    if opens_at and closes_at and opens_at > closes_at:
        return templates.TemplateResponse("surveys/manage_edit.html", {
            "request": request,
            "current_user": user,
            "form": form,
            "opens_at_input": form_data.get("opens_at"),
            "closes_at_input": form_data.get("closes_at"),
            "error": "O prazo de encerramento precisa ser depois do início.",
        }, status_code=400)

    if title:
        form.title = title
    form.description = description or None
    form.opens_at = opens_at
    if closes_at != form.closes_at:
        form.reminder_sent = False
    form.closes_at = closes_at
    db.commit()

    return RedirectResponse(f"/surveys/manage/{form_id}/edit?saved=1", status_code=302)


@router.post("/manage/{form_id}/toggle")
async def manage_toggle_form(form_id: int, request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    form = db.query(SurveyForm).get(form_id)
    if not form:
        raise HTTPException(404)
    form.is_active = not form.is_active
    db.commit()
    return RedirectResponse("/surveys/manage", status_code=302)


@router.post("/manage/{form_id}/delete")
async def manage_delete_form(form_id: int, request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    form = db.query(SurveyForm).get(form_id)
    if not form:
        raise HTTPException(404)
    db.delete(form)
    db.commit()
    return RedirectResponse("/surveys/manage", status_code=302)


@router.post("/manage/{form_id}/questions/add")
async def manage_add_question(form_id: int, request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    form = db.query(SurveyForm).get(form_id)
    if not form:
        raise HTTPException(404)

    form_data = await request.form()
    text = (form_data.get("text") or "").strip()
    q_type = form_data.get("type") or "scale"
    group_name = (form_data.get("group_name") or "").strip() or None

    if text:
        max_order = db.query(SurveyQuestion).filter(SurveyQuestion.form_id == form_id).count()
        db.add(SurveyQuestion(
            form_id=form_id, group_name=group_name, text=text,
            type=q_type, order=max_order,
        ))
        db.commit()

    return RedirectResponse(f"/surveys/manage/{form_id}/edit", status_code=302)


@router.post("/manage/{form_id}/questions/{question_id}/edit")
async def manage_edit_question(form_id: int, question_id: int, request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    q = db.query(SurveyQuestion).filter(
        SurveyQuestion.id == question_id, SurveyQuestion.form_id == form_id,
    ).first()
    if not q:
        raise HTTPException(404)

    form_data = await request.form()
    text = (form_data.get("text") or "").strip()
    q_type = form_data.get("type") or q.type.value
    group_name = (form_data.get("group_name") or "").strip() or None

    if text:
        q.text = text
    q.type = q_type
    q.group_name = group_name
    db.commit()

    return RedirectResponse(f"/surveys/manage/{form_id}/edit", status_code=302)


@router.post("/manage/{form_id}/questions/{question_id}/delete")
async def manage_delete_question(form_id: int, question_id: int, request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    q = db.query(SurveyQuestion).filter(
        SurveyQuestion.id == question_id, SurveyQuestion.form_id == form_id,
    ).first()
    if q:
        db.delete(q)
        db.commit()
    return RedirectResponse(f"/surveys/manage/{form_id}/edit", status_code=302)


@router.post("/manage/{form_id}/questions/{question_id}/move")
async def manage_move_question(form_id: int, question_id: int, request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    form_data = await request.form()
    direction = form_data.get("direction")  # "up" or "down"

    questions = db.query(SurveyQuestion).filter(
        SurveyQuestion.form_id == form_id,
    ).order_by(SurveyQuestion.order).all()

    idx = next((i for i, q in enumerate(questions) if q.id == question_id), None)
    if idx is not None:
        swap_idx = idx - 1 if direction == "up" else idx + 1
        if 0 <= swap_idx < len(questions):
            questions[idx].order, questions[swap_idx].order = questions[swap_idx].order, questions[idx].order
            db.commit()

    return RedirectResponse(f"/surveys/manage/{form_id}/edit", status_code=302)


# ── Preenchimento (continuação) ─────────────────────────────────────────────

def _get_or_create_response(db: Session, form: SurveyForm, user_id: int, period: str) -> SurveyResponse:
    resp = db.query(SurveyResponse).filter(
        SurveyResponse.form_id == form.id,
        SurveyResponse.user_id == user_id,
        SurveyResponse.period == period,
    ).first()
    if not resp:
        resp = SurveyResponse(
            form_id=form.id, user_id=user_id, period=period,
            status=EvaluationStatus.pending,
        )
        db.add(resp)
        db.commit()
        db.refresh(resp)
    return resp


def _grouped_questions(form: SurveyForm):
    groups = {}
    for q in form.questions:
        g = q.group_name or "Geral"
        groups.setdefault(g, []).append(q)
    return groups


@router.get("/{survey_type}", response_class=HTMLResponse)
async def survey_form(survey_type: str, request: Request, db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    form = db.query(SurveyForm).filter(SurveyForm.key == survey_type).first()
    if not form:
        raise HTTPException(404)

    period = current_period()
    resp = _get_or_create_response(db, form, user.id, period)

    if resp.status == EvaluationStatus.submitted:
        return RedirectResponse(f"/surveys/{survey_type}/view", status_code=302)

    existing = {a.question_id: a for a in resp.answers}

    return templates.TemplateResponse("surveys/form.html", {
        "request": request,
        "current_user": user,
        "survey_type": survey_type,
        "form_obj": form,
        "groups": _grouped_questions(form),
        "existing": existing,
        "scale_labels": SCALE_LABELS,
        "saved": request.query_params.get("saved"),
        "closed_msg": _deadline_status(form),
    })


async def _save_answers(db: Session, resp: SurveyResponse, form: SurveyForm, form_data) -> list:
    missing = []
    for q in form.questions:
        existing = db.query(SurveyAnswer).filter(
            SurveyAnswer.response_id == resp.id,
            SurveyAnswer.question_id == q.id,
        ).first()

        if q.type in (SurveyQuestionType.scale, SurveyQuestionType.rating10) or q.type in ("scale", "rating10"):
            val = form_data.get(f"score_{q.id}")
            score = int(val) if val else None
            if not existing:
                existing = SurveyAnswer(response_id=resp.id, question_id=q.id)
                db.add(existing)
            existing.score = score
            if score is None:
                missing.append(q.text)
        else:
            val = (form_data.get(f"text_{q.id}") or "").strip()
            if not existing:
                existing = SurveyAnswer(response_id=resp.id, question_id=q.id)
                db.add(existing)
            existing.text_answer = val or None
            if not val:
                missing.append(q.text)

    return missing


@router.post("/{survey_type}/save")
async def save_survey(survey_type: str, request: Request, db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    form = db.query(SurveyForm).filter(SurveyForm.key == survey_type).first()
    if not form:
        raise HTTPException(404)

    period = current_period()
    resp = _get_or_create_response(db, form, user.id, period)
    if resp.status == EvaluationStatus.submitted:
        raise HTTPException(400, detail="Pesquisa já enviada.")
    if _deadline_status(form):
        raise HTTPException(400, detail="Fora do prazo desta pesquisa.")

    form_data = await request.form()
    await _save_answers(db, resp, form, form_data)
    resp.status = EvaluationStatus.in_progress
    db.commit()

    return RedirectResponse(f"/surveys/{survey_type}?saved=1", status_code=302)


@router.post("/{survey_type}/submit")
async def submit_survey(survey_type: str, request: Request, db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    form = db.query(SurveyForm).filter(SurveyForm.key == survey_type).first()
    if not form:
        raise HTTPException(404)

    period = current_period()
    resp = _get_or_create_response(db, form, user.id, period)
    if resp.status == EvaluationStatus.submitted:
        raise HTTPException(400, detail="Pesquisa já enviada.")
    if _deadline_status(form):
        raise HTTPException(400, detail="Fora do prazo desta pesquisa.")

    form_data = await request.form()
    missing = await _save_answers(db, resp, form, form_data)

    if missing:
        db.commit()
        existing = {a.question_id: a for a in resp.answers}
        return templates.TemplateResponse("surveys/form.html", {
            "request": request,
            "current_user": user,
            "survey_type": survey_type,
            "form_obj": form,
            "groups": _grouped_questions(form),
            "existing": existing,
            "scale_labels": SCALE_LABELS,
            "error": f"Preencha todas as perguntas obrigatórias: {', '.join(missing[:3])}{'...' if len(missing) > 3 else ''}",
        }, status_code=400)

    resp.status = EvaluationStatus.submitted
    resp.submitted_at = datetime.utcnow()
    db.commit()

    return RedirectResponse("/surveys?msg=submitted", status_code=302)


@router.get("/{survey_type}/view", response_class=HTMLResponse)
async def view_survey(survey_type: str, request: Request, db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    form = db.query(SurveyForm).filter(SurveyForm.key == survey_type).first()
    if not form:
        raise HTTPException(404)

    period = current_period()
    resp = db.query(SurveyResponse).filter(
        SurveyResponse.form_id == form.id,
        SurveyResponse.user_id == user.id,
        SurveyResponse.period == period,
    ).first()
    if not resp:
        raise HTTPException(404)

    answers = {a.question_id: a for a in resp.answers}

    return templates.TemplateResponse("surveys/view.html", {
        "request": request,
        "current_user": user,
        "survey_type": survey_type,
        "form_obj": form,
        "response": resp,
        "groups": _grouped_questions(form),
        "answers": answers,
        "scale_labels": SCALE_LABELS,
    })


# ── Admin: resultados ──────────────────────────────────────────────────────

@router.get("/admin/{survey_type}/results", response_class=HTMLResponse)
async def admin_survey_results(survey_type: str, request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)

    form = db.query(SurveyForm).filter(SurveyForm.key == survey_type).first()
    if not form:
        raise HTTPException(404)

    period = request.query_params.get("period") or current_period()
    question_id_raw = request.query_params.get("question_id")
    selected_question_id = int(question_id_raw) if question_id_raw and question_id_raw.isdigit() else None

    responses = db.query(SurveyResponse).filter(
        SurveyResponse.form_id == form.id,
        SurveyResponse.period == period,
        SurveyResponse.status == EvaluationStatus.submitted,
    ).all()

    total_users = db.query(User).filter(User.is_active == True).count()

    averages = {}
    distributions = {}
    text_answers = {}
    for q in form.questions:
        q_type = q.type.value if hasattr(q.type, "value") else q.type
        is_numeric = q_type in SCALE_RANGES
        scores = []
        texts = []
        for r in responses:
            for a in r.answers:
                if a.question_id != q.id:
                    continue
                if is_numeric and a.score is not None:
                    scores.append(a.score)
                elif not is_numeric and a.text_answer:
                    texts.append({"user": r.user.name, "text": a.text_answer})

        if is_numeric:
            value_range = SCALE_RANGES[q_type]
            averages[q.id] = round(sum(scores) / len(scores), 2) if scores else None
            counts = {v: scores.count(v) for v in value_range}
            total = len(scores) or 1
            distributions[q.id] = {
                "counts": counts,
                "pct": {v: round(counts[v] * 100 / total, 1) for v in value_range},
                "total": len(scores),
                "range": list(value_range),
                "max": value_range[-1],
            }
        else:
            text_answers[q.id] = texts

    scale_question_ids = {q.id for q in form.questions if (q.type.value if hasattr(q.type, "value") else q.type) == "scale"}
    overall_scores = [
        a.score for r in responses for a in r.answers
        if a.question_id in scale_question_ids and a.score is not None
    ]
    overall_average = round(sum(overall_scores) / len(overall_scores), 2) if overall_scores else None

    groups_all = _grouped_questions(form)
    if selected_question_id:
        groups = {g: [q for q in qs if q.id == selected_question_id] for g, qs in groups_all.items()}
        groups = {g: qs for g, qs in groups.items() if qs}
    else:
        groups = groups_all

    return templates.TemplateResponse("surveys/admin_results.html", {
        "request": request,
        "current_user": user,
        "survey_type": survey_type,
        "form_obj": form,
        "period": period,
        "responses": responses,
        "total_users": total_users,
        "averages": averages,
        "distributions": distributions,
        "text_answers": text_answers,
        "overall_average": overall_average,
        "groups": groups,
        "selected_question_id": selected_question_id,
        "scale_labels": SCALE_LABELS,
    })


@router.get("/admin/{survey_type}/export.csv")
async def export_survey_csv(survey_type: str, request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    form = db.query(SurveyForm).filter(SurveyForm.key == survey_type).first()
    if not form:
        raise HTTPException(404)

    period = request.query_params.get("period") or current_period()
    responses = db.query(SurveyResponse).filter(
        SurveyResponse.form_id == form.id,
        SurveyResponse.period == period,
        SurveyResponse.status == EvaluationStatus.submitted,
    ).all()

    buf = io.StringIO()
    buf.write("﻿")
    writer = csv.writer(buf)
    writer.writerow(["Respondente", "Pergunta", "Resposta", "Enviado em"])
    for r in responses:
        submitted = r.submitted_at.strftime("%d/%m/%Y %H:%M") if r.submitted_at else ""
        by_q = {a.question_id: a for a in r.answers}
        for q in form.questions:
            a = by_q.get(q.id)
            if not a:
                continue
            value = a.score if a.score is not None else (a.text_answer or "")
            writer.writerow([r.user.name, q.text, value, submitted])

    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="avd360_{survey_type}_{period}.csv"'},
    )


@router.get("/admin/{survey_type}/results/{user_id}", response_class=HTMLResponse)
async def admin_survey_detail(survey_type: str, user_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)

    form = db.query(SurveyForm).filter(SurveyForm.key == survey_type).first()
    if not form:
        raise HTTPException(404)

    period = request.query_params.get("period") or current_period()

    resp = db.query(SurveyResponse).filter(
        SurveyResponse.form_id == form.id,
        SurveyResponse.user_id == user_id,
        SurveyResponse.period == period,
    ).first()
    if not resp:
        raise HTTPException(404)

    answers = {a.question_id: a for a in resp.answers}

    return templates.TemplateResponse("surveys/view.html", {
        "request": request,
        "current_user": user,
        "survey_type": survey_type,
        "form_obj": form,
        "response": resp,
        "period": period,
        "groups": _grouped_questions(form),
        "answers": answers,
        "scale_labels": SCALE_LABELS,
        "viewing_as_admin": True,
    })


@router.post("/admin/{survey_type}/results/{user_id}/delete")
async def admin_survey_delete_response(survey_type: str, user_id: int, request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)

    form = db.query(SurveyForm).filter(SurveyForm.key == survey_type).first()
    if not form:
        raise HTTPException(404)

    period = request.query_params.get("period") or current_period()

    resp = db.query(SurveyResponse).filter(
        SurveyResponse.form_id == form.id,
        SurveyResponse.user_id == user_id,
        SurveyResponse.period == period,
    ).first()
    if resp:
        db.delete(resp)
        db.commit()

    return RedirectResponse(f"/surveys/admin/{survey_type}/results?period={period}&msg=deleted", status_code=302)
