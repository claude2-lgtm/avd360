import hmac
import os
from datetime import datetime, timedelta

from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session

from app.models.database import (
    get_db, EvaluationCycle, CycleStatus, Evaluation, EvaluationStatus,
    SurveyForm, SurveyResponse, User,
)
from app.services.surveys_data import current_period, utc_to_br_display
from app.services.email import notify_cycle_deadline_reminder, notify_survey_deadline_reminder

router = APIRouter(prefix="/internal")

REMINDER_SECRET = os.getenv("REMINDER_SECRET", "")
REMINDER_LEAD_HOURS = float(os.getenv("REMINDER_LEAD_HOURS", "12"))


@router.post("/reminders/run")
async def run_reminders(request: Request, db: Session = Depends(get_db)):
    provided = request.headers.get("X-Reminder-Secret", "")
    if not REMINDER_SECRET or not hmac.compare_digest(provided, REMINDER_SECRET):
        raise HTTPException(status_code=401, detail="unauthorized")

    now = datetime.utcnow()
    lead = timedelta(hours=REMINDER_LEAD_HOURS)
    result = {"cycles_processed": 0, "cycle_emails_sent": 0, "forms_processed": 0, "form_emails_sent": 0}

    due_cycles = db.query(EvaluationCycle).filter(
        EvaluationCycle.status == CycleStatus.active,
        EvaluationCycle.end_date.isnot(None),
        EvaluationCycle.reminder_sent == False,
        EvaluationCycle.end_date > now,
        EvaluationCycle.end_date <= now + lead,
    ).all()

    for cycle in due_cycles:
        pending_ids = {
            row[0] for row in db.query(Evaluation.evaluator_id).filter(
                Evaluation.cycle_id == cycle.id,
                Evaluation.status != EvaluationStatus.submitted,
            ).distinct().all()
        }
        if pending_ids:
            users = db.query(User).filter(User.id.in_(pending_ids), User.is_active == True).all()
            if users:
                await notify_cycle_deadline_reminder(users, cycle.name, cycle.end_date.strftime("%d/%m/%Y %H:%M"))
                result["cycle_emails_sent"] += len(users)
        cycle.reminder_sent = True
        result["cycles_processed"] += 1
    db.commit()

    due_forms = db.query(SurveyForm).filter(
        SurveyForm.is_active == True,
        SurveyForm.closes_at.isnot(None),
        SurveyForm.reminder_sent == False,
        SurveyForm.closes_at > now,
        SurveyForm.closes_at <= now + lead,
    ).all()

    for form in due_forms:
        period = current_period()
        active_users = db.query(User).filter(User.is_active == True).all()
        submitted_ids = {
            r.user_id for r in db.query(SurveyResponse).filter(
                SurveyResponse.form_id == form.id,
                SurveyResponse.period == period,
                SurveyResponse.status == EvaluationStatus.submitted,
            ).all()
        }
        pending_users = [u for u in active_users if u.id not in submitted_ids]
        if pending_users:
            await notify_survey_deadline_reminder(
                pending_users, form.title, form.key, utc_to_br_display(form.closes_at)
            )
            result["form_emails_sent"] += len(pending_users)
        form.reminder_sent = True
        result["forms_processed"] += 1
    db.commit()

    return result
