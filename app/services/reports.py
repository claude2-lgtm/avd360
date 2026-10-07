from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import Dict, List, Optional
import json

from app.models.database import (
    User, Evaluation, EvaluationAnswer, Competency,
    CompetencyGroup, EvaluationCycle, EvaluationAssignment,
    EvaluationStatus, POSITIONS, DIRECTOR_POSITIONS
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


# Evaluations made by these positions count as "Superiores". The accented spelling is kept
# in case it was typed that way in a user's record; the official one (POSITIONS) has no accent.
MANAGER_POSITIONS = ["Coordenador de Projetos"] + DIRECTOR_POSITIONS + ["Diretor de Gestão"]

# Which position averages each person sees next to their own result
EXTRA_REFERENCE_POSITIONS = {
    "Coordenador de Projetos": ["Consultor de Projetos"],
}


def reference_positions_for(user: User) -> List[str]:
    """Own position first; coordinators also see consultants; directors and Gestão see every position."""
    own = [user.position] if user.position else []
    if user.position in DIRECTOR_POSITIONS or user.department == "Gestao":
        return own + [p for p in POSITIONS if p != user.position]
    return own + EXTRA_REFERENCE_POSITIONS.get(user.position, [])


def get_position_averages(db: Session, cycle_id: int,
                          positions: Optional[List[str]] = None) -> Dict[str, Dict]:
    """Average result per position among everyone evaluated in the cycle.

    Each person's overall average counts once, regardless of how many evaluations
    they received. Positions with nobody evaluated are left out.
    """
    query = (
        db.query(User)
        .join(Evaluation, Evaluation.evaluatee_id == User.id)
        .filter(Evaluation.cycle_id == cycle_id, Evaluation.status == EvaluationStatus.submitted)
    )
    if positions is not None:
        query = query.filter(User.position.in_(positions))
    by_position: Dict[str, List[float]] = {}
    for person in query.distinct().all():
        data = aggregate_report_data(db, person.id, cycle_id, include_benchmark=False)
        avg = data["summary"]["overall"]["avg"]
        if avg is not None and person.position:
            by_position.setdefault(person.position, []).append(avg)

    order = {p: i for i, p in enumerate(POSITIONS)}
    return {
        pos: {"position": pos, "count": len(v), "avg": sum(v) / len(v), "min": min(v), "max": max(v)}
        for pos, v in sorted(by_position.items(), key=lambda kv: order.get(kv[0], len(order)))
    }


def aggregate_report_data(db: Session, evaluatee_id: int, cycle_id: int,
                          include_benchmark: bool = True,
                          benchmark_cache: Optional[Dict] = None) -> Dict:
    """Build full report data for one user in one cycle.

    Pass the same benchmark_cache dict when building many reports of a cycle so
    each position's average is computed only once (it maps position -> average or None).
    """
    evaluatee = db.query(User).get(evaluatee_id)
    cycle = db.query(EvaluationCycle).get(cycle_id)

    evaluations = db.query(Evaluation).filter(
        Evaluation.evaluatee_id == evaluatee_id,
        Evaluation.cycle_id == cycle_id,
        Evaluation.status == EvaluationStatus.submitted,
    ).all()

    self_evals = [e for e in evaluations if e.is_self_evaluation]
    peer_evals = [e for e in evaluations if not e.is_self_evaluation and
                  e.evaluator.position not in MANAGER_POSITIONS]
    manager_evals = [e for e in evaluations if not e.is_self_evaluation and
                     e.evaluator.position in MANAGER_POSITIONS]

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

    def answer_sort_key(a):
        c = a.competency
        if not c:
            return (1, 0, 0, 0)
        return (0, c.group.order if c.group else 0, c.order or 0, c.id)

    # Full evaluation details: every score and comment given by each evaluator
    rel_order = {"Autoavaliação": 0, "Superior": 1, "Par": 2}
    ev_details = []
    for ev in evaluations:
        rel = "Autoavaliação" if ev.is_self_evaluation else (
            "Superior" if ev.evaluator.position in MANAGER_POSITIONS else "Par"
        )
        answers = sorted(ev.answers, key=answer_sort_key)
        scores = [a.score for a in answers if a.score is not None]
        ev_details.append({
            "evaluator_name": ev.evaluator.name,
            "relationship": rel,
            "general_observations": ev.general_observations,
            "avg": (sum(scores) / len(scores)) if scores else None,
            "answers": [
                {
                    "competency": a.competency.name if a.competency else "",
                    "group": a.competency.group.name if a.competency and a.competency.group else "",
                    "score": a.score,
                    "comment": a.comment,
                }
                for a in answers
            ],
        })
    ev_details.sort(key=lambda e: (rel_order.get(e["relationship"], 9), e["evaluator_name"]))

    position_averages = []
    if include_benchmark:
        wanted = reference_positions_for(evaluatee)
        cache = benchmark_cache if benchmark_cache is not None else {}
        missing = [p for p in wanted if p not in cache]
        if missing:
            computed = get_position_averages(db, cycle_id, missing)
            for p in missing:
                cache[p] = computed.get(p)
        position_averages = [cache[p] for p in wanted if cache.get(p)]
    benchmark = next((a for a in position_averages if a["position"] == evaluatee.position), None)

    return {
        "user": evaluatee,
        "cycle": cycle,
        "summary": summary,
        "comp_scores": comp_scores,
        "evaluations": ev_details,
        "position_benchmark": benchmark,
        "position_averages": position_averages,
    }
