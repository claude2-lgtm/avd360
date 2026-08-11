# AVD 360° — Grupo Gestão Consultoria

Sistema interno de Avaliação de Desenvolvimento 360° para o Grupo Gestão Consultoria.

---

## 🚀 Como instalar e rodar (Windows)

### Pré-requisitos
- **Python 3.11+** — [Download](https://www.python.org/downloads/)
  - ⚠️ Durante a instalação, marque **"Add Python to PATH"**

### Instalação (só precisa fazer uma vez)
1. Extraia o arquivo ZIP em uma pasta (ex: `C:\AVD360\`)
2. Clique duas vezes em **`instalar.bat`**
3. Aguarde a instalação das dependências

### Iniciar o sistema
1. Clique duas vezes em **`iniciar.bat`**
2. O navegador abrirá automaticamente em `http://localhost:8000`

---

## 🔐 Acesso padrão

| Campo  | Valor                       |
|--------|-----------------------------|
| E-mail | admin@grupogestao.com.br    |
| Senha  | Admin@2024                  |

> **Altere a senha no primeiro acesso em: Meu Perfil → Alterar senha**

---

## 📋 Funcionalidades

### Administrador
- **Dashboard** — visão geral, progresso do ciclo, pendentes por usuário
- **Colaboradores** — cadastro, edição, senha temporária automática, remoção
- **Ciclos de Avaliação** — criar, configurar designações, ativar, encerrar
- **Designações** — automáticas (por departamento) + manuais
- **Competências** — editar grupos e itens por cargo
- **Relatórios** — visualização + download em PDF por colaborador

### Colaborador
- **Minhas Avaliações** — lista do ciclo ativo com progresso
- **Formulário de avaliação** — estrelas 1-5 com descrição por competência
- **Rascunho automático** — salvar progresso antes de enviar
- **Bloqueio após submissão** — não permite editar avaliação enviada

---

## 🏗 Arquitetura

```
avd360/
├── main.py                   ← Entrada da aplicação
├── requirements.txt
├── .env                      ← Configurações (email, secret key)
├── avd360.db                 ← Banco SQLite (criado automaticamente)
└── app/
    ├── models/
    │   └── database.py       ← Modelos ORM (SQLAlchemy)
    ├── services/
    │   ├── auth.py           ← JWT, hashing de senha
    │   ├── seed.py           ← Dados iniciais (competências, admin)
    │   ├── email.py          ← Notificações por e-mail
    │   ├── pdf.py            ← Geração de relatórios PDF
    │   └── reports.py        ← Agregação de dados dos relatórios
    ├── routers/
    │   ├── auth.py           ← Login / Logout
    │   ├── dashboard.py      ← Dashboard admin e colaborador
    │   ├── users.py          ← CRUD de usuários + perfil
    │   ├── cycles.py         ← Ciclos e designações
    │   ├── evaluations.py    ← Formulário, submissão, relatórios
    │   └── competencies.py   ← Gestão de competências
    └── templates/            ← HTML Jinja2
```

---

## 🎯 Lógica de designações

| Departamento | Regra                                          |
|-------------|------------------------------------------------|
| Projetos    | Manual pelo admin                              |
| Outros      | Automático: todos avaliam todos do departamento |
| Self        | Autoavaliação gerada para todos automaticamente |

O admin pode adicionar/remover designações manualmente em qualquer caso.

---

## 📊 Competências por cargo

| Cargo                          | Grupos                                         |
|-------------------------------|------------------------------------------------|
| Consultor de Projetos          | Técnicas, Compromisso, Execução, Postura, Resultado |
| Coordenador de Projetos        | Técnicas, Compromisso, Comunicação, Postura, Resultado |
| Assessor Comercial/Gestão      | Técnicas, Compromisso, Comunicação, Engajamento, Postura |
| Diretoria + Presidência        | Compromisso, Comunicação, Execução, Postura, Resultado |

---

## 📧 Configurar e-mail (opcional)

O envio é feito via API do [SendGrid](https://sendgrid.com) (não usa SMTP direto, pois muitas hospedagens como o Render bloqueiam as portas SMTP tradicionais).

Edite o arquivo `.env` (ou as Environment Variables da hospedagem):
```
EMAIL_ENABLED=true
SENDGRID_API_KEY=SG.xxxxxxxxxxxx
EMAIL_FROM=noreply@grupogestao.com.br
```

Passos:
1. Crie uma conta em [sendgrid.com](https://sendgrid.com).
2. Em **Settings → Sender Authentication → Single Sender Verification**, cadastre o e-mail remetente (ex: `gp@grupogestao.co`) e confirme clicando no link recebido na caixa de entrada dele.
3. Em **Settings → API Keys**, gere uma chave com permissão de "Mail Send" e use como `SENDGRID_API_KEY`.
4. `EMAIL_FROM` deve ser exatamente o e-mail verificado no passo 2.

---

## 🔄 Fluxo de um ciclo

```
1. Admin cria ciclo (rascunho)
2. Admin configura designações (auto + ajustes manuais)
3. Admin ativa o ciclo → colaboradores notificados por e-mail
4. Colaboradores preenchem avaliações (estrelas 1-5 + comentários)
5. Admin acompanha progresso no dashboard
6. Admin acessa relatórios individuais (PDF) a qualquer momento
7. Admin encerra o ciclo
8. Histórico preservado para comparação futura
```

---

## ⚙️ Tecnologias

- **Backend:** FastAPI + Python 3.11
- **Banco:** SQLite (zero configuração)
- **Frontend:** Jinja2 + HTMX
- **PDF:** ReportLab
- **Autenticação:** JWT (cookie httponly)

---

*Versão 1.0 — Grupo Gestão Consultoria © 2025*
