from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import Dict, List, Optional
import json

from app.models.database import (
    User, Evaluation, EvaluationAnswer, Competency,
    CompetencyGroup, EvaluationCycle, EvaluationAssignment,
    EvaluationStatus
)


def get_competencies_for_position(db: Session, position: str) -> List[Competency]:
    groups = db.query(CompetencyGroup).filter(CompetencyGroup.is_active == True).all()
    result = []
    for g in groups:
        try:
            positions = json.loads(g.target_positions or "[]")
        except Exception:
            positions = []
        if position in positions:
            for c in g.competencies:
                if c.is_active:
                    result.append(c)
    return result


def get_cycle_progress(db: Session, cycle_id: int) -> Dict:
    """Returns completion stats for a cycle."""
    total = db.query(Evaluation).filter(Evaluation.cycle_id == cycle_id).count()
    submitted = db.query(Evaluation).filter(
        Evaluation.cycle_id == cycle_id,
        Evaluation.status == EvaluationStatus.submitted
    ).count()
    pending = total - submitted
    pct = round((submitted / total * 100) if total > 0 else 0)
    return {"total": total, "submitted": submitted, "pending": pending, "pct": pct}


def get_user_cycle_progress(db: Session, user_id: int, cycle_id: int) -> Dict:
    """Progress for a specific evaluator in a cycle."""
    total = db.query(Evaluation).filter(
        Evaluation.cycle_id == cycle_id,
        Evaluation.evaluator_id == user_id
    ).count()
    submitted = db.query(Evaluation).filter(
        Evaluation.cycle_id == cycle_id,
        Evaluation.evaluator_id == user_id,
        Evaluation.status == EvaluationStatus.submitted
    ).count()
    pct = round((submitted / total * 100) if total > 0 else 0)
    return {"total": total, "submitted": submitted, "pending": total - submitted, "pct": pct}


def aggregate_report_data(db: Session, evaluatee_id: int, cycle_id: int) -> Dict:
    """Build full report data for one user in one cycle."""
    evaluatee = db.query(User).get(evaluatee_id)
    cycle = db.query(EvaluationCycle).get(cycle_id)

    evaluations = db.query(Evaluation).filter(
        Evaluation.evaluatee_id == evaluatee_id,
        Evaluation.cycle_id == cycle_id,
        Evaluation.status == EvaluationStatus.submitted,
    ).all()

    self_evals = [e for e in evaluations if e.is_self_evaluation]
    peer_evals = [e for e in evaluations if not e.is_self_evaluation and
                  e.evaluator.position not in ["Coordenador de Projetos", "Diretor Comercial",
                                                "Diretor de Projetos", "Diretor de Gestão", "Presidente"]]
    manager_evals = [e for e in evaluations if not e.is_self_evaluation and
                     e.evaluator.position in ["Coordenador de Projetos", "Diretor Comercial",
                                              "Diretor de Projetos", "Diretor de Gestão", "Presidente"]]

    def avg_score(evals):
        scores = []
        for e in evals:
            for a in e.answers:
                if a.score is not None:
                    scores.append(a.score * (a.competency.weight if a.competency else 1))
        return (sum(scores) / len(scores)) if scores else None

    summary = {
        "self": {"count": len(self_evals), "avg": avg_score(self_evals)},
        "peers": {"count": len(peer_evals), "avg": avg_score(peer_evals)},
        "managers": {"count": len(manager_evals), "avg": avg_score(manager_evals)},
        "overall": {"count": len(evaluations), "avg": avg_score(evaluations)},
    }

    # Per-competency breakdown
    competencies = get_competencies_for_position(db, evaluatee.position or "")
    comp_scores = []
    for comp in competencies:
        def comp_avg(evals):
            scores = [a.score for e in evals for a in e.answers
                      if a.competency_id == comp.id and a.score is not None]
            return (sum(scores) / len(scores)) if scores else None

        self_avg = comp_avg(self_evals)
        peers_avg = comp_avg(peer_evals)
        all_avg = comp_avg(evaluations)
        comp_scores.append({
            "id": comp.id,
            "name": comp.name,
            "group": comp.group.name if comp.group else "",
            "self": self_avg,
            "peers": peers_avg,
            "avg": all_avg,
        })

    # Full evaluation details for comments
    ev_details = []
    for ev in evaluations:
        rel = "Autoavaliação" if ev.is_self_evaluation else (
            "Superior" if ev.evaluator.position in ["Coordenador de Projetos", "Diretor Comercial",
                                                     "Diretor de Projetos", "Diretor de Gestão", "Presidente"]
            else "Par"
        )
        ev_details.append({
            "evaluator_name": ev.evaluator.name,
            "relationship": rel,
            "general_observations": ev.general_observations,
            "answers": [
                {
                    "competency": a.competency.name if a.competency else "",
                    "score": a.score,
                    "comment": a.comment,
                }
                for a in ev.answers if a.comment
            ],
        })

    return {
        "user": evaluatee,
        "cycle": cycle,
        "summary": summary,
        "comp_scores": comp_scores,
        "evaluations": ev_details,
    }
