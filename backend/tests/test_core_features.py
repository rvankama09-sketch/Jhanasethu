import io
import warnings
from datetime import datetime, timezone

import pytest
from fastapi import BackgroundTasks, HTTPException, UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.core.config import get_settings
from app.core.security import hash_password, verify_password, create_access_token, decode_token
from app.database import Base
from app.agent.study_planner import generate_study_plan
from app.llm.providers.mock_provider import MockProvider
from app.routers.auth import signup, login
from app.routers.courses import create_course, join_course, list_courses, get_course
from app.rag.vector_store import get_collection
from app.routers.management import platform_metrics, adoption_and_interventions
from app.routers.syllabus import upload_syllabus, list_documents, get_status, delete_document
from app.routers.topics import list_topics
from app.schemas import CourseCreate, CourseJoin, UserCreate, UserLogin, UserOut


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_password_hash_round_trip():
    hashed = hash_password("S3cret!Password")
    assert hashed != "S3cret!Password"
    assert verify_password("S3cret!Password", hashed)
    assert not verify_password("WrongPassword", hashed)


def test_token_round_trip():
    token = create_access_token("user-123")
    assert decode_token(token) == "user-123"


def test_student_signup_and_login(db_session):
    result = signup(UserCreate(email="student@example.com", password="StrongPass123!"), db_session)
    assert result.access_token

    user = db_session.query(models.User).filter(models.User.email == "student@example.com").one()
    assert user.role == models.RoleEnum.student

    login_result = login(UserLogin(email="student@example.com", password="StrongPass123!"), db_session)
    assert login_result.access_token


def test_management_signup_requires_valid_token(db_session, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "management_emails", "admin@example.com")
    monkeypatch.setattr(settings, "management_signup_token", "top-secret-token")

    with pytest.raises(HTTPException) as exc_info:
        signup(
            UserCreate(
                email="admin@example.com",
                password="StrongPass123!",
                role="management",
            ),
            db_session,
        )
    assert exc_info.value.status_code == 403
    assert "Management signup" in str(exc_info.value.detail)

    created = signup(
        UserCreate(
            email="admin@example.com",
            password="StrongPass123!",
            role="management",
            management_token="top-secret-token",
        ),
        db_session,
    )
    assert created.access_token

    user = db_session.query(models.User).filter(models.User.email == "admin@example.com").one()
    assert user.role == models.RoleEnum.management


def test_schema_models_convert_from_orm_without_pydantic_warnings():
    user = models.User(
        id="user-456",
        email="orm@example.com",
        hashed_password="hashed-value",
        role=models.RoleEnum.student,
        created_at=datetime.now(timezone.utc),
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        payload = UserOut.model_validate(user)

    assert payload.email == "orm@example.com"
    assert not any("Support for class-based `config` is deprecated" in str(w.message) for w in caught)


def test_course_and_topic_flow_for_instructor_and_student(db_session):
    instructor = models.User(
        id="inst-1",
        email="instructor@example.com",
        hashed_password="hashed",
        role=models.RoleEnum.instructor,
    )
    student = models.User(
        id="stu-1",
        email="student2@example.com",
        hashed_password="hashed",
        role=models.RoleEnum.student,
    )
    document = models.Document(
        id="doc-1",
        user_id=instructor.id,
        filename="syllabus.pdf",
        document_type="syllabus",
        status="ready",
    )
    topic_one = models.Topic(id="topic-1", document_id=document.id, title="Algebra", difficulty="easy", order_index=1)
    topic_two = models.Topic(id="topic-2", document_id=document.id, title="Statistics", difficulty="medium", order_index=2)
    db_session.add_all([instructor, student, document, topic_one, topic_two])
    db_session.commit()

    created = create_course(
        CourseCreate(title="Math 101", document_id=document.id, description="Intro to math"),
        db_session,
        instructor,
    )
    assert created["title"] == "Math 101"
    assert created["join_code"]

    joined = join_course(CourseJoin(join_code=created["join_code"]), db_session, student)
    assert joined["document_id"] == document.id

    owned_courses = list_courses(db_session, instructor)
    assert any(course["id"] == created["id"] for course in owned_courses)

    enrolled_courses = list_courses(db_session, student)
    assert any(course["id"] == created["id"] for course in enrolled_courses)

    topics = list_topics(db_session, student)
    assert [topic.title for topic in topics] == ["Algebra", "Statistics"]

    detail = get_course(created["id"], db_session, student)
    assert [item["title"] for item in detail["topics"]] == ["Algebra", "Statistics"]


def test_study_plan_generation_for_enrolled_student(db_session):
    instructor = models.User(
        id="inst-2",
        email="instructor2@example.com",
        hashed_password="hashed",
        role=models.RoleEnum.instructor,
    )
    student = models.User(
        id="stu-2",
        email="student3@example.com",
        hashed_password="hashed",
        role=models.RoleEnum.student,
    )
    document = models.Document(
        id="doc-2",
        user_id=instructor.id,
        filename="course-outline.pdf",
        document_type="syllabus",
        status="ready",
    )
    topic_one = models.Topic(id="topic-3", document_id=document.id, title="Algorithms", difficulty="medium", order_index=1)
    topic_two = models.Topic(id="topic-4", document_id=document.id, title="Security", difficulty="hard", order_index=2)
    course = models.Course(
        id="course-2",
        owner_id=instructor.id,
        document_id=document.id,
        title="CS Fundamentals",
        description="Fundamentals",
        join_code="STACK42",
    )
    db_session.add_all([instructor, student, document, topic_one, topic_two, course])
    db_session.commit()
    db_session.add(models.CourseEnrollment(course_id=course.id, user_id=student.id))
    db_session.add(models.OverallAssessment(user_id=student.id, score=0.6, level="medium"))
    db_session.commit()

    plan = generate_study_plan(db_session, student.id)
    assert [item.topic_id for item in plan] == [topic_one.id, topic_two.id]
    assert {item.status for item in plan} <= {"pending", "needs_remediation", "mastered"}


def test_management_metrics_and_adoption_report(db_session):
    management = models.User(
        id="mgr-1",
        email="management@example.com",
        hashed_password="hashed",
        role=models.RoleEnum.management,
    )
    instructor = models.User(
        id="inst-3",
        email="instructor3@example.com",
        hashed_password="hashed",
        role=models.RoleEnum.instructor,
    )
    student = models.User(
        id="stu-3",
        email="student4@example.com",
        hashed_password="hashed",
        role=models.RoleEnum.student,
    )
    document = models.Document(
        id="doc-3",
        user_id=instructor.id,
        filename="history_syllabus.pdf",
        document_type="syllabus",
        status="ready",
    )
    topic = models.Topic(id="topic-5", document_id=document.id, title="Ancient History", difficulty="easy", order_index=1)
    course = models.Course(
        id="course-3",
        owner_id=instructor.id,
        document_id=document.id,
        title="World History",
        description="History course",
        join_code="HIST777",
    )
    db_session.add_all([management, instructor, student, document, topic, course])
    db_session.commit()
    db_session.add(models.CourseEnrollment(course_id=course.id, user_id=student.id))
    db_session.add(models.MasteryScore(user_id=student.id, topic_id=topic.id, score=0.80))
    db_session.add(
        models.LearningActivity(
            user_id=student.id,
            course_id=course.id,
            topic_id=topic.id,
            activity_type="quiz",
            title="History quiz",
            score=0.9,
        )
    )
    db_session.commit()

    metrics = platform_metrics(db_session, management)
    assert metrics["student_count"] >= 1
    assert metrics["faculty_count"] >= 1
    assert metrics["course_count"] >= 1

    adoption = adoption_and_interventions(db_session, management)
    assert adoption["course_count"] >= 1
    assert adoption["active_students"] >= 1
    assert adoption["daily_activity"]


def test_syllabus_upload_list_status_and_delete(db_session):
    instructor = models.User(
        id="inst-4",
        email="instructor4@example.com",
        hashed_password="hashed",
        role=models.RoleEnum.instructor,
    )
    db_session.add(instructor)
    db_session.commit()

    upload_file = UploadFile(filename="sample.pdf", file=io.BytesIO(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"))
    result = upload_syllabus(
        BackgroundTasks(),
        file=upload_file,
        document_type="syllabus",
        db=db_session,
        current_user=instructor,
    )

    assert result["document_id"]
    assert result["status"] == "processing"

    status = get_status(result["document_id"], db_session, instructor)
    assert status["status"] == "processing"

    docs = list_documents(db_session, instructor)
    assert any(doc["id"] == result["document_id"] for doc in docs)

    delete_document(result["document_id"], db_session, instructor)
    assert db_session.query(models.Document).filter(models.Document.id == result["document_id"]).first() is None


def test_chroma_embedding_function_has_no_deprecation_warnings():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        get_collection()

    assert not any(
        "EmbeddingFunction class does not implement name" in str(w.message)
        or "does not implement __init__" in str(w.message)
        for w in caught
    )


def test_mock_provider_returns_valid_quiz_and_study_plan_json():
    provider = MockProvider()

    quiz_json = provider.complete(
        [
            {"role": "system", "content": "Generate a quiz with question structure."},
            {"role": "user", "content": "Topic: networking"},
        ],
        json_mode=True,
    )
    quiz_data = __import__("json").loads(quiz_json)
    assert "questions" in quiz_data
    assert len(quiz_data["questions"]) == 5
    assert set(quiz_data["questions"][0].keys()) >= {"question", "options", "correct_index"}

    plan_json = provider.complete(
        [
            {"role": "system", "content": "Create study plan for this syllabus."},
            {"role": "user", "content": "Topics include algorithms, systems, security"},
        ],
        json_mode=True,
    )
    plan_data = __import__("json").loads(plan_json)
    assert "ordered_topics" in plan_data
    assert plan_data["ordered_topics"]
