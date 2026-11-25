import enum
import uuid

from app.core.time import utc_now

from sqlalchemy import (
    Column, String, Float, Integer, ForeignKey, DateTime, Text, Enum, JSON, Boolean,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class RoleEnum(str, enum.Enum):
    student = "student"
    instructor = "instructor"
    management = "management"


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=gen_uuid)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(RoleEnum), default=RoleEnum.student, nullable=False)
    created_at = Column(DateTime, default=utc_now)

    documents = relationship("Document", back_populates="owner", cascade="all, delete-orphan")
    mastery_scores = relationship("MasteryScore", back_populates="user", cascade="all, delete-orphan")
    quiz_attempts = relationship("QuizAttempt", back_populates="user", cascade="all, delete-orphan")
    chat_messages = relationship("ChatMessage", back_populates="user", cascade="all, delete-orphan")
    study_plan_items = relationship("StudyPlanItem", back_populates="user", cascade="all, delete-orphan")
    owned_courses = relationship("Course", back_populates="owner", cascade="all, delete-orphan")
    course_enrollments = relationship("CourseEnrollment", back_populates="user", cascade="all, delete-orphan")
    learning_activities = relationship("LearningActivity", back_populates="user", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    filename = Column(String, nullable=False)
    document_type = Column(String, default="syllabus", nullable=False)
    status = Column(String, default="processing")  # processing | ready | failed
    uploaded_at = Column(DateTime, default=utc_now)

    owner = relationship("User", back_populates="documents")
    topics = relationship("Topic", back_populates="document", cascade="all, delete-orphan")
    courses = relationship("Course", back_populates="document", cascade="all, delete-orphan")


class Topic(Base):
    __tablename__ = "topics"

    id = Column(String, primary_key=True, default=gen_uuid)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    parent_id = Column(String, ForeignKey("topics.id"), nullable=True)
    title = Column(String, nullable=False)
    difficulty = Column(String, default="medium")  # easy | medium | hard
    order_index = Column(Integer, default=0)

    document = relationship("Document", back_populates="topics")
    children = relationship("Topic", backref="parent", remote_side=[id])


class MasteryScore(Base):
    __tablename__ = "mastery_scores"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    topic_id = Column(String, ForeignKey("topics.id"), nullable=False)
    score = Column(Float, default=0.0)  # 0.0 - 1.0
    attempts = Column(Integer, default=0)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    user = relationship("User", back_populates="mastery_scores")
    topic = relationship("Topic")


class StudyPlanItem(Base):
    __tablename__ = "study_plan_items"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    topic_id = Column(String, ForeignKey("topics.id"), nullable=False)
    status = Column(String, default="pending")  # pending | in_progress | mastered | needs_remediation
    scheduled_order = Column(Integer, default=0)
    reason = Column(Text, nullable=True)  # why the agent scheduled this next
    created_at = Column(DateTime, default=utc_now)

    user = relationship("User", back_populates="study_plan_items")
    topic = relationship("Topic")


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    topic_id = Column(String, ForeignKey("topics.id"), nullable=True)
    questions = Column(JSON, nullable=False)   # list of {question, options, correct_index}
    answers = Column(JSON, nullable=True)      # list of selected indices
    score = Column(Float, nullable=True)       # 0.0 - 1.0
    explanations = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utc_now)

    user = relationship("User", back_populates="quiz_attempts")
    topic = relationship("Topic")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    role = Column(String, nullable=False)  # user | assistant
    content = Column(Text, nullable=False)
    citations = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utc_now)

    user = relationship("User", back_populates="chat_messages")

class OverallAssessment(Base):
    __tablename__ = "overall_assessments"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    score = Column(Float, nullable=False)
    level = Column(String, nullable=False)  # easy | medium | hard
    created_at = Column(DateTime, default=utc_now)

    user = relationship("User")


class Course(Base):
    __tablename__ = "courses"

    id = Column(String, primary_key=True, default=gen_uuid)
    owner_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    join_code = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    owner = relationship("User", back_populates="owned_courses")
    document = relationship("Document", back_populates="courses")
    enrollments = relationship("CourseEnrollment", back_populates="course", cascade="all, delete-orphan")
    activities = relationship("LearningActivity", back_populates="course")


class CourseEnrollment(Base):
    __tablename__ = "course_enrollments"
    __table_args__ = (UniqueConstraint("course_id", "user_id", name="uq_course_enrollment"),)

    id = Column(String, primary_key=True, default=gen_uuid)
    course_id = Column(String, ForeignKey("courses.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    joined_at = Column(DateTime, default=utc_now, nullable=False)

    course = relationship("Course", back_populates="enrollments")
    user = relationship("User", back_populates="course_enrollments")


class LearningActivity(Base):
    __tablename__ = "learning_activities"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    course_id = Column(String, ForeignKey("courses.id"), nullable=True, index=True)
    topic_id = Column(String, ForeignKey("topics.id"), nullable=True, index=True)
    activity_type = Column(String, nullable=False)
    title = Column(String, nullable=False)
    score = Column(Float, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False, index=True)

    user = relationship("User", back_populates="learning_activities")
    course = relationship("Course", back_populates="activities")
    topic = relationship("Topic")


class FacultyQuestionDraft(Base):
    __tablename__ = "faculty_question_drafts"

    id = Column(String, primary_key=True, default=gen_uuid)
    course_id = Column(String, ForeignKey("courses.id"), nullable=False, index=True)
    topic_id = Column(String, ForeignKey("topics.id"), nullable=False, index=True)
    instructor_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    questions = Column(JSON, nullable=False)
    status = Column(String, default="pending", nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    reviewed_at = Column(DateTime, nullable=True)

    topic = relationship("Topic")


class ScheduledAssessment(Base):
    __tablename__ = "scheduled_assessments"

    id = Column(String, primary_key=True, default=gen_uuid)
    course_id = Column(String, ForeignKey("courses.id"), nullable=False, index=True)
    topic_id = Column(String, ForeignKey("topics.id"), nullable=False, index=True)
    question_draft_id = Column(String, ForeignKey("faculty_question_drafts.id"), nullable=True)
    instructor_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    scheduled_at = Column(DateTime, nullable=True)
    duration_minutes = Column(Integer, default=45, nullable=False)
    ai_support_enabled = Column(Boolean, default=False, nullable=False)
    status = Column(String, default="scheduled", nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    topic = relationship("Topic")


class AssessmentAttempt(Base):
    __tablename__ = "assessment_attempts"

    id = Column(String, primary_key=True, default=gen_uuid)
    assessment_id = Column(String, ForeignKey("scheduled_assessments.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    quiz_attempt_id = Column(String, ForeignKey("quiz_attempts.id"), unique=True, nullable=False)
    started_at = Column(DateTime, default=utc_now, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    score = Column(Float, nullable=True)