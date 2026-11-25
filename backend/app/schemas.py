from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, ConfigDict, EmailStr


# ---- Auth ----
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: str = "student"
    management_token: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    role: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CourseCreate(BaseModel):
    title: str
    document_id: str
    description: Optional[str] = None


class CourseJoin(BaseModel):
    join_code: str


# ---- Topics / Study plan ----
class TopicOut(BaseModel):
    id: str
    title: str
    difficulty: str
    order_index: int
    parent_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class StudyPlanItemOut(BaseModel):
    id: str
    topic_id: str
    topic_title: str
    status: str
    scheduled_order: int
    reason: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ---- Quiz ----
class QuizGenerateRequest(BaseModel):
    topic_id: str
    num_questions: int = 5

class DiagnosticQuizGenerateRequest(BaseModel):
    num_questions: int = 10


class DiagnosticQuizOut(BaseModel):
    quiz_id: str
    questions: list[dict]


class DiagnosticQuizResultOut(BaseModel):
    quiz_id: str
    score: float
    level: str
    explanations: list[dict]


class QuizQuestion(BaseModel):
    question: str
    options: list[str]
    correct_index: int


class QuizOut(BaseModel):
    quiz_id: str
    topic_id: str
    questions: list[dict]  # options only, no correct_index sent to client


class QuizSubmitRequest(BaseModel):
    quiz_id: str
    answers: list[int]


class QuizResultOut(BaseModel):
    quiz_id: str
    score: float
    mastery_score: float
    passed: bool
    explanations: list[dict]
    remediation_triggered: bool


# ---- Study Kit ----
class StudyKitRequest(BaseModel):
    topic_id: str


class StudyKitOut(BaseModel):
    topic_id: str
    summary: str
    flashcards: list[dict]
    quiz: list[dict]
    step_by_step_guide: list[str]


# ---- Remediation ----
class RemediationRequest(BaseModel):
    topic_id: str
    sub_concept: Optional[str] = None


class RemediationOut(BaseModel):
    topic_id: str
    micro_module: str
    explanation: str
    resources: list[dict] = []


# ---- Chat ----
class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    role: str
    content: str
    citations: list[dict] = []


# ---- Progress ----
class ProgressTrend(BaseModel):
    topic_id: str
    topic_title: str
    score: float
    attempts: int
    status: str


class ProgressOut(BaseModel):
    overall_mastery: float
    trends: list[ProgressTrend]


class FacultyQuestionDraftCreate(BaseModel):
    topic_id: str
    num_questions: int = 5


class FacultyQuestionDraftReview(BaseModel):
    status: str


class FacultyAssessmentCreate(BaseModel):
    topic_id: str
    title: str
    question_draft_id: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    duration_minutes: int = 45
    ai_support_enabled: bool = False
# ---- Study ----
class StudyRequest(BaseModel):
    topic_id: str


class StudyOut(BaseModel):
    topic_id: str
    topic_title: str
    content: str
    citations: list[dict] = []
