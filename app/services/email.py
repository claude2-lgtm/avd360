import os
from typing import List

import httpx


EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "false").lower() == "true"
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "noreply@grupogestao.com.br")

RESEND_API_URL = "https://api.resend.com/emails"


async def send_email(to: List[str], subject: str, body_html: str):
    if not EMAIL_ENABLED:
        print(f"[EMAIL SIMULADO] Para: {to} | Assunto: {subject}")
        return True
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                RESEND_API_URL,
                headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
                json={
                    "from": EMAIL_FROM,
                    "to": to,
                    "subject": subject,
                    "html": body_html,
                },
            )
        if response.status_code >= 400:
            print(f"[EMAIL ERRO] {response.status_code} {response.text}")
            return False
        return True
    except Exception as e:
        print(f"[EMAIL ERRO] {e}")
        return False


async def notify_cycle_opened(users: list, cycle_name: str, end_date: str):
    for user in users:
        body = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
          <div style="background:#6F12FF;padding:24px;border-radius:8px 8px 0 0">
            <h1 style="color:white;margin:0;font-size:20px">AVD 360° | Grupo Gestão</h1>
          </div>
          <div style="background:#f9f9f9;padding:24px;border-radius:0 0 8px 8px">
            <p>Olá, <strong>{user.name}</strong>!</p>
            <p>O ciclo de avaliação <strong>{cycle_name}</strong> foi aberto.</p>
            <p>Você tem avaliações pendentes. O prazo final é <strong>{end_date}</strong>.</p>
            <p>Acesse o sistema para responder suas avaliações.</p>
            <br>
            <p style="color:#888;font-size:12px">Grupo Gestão Consultoria</p>
          </div>
        </div>
        """
        await send_email([user.email], f"AVD 360° — Avaliação aberta: {cycle_name}", body)


async def notify_new_user(user_email: str, user_name: str, temp_password: str):
    body = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
      <div style="background:#6F12FF;padding:24px;border-radius:8px 8px 0 0">
        <h1 style="color:white;margin:0;font-size:20px">AVD 360° | Grupo Gestão</h1>
      </div>
      <div style="background:#f9f9f9;padding:24px;border-radius:0 0 8px 8px">
        <p>Olá, <strong>{user_name}</strong>!</p>
        <p>Sua conta no sistema AVD 360° foi criada.</p>
        <p><strong>E-mail:</strong> {user_email}<br>
        <strong>Senha temporária:</strong> {temp_password}</p>
        <p>Acesse o sistema e altere sua senha no primeiro login.</p>
        <br>
        <p style="color:#888;font-size:12px">Grupo Gestão Consultoria</p>
      </div>
    </div>
    """
    return await send_email([user_email], "AVD 360° — Bem-vindo ao sistema!", body)
