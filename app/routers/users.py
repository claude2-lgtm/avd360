from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from app.templates_config import make_templates
from sqlalchemy.orm import Session
from typing import Optional
import asyncio

from app.models.database import get_db, User, UserRole, DEPARTMENTS, POSITIONS
from app.services.auth import (
    get_current_user_from_cookie, require_admin,
    get_password_hash, generate_temp_password, verify_password
)
from app.services.email import notify_new_user

router = APIRouter(prefix="/users")
templates = make_templates()


@router.get("", response_class=HTMLResponse)
async def list_users(request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    users = db.query(User).filter(User.is_active == True).order_by(User.name).all()
    return templates.TemplateResponse("admin/users.html", {
        "request": request,
        "current_user": user,
        "users": users,
        "departments": DEPARTMENTS,
        "positions": POSITIONS,
        "all_users": users,
    })


@router.post("/create", response_class=HTMLResponse)
async def create_user(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    department: str = Form(...),
    position: str = Form(...),
    manager_id: Optional[int] = Form(None),
    role: str = Form("collaborator"),
    db: Session = Depends(get_db),
):
    require_admin(request, db)

    existing = db.query(User).filter(User.email == email.strip().lower()).first()
    if existing:
        users = db.query(User).filter(User.is_active == True).all()
        return templates.TemplateResponse("admin/users.html", {
            "request": request,
            "current_user": get_current_user_from_cookie(request, db),
            "users": users,
            "departments": DEPARTMENTS,
            "positions": POSITIONS,
            "all_users": users,
            "error": f"E-mail {email} já cadastrado.",
        })

    temp_pwd = generate_temp_password()
    new_user = User(
        name=name.strip(),
        email=email.strip().lower(),
        hashed_password=get_password_hash(temp_pwd),
        temp_password=temp_pwd,
        role=UserRole(role),
        department=department,
        position=position,
        manager_id=manager_id if manager_id else None,
        is_active=True,
    )
    db.add(new_user)
    db.commit()

    asyncio.create_task(notify_new_user(new_user.email, new_user.name, temp_pwd))

    return RedirectResponse("/users?msg=created", status_code=302)


@router.get("/{user_id}/edit", response_class=HTMLResponse)
async def edit_user_page(user_id: int, request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    target = db.query(User).get(user_id)
    if not target:
        raise HTTPException(404)
    all_users = db.query(User).filter(User.is_active == True, User.id != user_id).all()
    return templates.TemplateResponse("admin/user_edit.html", {
        "request": request,
        "current_user": get_current_user_from_cookie(request, db),
        "target_user": target,
        "departments": DEPARTMENTS,
        "positions": POSITIONS,
        "all_users": all_users,
    })


@router.post("/{user_id}/edit", response_class=HTMLResponse)
async def edit_user_post(
    user_id: int,
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    department: str = Form(...),
    position: str = Form(...),
    manager_id: Optional[int] = Form(None),
    role: str = Form("collaborator"),
    new_password: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    require_admin(request, db)
    target = db.query(User).get(user_id)
    if not target:
        raise HTTPException(404)

    target.name = name.strip()
    target.email = email.strip().lower()
    target.department = department
    target.position = position
    target.manager_id = manager_id if manager_id else None
    target.role = UserRole(role)

    if new_password and new_password.strip():
        target.hashed_password = get_password_hash(new_password.strip())
        target.temp_password = None

    db.commit()
    return RedirectResponse("/users?msg=updated", status_code=302)


@router.post("/{user_id}/delete")
async def delete_user(user_id: int, request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    target = db.query(User).get(user_id)
    if target:
        target.is_active = False
        db.commit()
    return RedirectResponse("/users?msg=deleted", status_code=302)


@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse("admin/profile.html", {
        "request": request,
        "current_user": user,
    })


@router.post("/profile/password")
async def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    error = None
    if not verify_password(current_password, user.hashed_password):
        error = "Senha atual incorreta."
    elif len(new_password) < 8:
        error = "A nova senha deve ter no mínimo 8 caracteres."
    elif new_password != confirm_password:
        error = "As senhas não coincidem."

    if error:
        return templates.TemplateResponse("admin/profile.html", {
            "request": request,
            "current_user": user,
            "error": error,
        })

    user.hashed_password = get_password_hash(new_password)
    user.temp_password = None
    db.commit()
    return RedirectResponse("/users/profile?msg=password_changed", status_code=302)
