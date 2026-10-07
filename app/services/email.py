import base64
import os
from dataclasses import dataclass
from typing import List, Optional

import httpx


EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "false").lower() == "true"
BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "gp@grupogestao.co")
EMAIL_FROM_NAME = os.getenv("EMAIL_FROM_NAME", "AVD 360° | Grupo Gestão")
APP_URL = os.getenv("APP_URL", "https://avd360.onrender.com")

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"

# Google Apps Script web app deployed from the sender's Google account (gp@grupogestao.co).
# When set, it takes precedence over Brevo. See docs/apps_script_email.gs.
APPS_SCRIPT_URL = os.getenv("APPS_SCRIPT_URL", "")
APPS_SCRIPT_SECRET = os.getenv("APPS_SCRIPT_SECRET", "")
AUTO_EMAIL_READY = EMAIL_ENABLED and bool(APPS_SCRIPT_URL)


@dataclass
class EmailResult:
    ok: bool
    error: str = ""

    def __bool__(self):
        return self.ok


def _describe_error(status: int, body: dict) -> str:
    message = body.get("message") or body.get("code") or ""
    if status == 401:
        reason = "chave de API do Brevo inválida ou ausente (BREVO_API_KEY)"
    elif status == 402 or "credit" in message.lower():
        reason = "créditos de envio do Brevo esgotados"
    elif "sender" in message.lower():
        reason = f"remetente {EMAIL_FROM} não verificado no Brevo"
    else:
        reason = "o serviço de e-mail recusou o envio"
    return f"{reason} ({status}: {message})" if message else f"{reason} ({status})"


async def send_email(to: List[str], subject: str, body_html: str,
                     attachments: Optional[List[dict]] = None) -> EmailResult:
    """attachments: list of {"filename", "content" (bytes)}."""
    if not EMAIL_ENABLED:
        names = [a["filename"] for a in attachments or []]
        print(f"[EMAIL SIMULADO] Para: {to} | Assunto: {subject} | Anexos: {names}", flush=True)
        return EmailResult(True)
    if APPS_SCRIPT_URL:
        return await _send_via_apps_script(to, subject, body_html, attachments)
    if not BREVO_API_KEY:
        print("[EMAIL ERRO] BREVO_API_KEY não configurada", flush=True)
        return EmailResult(False, "chave de API do Brevo não configurada (BREVO_API_KEY)")

    payload = {
        "sender": {"email": EMAIL_FROM, "name": EMAIL_FROM_NAME},
        "to": [{"email": addr} for addr in to],
        "subject": subject,
        "htmlContent": body_html,
    }
    if attachments:
        payload["attachment"] = [
            {"content": base64.b64encode(a["content"]).decode("ascii"), "name": a["filename"]}
            for a in attachments
        ]
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                BREVO_API_URL,
                headers={"api-key": BREVO_API_KEY, "accept": "application/json"},
                json=payload,
            )
        if response.status_code >= 400:
            print(f"[EMAIL ERRO] {response.status_code} {response.text}", flush=True)
            try:
                body = response.json()
            except ValueError:
                body = {}
            return EmailResult(False, _describe_error(response.status_code, body))
        return EmailResult(True)
    except Exception as e:
        print(f"[EMAIL ERRO] {e}", flush=True)
        return EmailResult(False, f"não foi possível conectar ao serviço de e-mail ({e})")


async def _send_via_apps_script(to: List[str], subject: str, body_html: str,
                                attachments: Optional[List[dict]]) -> EmailResult:
    payload = {
        "secret": APPS_SCRIPT_SECRET,
        "to": ",".join(to),
        "subject": subject,
        "htmlBody": body_html,
        "name": EMAIL_FROM_NAME,
        "attachments": [
            {"name": a["filename"], "content": base64.b64encode(a["content"]).decode("ascii"),
             "mimeType": a.get("type", "application/pdf")}
            for a in attachments or []
        ],
    }
    try:
        # Apps Script answers a POST with a redirect to the actual response
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            response = await client.post(APPS_SCRIPT_URL, json=payload)
        try:
            body = response.json()
        except ValueError:
            print(f"[EMAIL ERRO] Apps Script {response.status_code} {response.text[:300]}", flush=True)
            return EmailResult(False, "o Google Apps Script não respondeu corretamente "
                                      "(confira se foi implantado com acesso para \"Qualquer pessoa\")")
        if not body.get("ok"):
            print(f"[EMAIL ERRO] Apps Script {body}", flush=True)
            return EmailResult(False, f"o Google recusou o envio ({body.get('error', 'erro desconhecido')})")
        return EmailResult(True)
    except Exception as e:
        print(f"[EMAIL ERRO] {e}", flush=True)
        return EmailResult(False, f"não foi possível conectar ao Google Apps Script ({e})")


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
            <p style="text-align:center;margin:24px 0">
              <a href="{APP_URL}" style="background:#6F12FF;color:white;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:600;display:inline-block">Acessar o sistema</a>
            </p>
            <br>
            <p style="color:#888;font-size:12px">Grupo Gestão Consultoria</p>
          </div>
        </div>
        """
        await send_email([user.email], f"AVD 360° — Avaliação aberta: {cycle_name}", body)


async def notify_cycle_deadline_reminder(users: list, cycle_name: str, end_date: str):
    for user in users:
        body = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
          <div style="background:#6F12FF;padding:24px;border-radius:8px 8px 0 0">
            <h1 style="color:white;margin:0;font-size:20px">AVD 360° | Grupo Gestão</h1>
          </div>
          <div style="background:#f9f9f9;padding:24px;border-radius:0 0 8px 8px">
            <p>Olá, <strong>{user.name}</strong>!</p>
            <p>⏰ O prazo do ciclo <strong>{cycle_name}</strong> está terminando em breve — <strong>{end_date}</strong>.</p>
            <p>Você ainda tem avaliações pendentes. Complete-as antes do encerramento.</p>
            <p style="text-align:center;margin:24px 0">
              <a href="{APP_URL}" style="background:#6F12FF;color:white;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:600;display:inline-block">Completar avaliações</a>
            </p>
            <br>
            <p style="color:#888;font-size:12px">Grupo Gestão Consultoria</p>
          </div>
        </div>
        """
        await send_email([user.email], f"AVD 360° — Prazo terminando: {cycle_name}", body)


async def notify_survey_deadline_reminder(users: list, survey_title: str, survey_key: str, closes_at: str):
    for user in users:
        body = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
          <div style="background:#6F12FF;padding:24px;border-radius:8px 8px 0 0">
            <h1 style="color:white;margin:0;font-size:20px">AVD 360° | Grupo Gestão</h1>
          </div>
          <div style="background:#f9f9f9;padding:24px;border-radius:0 0 8px 8px">
            <p>Olá, <strong>{user.name}</strong>!</p>
            <p>⏰ O prazo da pesquisa <strong>{survey_title}</strong> está terminando em breve — <strong>{closes_at}</strong> (horário de Brasília).</p>
            <p>Você ainda não respondeu. Responda antes do encerramento.</p>
            <p style="text-align:center;margin:24px 0">
              <a href="{APP_URL}/surveys/{survey_key}" style="background:#6F12FF;color:white;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:600;display:inline-block">Responder agora</a>
            </p>
            <br>
            <p style="color:#888;font-size:12px">Grupo Gestão Consultoria</p>
          </div>
        </div>
        """
        await send_email([user.email], f"AVD 360° — Prazo terminando: {survey_title}", body)


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
        <p style="text-align:center;margin:24px 0">
          <a href="{APP_URL}" style="background:#6F12FF;color:white;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:600;display:inline-block">Acessar o sistema</a>
        </p>
        <br>
        <p style="color:#888;font-size:12px">Grupo Gestão Consultoria</p>
      </div>
    </div>
    """
    return await send_email([user_email], "AVD 360° — Bem-vindo ao sistema!", body)


async def send_individual_report(user_email: str, user_name: str, cycle_name: str,
                                 pdf_bytes: bytes, filename: str):
    body = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
      <div style="background:#6F12FF;padding:24px;border-radius:8px 8px 0 0">
        <h1 style="color:white;margin:0;font-size:20px">AVD 360° | Grupo Gestão</h1>
      </div>
      <div style="background:#f9f9f9;padding:24px;border-radius:0 0 8px 8px">
        <p>Olá, <strong>{user_name}</strong>!</p>
        <p>O ciclo de avaliação <strong>{cycle_name}</strong> foi concluído.</p>
        <p>Seu relatório individual de desempenho está em anexo neste e-mail (PDF).</p>
        <p>Em caso de dúvidas, procure seu gestor ou o RH.</p>
        <br>
        <p style="color:#888;font-size:12px">Grupo Gestão Consultoria</p>
      </div>
    </div>
    """
    return await send_email(
        [user_email],
        f"AVD 360° — Seu relatório de avaliação: {cycle_name}",
        body,
        attachments=[{"filename": filename, "content": pdf_bytes}],
    )
