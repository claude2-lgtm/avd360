from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Boolean,
    DateTime, Text, ForeignKey, Enum as SAEnum, text
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.sql import func
import enum
import os

# Use PostgreSQL on Railway, SQLite locally
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./avd360.db")

# Railway provides postgres:// but SQLAlchemy needs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class UserRole(str, enum.Enum):
    admin = "admin"
    collaborator = "collaborator"


class CycleStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    closed = "closed"


class EvaluationStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    submitted = "submitted"


DEPARTMENTS = ["Comercial", "Gestao", "Projetos", "Presidencia"]

POSITIONS = [
    "Consultor de Projetos",
    "Assessor Comercial",
    "Assessor de Gestao",
    "Coordenador de Projetos",
    "Diretor Comercial",
    "Diretor de Projetos",
    "Diretor de Gestao",
    "Presidente",
]

DIRECTOR_POSITIONS = [
    "Diretor Comercial",
    "Diretor de Projetos",
    "Diretor de Gestao",
    "Presidente",
]


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    email = Column(String(200), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(SAEnum(UserRole), default=UserRole.collaborator, nullable=False)
    department = Column(String(100), nullable=True)
    position = Column(String(100), nullable=True)
    manager_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    temp_password = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    manager = relationship("User", remote_side=[id], backref="subordinates")
    evaluations_given = relationship("Evaluation", foreign_keys="Evaluation.evaluator_id", back_populates="evaluator")
    evaluations_received = relationship("Evaluation", foreign_keys="Evaluation.evaluatee_id", back_populates="evaluatee")


class EvaluationCycle(Base):
    __tablename__ = "evaluation_cycles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(SAEnum(CycleStatus), default=CycleStatus.draft, nullable=False)
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    created_by = relationship("User")
    evaluations = relationship("Evaluation", back_populates="cycle", cascade="all, delete-orphan")
    assignments = relationship("EvaluationAssignment", back_populates="cycle", cascade="all, delete-orphan")


class EvaluationAssignment(Base):
    __tablename__ = "evaluation_assignments"

    id = Column(Integer, primary_key=True, index=True)
    cycle_id = Column(Integer, ForeignKey("evaluation_cycles.id"), nullable=False)
    evaluator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    evaluatee_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_self = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())

    cycle = relationship("EvaluationCycle", back_populates="assignments")
    evaluator = relationship("User", foreign_keys=[evaluator_id])
    evaluatee = relationship("User", foreign_keys=[evaluatee_id])


class CompetencyGroup(Base):
    __tablename__ = "competency_groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    target_positions = Column(Text, nullable=True)
    order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())

    competencies = relationship("Competency", back_populates="group", order_by="Competency.order")


class Competency(Base):
    __tablename__ = "competencies"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("competency_groups.id"), nullable=False)
    name = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)
    weight = Column(Float, default=1.0)
    order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    group = relationship("CompetencyGroup", back_populates="competencies")
    answers = relationship("EvaluationAnswer", back_populates="competency")


class Evaluation(Base):
    __tablename__ = "evaluations"

    id = Column(Integer, primary_key=True, index=True)
    cycle_id = Column(Integer, ForeignKey("evaluation_cycles.id"), nullable=False)
    evaluator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    evaluatee_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_self_evaluation = Column(Boolean, default=False)
    status = Column(SAEnum(EvaluationStatus), default=EvaluationStatus.pending)
    general_observations = Column(Text, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    cycle = relationship("EvaluationCycle", back_populates="evaluations")
    evaluator = relationship("User", foreign_keys=[evaluator_id], back_populates="evaluations_given")
    evaluatee = relationship("User", foreign_keys=[evaluatee_id], back_populates="evaluations_received")
    answers = relationship("EvaluationAnswer", back_populates="evaluation", cascade="all, delete-orphan")


class EvaluationAnswer(Base):
    __tablename__ = "evaluation_answers"

    id = Column(Integer, primary_key=True, index=True)
    evaluation_id = Column(Integer, ForeignKey("evaluations.id"), nullable=False)
    competency_id = Column(Integer, ForeignKey("competencies.id"), nullable=False)
    score = Column(Float, nullable=True)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    evaluation = relationship("Evaluation", back_populates="answers")
    competency = relationship("Competency", back_populates="answers")


class SurveyQuestionType(str, enum.Enum):
    scale = "scale"
    rating10 = "rating10"
    text = "text"


class SurveyForm(Base):
    __tablename__ = "survey_forms"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(50), unique=True, nullable=False, index=True)  # slug, ex: "fib"
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    opens_at = Column(DateTime, nullable=True)   # UTC; convertido de horário de Brasília
    closes_at = Column(DateTime, nullable=True)  # UTC; convertido de horário de Brasília
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    questions = relationship(
        "SurveyQuestion", back_populates="form",
        order_by="SurveyQuestion.order", cascade="all, delete-orphan",
    )
    responses = relationship("SurveyResponse", back_populates="form", cascade="all, delete-orphan")


class SurveyQuestion(Base):
    __tablename__ = "survey_questions"

    id = Column(Integer, primary_key=True, index=True)
    form_id = Column(Integer, ForeignKey("survey_forms.id"), nullable=False)
    group_name = Column(String(200), nullable=True)
    text = Column(Text, nullable=False)
    type = Column(
        SAEnum(SurveyQuestionType, native_enum=False, create_constraint=False, length=20),
        default=SurveyQuestionType.scale, nullable=False,
    )
    order = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now())

    form = relationship("SurveyForm", back_populates="questions")
    answers = relationship("SurveyAnswer", back_populates="question", cascade="all, delete-orphan")


class SurveyResponse(Base):
    __tablename__ = "survey_responses"

    id = Column(Integer, primary_key=True, index=True)
    form_id = Column(Integer, ForeignKey("survey_forms.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    period = Column(String(20), nullable=False)  # e.g. "2026-1" (semestre)
    status = Column(SAEnum(EvaluationStatus), default=EvaluationStatus.pending, nullable=False)
    submitted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    form = relationship("SurveyForm", back_populates="responses")
    user = relationship("User")
    answers = relationship("SurveyAnswer", back_populates="response", cascade="all, delete-orphan")


class SurveyAnswer(Base):
    __tablename__ = "survey_answers"

    id = Column(Integer, primary_key=True, index=True)
    response_id = Column(Integer, ForeignKey("survey_responses.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("survey_questions.id"), nullable=False)
    score = Column(Integer, nullable=True)
    text_answer = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    response = relationship("SurveyResponse", back_populates="answers")
    question = relationship("SurveyQuestion", back_populates="answers")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    Base.metadata.create_all(bind=engine)
    run_migrations()


def run_migrations():
    """Patches columns on tables that already existed in production before
    they were added/changed here, since create_all() only creates missing
    tables and never alters existing ones. Safe to run on every startup."""
    if not DATABASE_URL.startswith("postgresql"):
        return
    with engine.begin() as conn:
        conn.execute(text(
            "ALTER TABLE survey_forms ADD COLUMN IF NOT EXISTS opens_at TIMESTAMP"
        ))
        conn.execute(text(
            "ALTER TABLE survey_forms ADD COLUMN IF NOT EXISTS closes_at TIMESTAMP"
        ))
        conn.execute(text(
            "ALTER TABLE survey_questions ALTER COLUMN type TYPE VARCHAR(20) USING type::text"
        ))
