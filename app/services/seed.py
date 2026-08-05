import json
from sqlalchemy.orm import Session
from app.models.database import (
    CompetencyGroup, Competency, User, UserRole
)
from app.services.auth import get_password_hash

# ── Competency definitions ──────────────────────────────────────────────────
# target_positions: list of position names this group applies to.
# Empty list = applies to all (used as fallback).

COMPETENCY_DATA = [
    # ── CONSULTOR DE PROJETOS ──────────────────────────────────────────────
    {
        "group": "Competências Técnicas",
        "positions": ["Consultor de Projetos"],
        "order": 1,
        "items": [
            {
                "name": "Capacidade analítica",
                "weight": 1,
                "order": 1,
                "description": (
                    "Avalie a habilidade do consultor em interpretar dados, identificar problemas e propor "
                    "soluções estruturadas para os projetos, considerando: análise crítica (questiona premissas "
                    "e busca dados concretos); estruturação de problemas (divide desafios complexos em partes "
                    "gerenciáveis); soluções baseadas em evidências."
                ),
            }
        ],
    },
    {
        "group": "Compromisso",
        "positions": ["Consultor de Projetos"],
        "order": 2,
        "items": [
            {
                "name": "Busca trazer melhorias na área",
                "weight": 1,
                "order": 1,
                "description": (
                    "Avalie a proatividade do membro em identificar e propor melhorias para os processos da área, "
                    "mesmo que pequenas. Considere: iniciativa para sugerir mudanças (não espera ser solicitado); "
                    "impacto das contribuições (seja em eficiência, qualidade ou organização); visão macro "
                    "(entende que melhorias na área beneficiam todos os projetos)."
                ),
            },
            {
                "name": "Compromisso com os ritos da área",
                "weight": 1,
                "order": 2,
                "description": (
                    "Avalie se o membro segue os processos e rotinas estabelecidos pela sua área "
                    "(ex.: reuniões, templates de documentos, fluxos de aprovação, reports, dailys). "
                    "Considere: adesão aos ritos (participa e respeita os processos definidos)."
                ),
            },
            {
                "name": "Clareza e assertividade na comunicação",
                "weight": 1,
                "order": 3,
                "description": (
                    "Avalie a capacidade do membro de se comunicar de forma eficaz, tanto internamente "
                    "quanto externamente, observando: clareza na transmissão de informações; escuta ativa; "
                    "respeito ao opinar; adaptação do linguajar ao contexto."
                ),
            },
            {
                "name": "Compromisso com os feeds — Recebidos e enviados",
                "weight": 1,
                "order": 4,
                "description": (
                    "Avalie o envolvimento do membro com a cultura de feedback contínuo: maturidade para receber "
                    "feeds (aceita críticas sem justificativas excessivas); compromisso em dar feeds; qualidade do "
                    "feedback (construtivo, específico e focado no desenvolvimento do outro)."
                ),
            },
            {
                "name": "Relacionamento com o cliente",
                "weight": 1,
                "order": 5,
                "description": (
                    "Avalie a capacidade de construir relações profissionais positivas: comunicação clara; "
                    "gestão de expectativas; empatia (entende e responde às necessidades do cliente)."
                ),
            },
        ],
    },
    {
        "group": "Execução",
        "positions": ["Consultor de Projetos"],
        "order": 3,
        "items": [
            {
                "name": "Conhecimento do escopo",
                "weight": 1,
                "order": 1,
                "description": (
                    "Avalie o domínio que o membro tem/adquiriu do escopo ao longo do projeto. Considere: "
                    "entendimento completo (sabe explicar objetivos, entregáveis e limitações); alinhamento "
                    "constante; gestão de mudanças (identifica e comunica desvios no escopo)."
                ),
            }
        ],
    },
    {
        "group": "Postura",
        "positions": ["Consultor de Projetos"],
        "order": 4,
        "items": [
            {
                "name": "Postura nas reuniões",
                "weight": 1,
                "order": 1,
                "description": (
                    "Avalie o membro quanto à postura profissional durante reuniões: câmera ligada (quando "
                    "aplicável); vestimenta adequada; linguajar claro e profissional; postura atenta e participativa."
                ),
            },
            {
                "name": "Proatividade",
                "weight": 1,
                "order": 2,
                "description": (
                    "Avalie a iniciativa do membro para além das tarefas obrigatórias: antecipação (identifica "
                    "necessidades antes de ser solicitado); solução de gaps; engajamento em discussões e ideias."
                ),
            },
        ],
    },
    {
        "group": "Resultado",
        "positions": ["Consultor de Projetos"],
        "order": 5,
        "items": [
            {
                "name": "Entregas e qualidade dos projetos",
                "weight": 1,
                "order": 1,
                "description": (
                    "Avalie a excelência técnica e pontualidade nas entregas: padrão de qualidade; "
                    "cumprimento de etapas; melhoria contínua. Cuidado com o conteúdo: validações, "
                    "Padrão da Marca, ortografia, prazo."
                ),
            }
        ],
    },
    # ── COORDENADOR DE PROJETOS ────────────────────────────────────────────
    {
        "group": "Competências Técnicas",
        "positions": ["Coordenador de Projetos"],
        "order": 1,
        "items": [
            {
                "name": "Planejamento do projeto",
                "weight": 1,
                "order": 1,
                "description": (
                    "Avalie a capacidade de estruturar a execução: detalhamento (divide macro-atividades em "
                    "tarefas executáveis); antecipação de riscos (prevê e mitiga obstáculos); ajuste dinâmico "
                    "(replaneja conforme necessidades surgem)."
                ),
            }
        ],
    },
    {
        "group": "Compromisso",
        "positions": ["Coordenador de Projetos"],
        "order": 2,
        "items": [
            {
                "name": "Busca trazer melhorias na área",
                "weight": 1,
                "order": 1,
                "description": (
                    "Avalie a proatividade do membro em identificar e propor melhorias para os processos da área, "
                    "mesmo que pequenas. Iniciativa, impacto das contribuições e visão macro."
                ),
            },
            {
                "name": "Compromisso com os ritos da área",
                "weight": 1,
                "order": 2,
                "description": (
                    "Avalie se o membro segue os processos e rotinas estabelecidos pela sua área: "
                    "adesão aos ritos, participação e respeito aos processos definidos."
                ),
            },
            {
                "name": "Cumprimento de prazos",
                "weight": 1,
                "order": 3,
                "description": (
                    "Avalie a pontualidade na entrega de tarefas: responsabilidade (entrega dentro do prazo "
                    "ou comunica atrasos com antecedência); priorização; impacto no time."
                ),
            },
            {
                "name": "Qualidade e compromisso nas validações",
                "weight": 1,
                "order": 4,
                "description": (
                    "Avalie a qualidade nas validações: revisões sistemáticas dentro do prazo; padronização; "
                    "documentação (registra aprovações formalmente); tempo de validação."
                ),
            },
        ],
    },
    {
        "group": "Comunicação",
        "positions": ["Coordenador de Projetos"],
        "order": 3,
        "items": [
            {
                "name": "Clareza e assertividade na comunicação",
                "weight": 1,
                "order": 1,
                "description": (
                    "Avalie a comunicação eficaz interna e externa: clareza, escuta ativa, respeito ao opinar, "
                    "adaptação do linguajar ao contexto."
                ),
            },
            {
                "name": "Compromisso com os feeds — Recebidos e enviados",
                "weight": 1,
                "order": 2,
                "description": (
                    "Avalie o envolvimento com a cultura de feedback contínuo: maturidade para receber, "
                    "qualidade ao dar feedbacks construtivos e específicos."
                ),
            },
        ],
    },
    {
        "group": "Postura",
        "positions": ["Coordenador de Projetos"],
        "order": 4,
        "items": [
            {
                "name": "Gestão de equipes",
                "weight": 1,
                "order": 1,
                "description": (
                    "Avalie a liderança operacional: delegação eficaz (distribui tarefas conforme habilidades); "
                    "motivação (mantém o time engajado); mediação de conflitos (resolve atritos construtivamente)."
                ),
            },
            {
                "name": "Postura de líder",
                "weight": 1,
                "order": 2,
                "description": (
                    "Avalie comportamentos de liderança: exemplo (age como modelo); visão estratégica "
                    "(pensa no longo prazo); tomada de decisão (assume responsabilidades difíceis)."
                ),
            },
            {
                "name": "Postura nas reuniões",
                "weight": 1,
                "order": 3,
                "description": (
                    "Câmera ligada, vestimenta adequada, linguajar profissional, postura atenta e participativa."
                ),
            },
            {
                "name": "Proatividade",
                "weight": 1,
                "order": 4,
                "description": (
                    "Antecipação de necessidades, solução de gaps, engajamento em discussões e proposição de ideias."
                ),
            },
        ],
    },
    {
        "group": "Resultado",
        "positions": ["Coordenador de Projetos"],
        "order": 5,
        "items": [
            {
                "name": "Resolução de problemas",
                "weight": 1,
                "order": 1,
                "description": (
                    "Avalie a capacidade de lidar com desafios complexos: análise crítica (entende causas raiz); "
                    "viabilidade das soluções; tomada de decisão com segurança e dados."
                ),
            }
        ],
    },
    # ── ASSESSOR COMERCIAL + ASSESSOR DE GESTÃO ────────────────────────────
    {
        "group": "Competências Técnicas",
        "positions": ["Assessor Comercial", "Assessor de Gestão"],
        "order": 1,
        "items": [
            {
                "name": "Postura resolutiva",
                "weight": 1,
                "order": 1,
                "description": (
                    "Capacidade de identificar oportunidades de melhoria, propor soluções criativas e agir de "
                    "forma autônoma frente a desafios, contribuindo ativamente com ideias inovadoras."
                ),
            }
        ],
    },
    {
        "group": "Compromisso",
        "positions": ["Assessor Comercial", "Assessor de Gestão"],
        "order": 2,
        "items": [
            {
                "name": "Busca trazer melhorias na área",
                "weight": 1,
                "order": 1,
                "description": (
                    "Proatividade em identificar e propor melhorias para processos da área: iniciativa, "
                    "impacto das contribuições e visão macro."
                ),
            },
            {
                "name": "Compromisso com os ritos da área",
                "weight": 1,
                "order": 2,
                "description": (
                    "Adesão aos processos e rotinas estabelecidos: reuniões, templates, fluxos de aprovação, "
                    "reports, dailys."
                ),
            },
            {
                "name": "Cumprimento de prazos",
                "weight": 1,
                "order": 3,
                "description": (
                    "Pontualidade nas entregas: responsabilidade, priorização e impacto no time e clientes."
                ),
            },
        ],
    },
    {
        "group": "Comunicação",
        "positions": ["Assessor Comercial", "Assessor de Gestão"],
        "order": 3,
        "items": [
            {
                "name": "Clareza e assertividade na comunicação",
                "weight": 1,
                "order": 1,
                "description": (
                    "Comunicação eficaz interna e externa: clareza, escuta ativa, respeito ao opinar, "
                    "adaptação do linguajar. Comercial: uso de rapport."
                ),
            },
            {
                "name": "Compromisso com os feeds — Recebidos e enviados",
                "weight": 1,
                "order": 2,
                "description": (
                    "Cultura de feedback contínuo: maturidade para receber, qualidade ao dar feedbacks."
                ),
            },
        ],
    },
    {
        "group": "Engajamento",
        "positions": ["Assessor Comercial", "Assessor de Gestão"],
        "order": 4,
        "items": [
            {
                "name": "Colaboração com outras áreas",
                "weight": 1,
                "order": 1,
                "description": (
                    "Abertura para apoiar outras diretorias em iniciativas que envolvam inovação, contribuindo "
                    "com visão criativa e soluções que agreguem valor ao coletivo."
                ),
            },
            {
                "name": "Participação ativa durante as reuniões de inovação",
                "weight": 1,
                "order": 2,
                "description": (
                    "Engajamento nas reuniões da área: ideias, sugestões, feedbacks construtivos e alinhamento "
                    "com os objetivos."
                ),
            },
        ],
    },
    {
        "group": "Postura",
        "positions": ["Assessor Comercial", "Assessor de Gestão"],
        "order": 5,
        "items": [
            {
                "name": "Postura nas reuniões",
                "weight": 1,
                "order": 1,
                "description": (
                    "Câmera ligada, vestimenta adequada, linguajar profissional, postura atenta e participativa."
                ),
            },
            {
                "name": "Proatividade",
                "weight": 1,
                "order": 2,
                "description": (
                    "Antecipação, solução de gaps e engajamento em discussões e ideias."
                ),
            },
        ],
    },
    # ── DIRETORIA + PRESIDÊNCIA ────────────────────────────────────────────
    {
        "group": "Compromisso",
        "positions": ["Diretor Comercial", "Diretor de Projetos", "Diretor de Gestão", "Presidente"],
        "order": 1,
        "items": [
            {
                "name": "Busca trazer melhorias na área",
                "weight": 1,
                "order": 1,
                "description": (
                    "Proatividade em identificar e propor melhorias: iniciativa, impacto das contribuições, "
                    "visão macro."
                ),
            },
            {
                "name": "Compromisso com os ritos da área",
                "weight": 1,
                "order": 2,
                "description": (
                    "Adesão aos processos e rotinas: reuniões, templates, fluxos de aprovação, reports, dailys."
                ),
            },
            {
                "name": "Criação e acompanhamento de planos de ação",
                "weight": 1,
                "order": 3,
                "description": (
                    "Implementação de melhorias: detecção de gaps, ações mensuráveis, follow-up com resultados "
                    "das ações implementadas."
                ),
            },
            {
                "name": "Cumprimento de prazos",
                "weight": 1,
                "order": 4,
                "description": (
                    "Pontualidade nas entregas: responsabilidade, priorização e impacto no time."
                ),
            },
            {
                "name": "Preocupação com os indicadores",
                "weight": 1,
                "order": 5,
                "description": (
                    "Uso de dados na gestão: análise periódica, comunicação visual dos resultados com o time."
                ),
            },
        ],
    },
    {
        "group": "Comunicação",
        "positions": ["Diretor Comercial", "Diretor de Projetos", "Diretor de Gestão", "Presidente"],
        "order": 2,
        "items": [
            {
                "name": "Clareza e assertividade na comunicação",
                "weight": 1,
                "order": 1,
                "description": (
                    "Comunicação eficaz interna e externa: clareza, escuta ativa, respeito ao opinar, "
                    "adaptação do linguajar."
                ),
            },
            {
                "name": "Compromisso com os feeds — Recebidos e enviados",
                "weight": 1,
                "order": 2,
                "description": (
                    "Cultura de feedback contínuo: maturidade para receber, qualidade ao dar feedbacks."
                ),
            },
            {
                "name": "Relacionamento institucional",
                "weight": 1,
                "order": 3,
                "description": (
                    "Construção de parcerias externas: networking ativo, imagem profissional e "
                    "parcerias estratégicas mutuamente benéficas."
                ),
            },
        ],
    },
    {
        "group": "Execução",
        "positions": ["Diretor Comercial", "Diretor de Projetos", "Diretor de Gestão", "Presidente"],
        "order": 3,
        "items": [
            {
                "name": "Cumprimento dos objetivos empresariais",
                "weight": 1,
                "order": 1,
                "description": (
                    "Atingimento de metas estratégicas: alinhamento com o que impacta a empresa, "
                    "adaptação de rotas e prestação de contas ao time."
                ),
            }
        ],
    },
    {
        "group": "Postura",
        "positions": ["Diretor Comercial", "Diretor de Projetos", "Diretor de Gestão", "Presidente"],
        "order": 4,
        "items": [
            {
                "name": "Postura nas reuniões",
                "weight": 1,
                "order": 1,
                "description": (
                    "Câmera ligada, vestimenta adequada, linguajar profissional, postura atenta e participativa."
                ),
            },
            {
                "name": "Proatividade",
                "weight": 1,
                "order": 2,
                "description": (
                    "Antecipação, solução de gaps e engajamento ativo em discussões e proposição de ideias."
                ),
            },
        ],
    },
    {
        "group": "Resultado",
        "positions": ["Diretor Comercial", "Diretor de Projetos", "Diretor de Gestão", "Presidente"],
        "order": 5,
        "items": [
            {
                "name": "Resolução de problemas",
                "weight": 1,
                "order": 1,
                "description": (
                    "Capacidade de lidar com desafios complexos: análise crítica, viabilidade das soluções, "
                    "tomada de decisão com segurança e dados."
                ),
            }
        ],
    },
]


def seed_competencies(db: Session):
    """Insert all competency groups and items if not already seeded."""
    if db.query(CompetencyGroup).count() > 0:
        return

    for entry in COMPETENCY_DATA:
        group = CompetencyGroup(
            name=entry["group"],
            target_positions=json.dumps(entry["positions"], ensure_ascii=False),
            order=entry["order"],
            is_active=True,
        )
        db.add(group)
        db.flush()

        for item in entry["items"]:
            comp = Competency(
                group_id=group.id,
                name=item["name"],
                description=item["description"],
                weight=item["weight"],
                order=item["order"],
                is_active=True,
            )
            db.add(comp)

    db.commit()


def seed_admin(db: Session):
    """Create default admin if none exists."""
    from app.models.database import UserRole
    admin = db.query(User).filter(User.role == UserRole.admin).first()
    if admin:
        return

    admin = User(
        name="Administrador",
        email="admin@grupogestao.com.br",
        hashed_password=get_password_hash("Admin@2024"),
        role=UserRole.admin,
        department="Gestão",
        position="Diretor de Gestão",
        is_active=True,
    )
    db.add(admin)
    db.commit()
    print("✓ Admin criado: admin@grupogestao.com.br / Admin@2024")


# (name, email, password) — password is the collaborator's first name.
# department/position left blank; an admin assigns those later via /users.
COLLABORATORS_SEED = [
    ("Allegra", "allegra@grupogestao.co", "allegra"),
    ("Amin", "amin@grupogestao.co", "amin"),
    ("Ana Ulhoa", "anaulhoa@grupogestao.co", "ana"),
    ("Ana Brentano", "anabrentano@grupogestao.co", "ana"),
    ("Bernardo Valentim", "bernardovalentim@grupogestao.co", "bernardo"),
    ("Cecília", "cecilia@grupogestao.co", "cecilia"),
    ("Davi Mescouto", "davimescouto@grupogestao.co", "davi"),
    ("Davi Takami", "davitakami@grupogestao.co", "davi"),
    ("Eduardo Breide", "eduardobreide@grupogestao.co", "eduardo"),
    ("Enzo Weyne", "enzoweyne@grupogestao.co", "enzo"),
    ("Enzo Marques", "enzomarques@grupogestao.co", "enzo"),
    ("Evelyn", "evelyn@grupogestao.co", "evelyn"),
    ("Felipe Charbel", "felipecharbel@grupogestao.co", "felipe"),
    ("Felipe Pohl", "felipepohl@grupogestao.co", "felipe"),
    ("Gabriel Gadelha", "gabrielgadelha@grupogestao.co", "gabriel"),
    ("Gabriel Linhares", "gabriellinhares@grupogestao.co", "gabriel"),
    ("Gabriel Ávila", "gabrielavila@grupogestao.co", "gabriel"),
    ("Gustavo Meira", "gustavomeira@grupogestao.co", "gustavo"),
    ("Isabela Cabral", "isabelacabral@grupogestao.co", "isabela"),
    ("Isabella Moreira", "isabellamoreira@grupogestao.co", "isabella"),
    ("Karen", "karen@grupogestao.co", "karen"),
    ("Laura", "laura@grupogestao.co", "laura"),
    ("Lavínia Ferraz", "laviniaferraz@grupogestao.co", "lavinia"),
    ("Louise", "louise@grupogestao.co", "louise"),
    ("Lucas Lambach", "lucaslambach@grupogestao.co", "lucas"),
    ("Luiz Gustavo", "luizgustavo@grupogestao.co", "luizgustavo"),
    ("Manuella", "manuella@grupogestao.co", "manuella"),
    ("Marcos Furtado", "marcosfurtado@grupogestao.co", "marcos"),
    ("Maria Eduarda Passos", "mariaeduardapassos@grupogestao.co", "mariaeduarda"),
    ("Maria Eduarda Sollero", "mariaeduardasollero@grupogestao.co", "mariaeduarda"),
    ("Marina Mancebo", "marinamancebo@grupogestao.co", "marina"),
    ("Marina Medeiros", "marinamedeiros@grupogestao.co", "marina"),
    ("Mateus Barcelos", "mateusbarcelos@grupogestao.co", "mateus"),
    ("Nicole Vollstedt", "nicolevollstedt@grupogestao.co", "nicole"),
    ("Oto", "oto@grupogestao.co", "oto"),
    ("Pedro Aquino", "pedroaquino@grupogestao.co", "pedro"),
    ("Rafael Leivas", "rafaelleivas@grupogestao.co", "rafael"),
    ("Rafael", "rafael@grupogestao.co", "rafael"),
    ("Rafaela Gutierrez", "rafaelagutierrez@grupogestao.co", "rafaela"),
    ("Rafaela", "rafaela@grupogestao.co", "rafaela"),
    ("Renato", "renato@grupogestao.co", "renato"),
    ("Samuel", "samuel@grupogestao.co", "samuel"),
    ("Tiago Zamboni", "tiagozamboni@grupogestao.co", "tiago"),
]


def seed_collaborators(db: Session):
    """Create the initial batch of collaborator accounts if missing."""
    from app.models.database import UserRole
    for name, email, password in COLLABORATORS_SEED:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            continue
        db.add(User(
            name=name,
            email=email,
            hashed_password=get_password_hash(password),
            role=UserRole.collaborator,
            is_active=True,
        ))
    db.commit()


def run_seed(db: Session):
    seed_competencies(db)
    seed_admin(db)
    seed_collaborators(db)
