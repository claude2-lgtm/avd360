from fastapi import APIRouter, Request, Form, Depends, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from app.templates_config import make_templates
from sqlalchemy.orm import Session
from datetime import timedelta

from app.models.database import get_db
from app.services.auth import (
    authenticate_user, create_access_token,
    get_current_user_from_cookie, ACCESS_TOKEN_EXPIRE_MINUTES
)

router = APIRouter()
templates = make_templates()


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(request, db)
    if user:
        return RedirectResponse("/dashboard", status_code=302)
    return templates.TemplateResponse("auth/login.html", {"request": request, "error": None})


@router.post("/login", response_class=HTMLResponse)
async def login_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = authenticate_user(db, email.strip().lower(), password)
    if not user:
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "E-mail ou senha incorretos."},
            status_code=401,
        )

    token = create_access_token(
        data={"sub": user.email},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    response = RedirectResponse("/dashboard", status_code=302)
    response.set_cookie(
        key="access_token",
        value=f"Bearer {token}",
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
    )
    return response


@router.get("/logout")
async def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("access_token")
    return response
