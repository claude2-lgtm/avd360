# Seed inicial dos formulários FIB e PCO. Depois de criados no banco pela
# primeira vez, o admin pode editar/adicionar/remover perguntas pela interface
# de "Gerenciar Formulários" — este arquivo só serve de ponto de partida.

SCALE_LABELS = {
    1: "Nada satisfeito",
    2: "Pouco satisfeito",
    3: "Satisfeito",
    4: "Muito satisfeito",
    5: "Extremamente satisfeito",
}

SEED_FORMS = [
    {
        "key": "fib",
        "title": "FIB — Felicidade Interna Bruta",
        "description": "Pesquisa sobre satisfação, motivação e bem-estar no Grupo Gestão.",
        "questions": [
            {"group": "Satisfação Geral e Engajamento", "type": "scale", "text": "O quão satisfeito você está com o seu trabalho no geral?"},
            {"group": "Satisfação Geral e Engajamento", "type": "scale", "text": "Você se sente motivado?"},
            {"group": "Satisfação Geral e Engajamento", "type": "text", "text": "O que te motiva a continuar?"},
            {"group": "Satisfação Geral e Engajamento", "type": "scale", "text": "O seu trabalho vale a pena?"},
            {"group": "Satisfação Geral e Engajamento", "type": "scale", "text": "Você se sente orgulhoso de fazer parte do Grupo Gestão?"},
            {"group": "Satisfação Geral e Engajamento", "type": "scale", "text": "Você se sente alinhado com a missão e os valores do Grupo Gestão?"},
            {"group": "Equilíbrio Trabalho-Vida", "type": "scale", "text": "O quão satisfeito você está com o equilíbrio entre o tempo que você gasta no seu trabalho e o tempo que você despende em outros aspectos da sua vida?"},
            {"group": "Ambiente de Trabalho e Relações", "type": "scale", "text": "Você tem pessoas de confiança dentro do GG?"},
            {"group": "Ambiente de Trabalho e Relações", "type": "scale", "text": "Você sente que há colaboração e respeito no ambiente de trabalho?"},
            {"group": "Ambiente de Trabalho e Relações", "type": "scale", "text": "Você sente que pode ser você mesmo dentro do GG?"},
            {"group": "Desenvolvimento e Aprendizado", "type": "scale", "text": "Você conseguiu absorver e aplicar os conhecimentos adquiridos em treinamentos no dia a dia?"},
            {"group": "Sentimentos e Emoções", "type": "scale", "text": "Você se sente frustrado?"},
            {"group": "Sentimentos e Emoções", "type": "scale", "text": "O seu trabalho é estressante?"},
            {"group": "Sugestões para Melhoria", "type": "text", "text": "O que te faria mais feliz hoje dentro do GG?"},
            {"group": "Sugestões para Melhoria", "type": "text", "text": "O que faria Gestão ficar mais próxima da sua área esse semestre?"},
        ],
    },
    {
        "key": "pco",
        "title": "PCO — Pesquisa de Clima Organizacional",
        "description": "Pesquisa sobre eficácia, comunicação, feedback e desenvolvimento no Grupo Gestão.",
        "questions": [
            {"group": "Eficácia e Eficiência", "type": "scale", "text": "As metas e objetivos definidos para minha área são claros."},
            {"group": "Eficácia e Eficiência", "type": "scale", "text": "A carga de trabalho é adequada e gerenciável."},
            {"group": "Comunicação", "type": "scale", "text": "A comunicação entre as diferentes áreas da empresa é eficaz."},
            {"group": "Comunicação", "type": "scale", "text": "Sinto que posso me comunicar facilmente com meus superiores."},
            {"group": "Feedback e Melhoria Contínua", "type": "scale", "text": "Recebo feedback regular sobre meu desempenho."},
            {"group": "Feedback e Melhoria Contínua", "type": "scale", "text": "Minhas sugestões para melhorias são valorizadas."},
            {"group": "Inovação e Aprendizado", "type": "scale", "text": "Tive oportunidades de participar de treinamentos que agregam valor."},
            {"group": "Inovação e Aprendizado", "type": "scale", "text": "Sinto-me encorajado a propor novas ideias no meu trabalho."},
            {"group": "Inovação e Aprendizado", "type": "scale", "text": "Recebo apoio para desenvolver minhas habilidades."},
            {"group": "Resultados Gerais", "type": "scale", "text": "Sinto que meu trabalho tem um impacto positivo nos resultados gerais da empresa."},
            {"group": "Sugestões para Melhoria", "type": "text", "text": "Quais melhorias você sugeriria para os processos e a eficiência no seu trabalho?"},
        ],
    },
]


def seed_surveys(db):
    """Cria FIB e PCO no banco na primeira vez que o app roda. Não sobrescreve
    formulários já existentes (o admin pode ter editado as perguntas)."""
    from app.models.database import SurveyForm, SurveyQuestion

    for form_data in SEED_FORMS:
        existing = db.query(SurveyForm).filter(SurveyForm.key == form_data["key"]).first()
        if existing:
            continue
        form = SurveyForm(
            key=form_data["key"],
            title=form_data["title"],
            description=form_data["description"],
            is_active=True,
        )
        db.add(form)
        db.flush()  # get form.id
        for i, q in enumerate(form_data["questions"]):
            db.add(SurveyQuestion(
                form_id=form.id,
                group_name=q["group"],
                text=q["text"],
                type=q["type"],
                order=i,
            ))
    db.commit()


def current_period() -> str:
    """Retorna o período semestral atual, ex: '2026-1' (Jan-Jun) ou '2026-2' (Jul-Dez)."""
    from datetime import datetime
    now = datetime.utcnow()
    half = 1 if now.month <= 6 else 2
    return f"{now.year}-{half}"
