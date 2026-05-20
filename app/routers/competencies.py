from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from app.templates_config import make_templates
from sqlalchemy.orm import Session
from typing import Optional
import json

from app.models.database import get_db, CompetencyGroup, Competency, POSITIONS
from app.services.auth import require_admin, get_current_user_from_cookie

router = APIRouter(prefix="/competencies")
templates = make_templates()


@router.get("", response_class=HTMLResponse)
async def list_competencies(request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    groups = db.query(CompetencyGroup).filter(
        CompetencyGroup.is_active == True
    ).order_by(CompetencyGroup.order, CompetencyGroup.name).all()

    return templates.TemplateResponse("admin/competencies.html", {
        "request": request,
        "current_user": user,
        "groups": groups,
        "positions": POSITIONS,
    })


@router.post("/groups/create")
async def create_group(
    request: Request,
    name: str = Form(...),
    target_positions: list = Form(...),
    db: Session = Depends(get_db),
):
    require_admin(request, db)
    group = CompetencyGroup(
        name=name.strip(),
        target_positions=json.dumps(target_positions, ensure_ascii=False),
        order=0,
        is_active=True,
    )
    db.add(group)
    db.commit()
    return RedirectResponse("/competencies?msg=group_created", status_code=302)


@router.post("/groups/{group_id}/edit")
async def edit_group(
    group_id: int,
    request: Request,
    name: str = Form(...),
    target_positions: list = Form(default=[]),
    db: Session = Depends(get_db),
):
    require_admin(request, db)
    group = db.query(CompetencyGroup).get(group_id)
    if not group:
        raise HTTPException(404)
    group.name = name.strip()
    group.target_positions = json.dumps(target_positions, ensure_ascii=False)
    db.commit()
    return RedirectResponse("/competencies?msg=updated", status_code=302)


@router.post("/groups/{group_id}/delete")
async def delete_group(group_id: int, request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    group = db.query(CompetencyGroup).get(group_id)
    if group:
        group.is_active = False
        for c in group.competencies:
            c.is_active = False
        db.commit()
    return RedirectResponse("/competencies?msg=deleted", status_code=302)


@router.post("/create")
async def create_competency(
    request: Request,
    group_id: int = Form(...),
    name: str = Form(...),
    description: Optional[str] = Form(None),
    weight: float = Form(1.0),
    db: Session = Depends(get_db),
):
    require_admin(request, db)
    comp = Competency(
        group_id=group_id,
        name=name.strip(),
        description=description,
        weight=weight,
        order=0,
        is_active=True,
    )
    db.add(comp)
    db.commit()
    return RedirectResponse("/competencies?msg=comp_created", status_code=302)


@router.post("/{comp_id}/edit")
async def edit_competency(
    comp_id: int,
    request: Request,
    name: str = Form(...),
    description: Optional[str] = Form(None),
    weight: float = Form(1.0),
    db: Session = Depends(get_db),
):
    require_admin(request, db)
    comp = db.query(Competency).get(comp_id)
    if not comp:
        raise HTTPException(404)
    comp.name = name.strip()
    comp.description = description
    comp.weight = weight
    db.commit()
    return RedirectResponse("/competencies?msg=updated", status_code=302)


@router.post("/{comp_id}/delete")
async def delete_competency(comp_id: int, request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    comp = db.query(Competency).get(comp_id)
    if comp:
        comp.is_active = False
        db.commit()
    return RedirectResponse("/competencies?msg=deleted", status_code=302)
