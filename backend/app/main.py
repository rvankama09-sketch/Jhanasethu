from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.database import Base, engine
from app.routers import (
    auth, syllabus, study_plan, quiz, study_kit, study, remediation, chat, progress,
    topics, courses, management, faculty,
)

settings = get_settings()

app = FastAPI(
    title="Personalized Learning Path Generator API",
    version="1.0.0",
    description="AI-powered agentic tutor backend (FastAPI + LangGraph + RAG).",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    if engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'roleenum') THEN "
                "ALTER TYPE roleenum ADD VALUE IF NOT EXISTS 'management'; "
                "END IF; END $$;"
            )
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health():
    return {"status": "ok", "llm_provider": settings.llm_provider}


app.include_router(auth.router)
app.include_router(syllabus.router)
app.include_router(study_plan.router)
app.include_router(quiz.router)
app.include_router(study_kit.router)
app.include_router(study.router)
app.include_router(remediation.router)
app.include_router(chat.router)
app.include_router(progress.router)
app.include_router(topics.router)
app.include_router(courses.router)
app.include_router(management.router)
app.include_router(faculty.router)
