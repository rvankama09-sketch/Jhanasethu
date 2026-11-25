from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import models, schemas
from app.agent.quiz_tools import generate_quiz
from app.core.security import get_current_user
from app.core.time import utc_now
from app.database import get_db
from app.llm.factory import get_llm_provider

router = APIRouter(tags=["faculty-workspace"])


def _owned_course(db: Session, course_id: str, instructor: models.User) -> models.Course:
    course = (
        db.query(models.Course)
        .filter(
            models.Course.id == course_id,
            models.Course.owner_id == instructor.id,
        )
        .first()
    )
    if instructor.role != models.RoleEnum.instructor or not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


def _assessment_out(assessment: models.ScheduledAssessment) -> dict:
    return {
        "id": assessment.id,
        "course_id": assessment.course_id,
        "topic_id": assessment.topic_id,
        "topic_title": assessment.topic.title if assessment.topic else "Unknown",
        "question_draft_id": assessment.question_draft_id,
        "title": assessment.title,
        "scheduled_at": assessment.scheduled_at,
        "duration_minutes": assessment.duration_minutes,
        "ai_support_enabled": assessment.ai_support_enabled,
        "status": assessment.status,
        "created_at": assessment.created_at,
    }


@router.get("/faculty/courses/{course_id}/question-drafts")
def list_question_drafts(
    course_id: str,
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _owned_course(db, course_id, current_user)
    query = db.query(models.FacultyQuestionDraft).filter(
        models.FacultyQuestionDraft.course_id == course_id
    )
    if status:
        query = query.filter(models.FacultyQuestionDraft.status == status)
    drafts = query.order_by(models.FacultyQuestionDraft.created_at.desc()).all()
    return [
        {
            "id": draft.id,
            "course_id": draft.course_id,
            "topic_id": draft.topic_id,
            "topic_title": draft.topic.title if draft.topic else "Unknown",
            "questions": draft.questions,
            "status": draft.status,
            "created_at": draft.created_at,
            "reviewed_at": draft.reviewed_at,
        }
        for draft in drafts
    ]


@router.post("/faculty/courses/{course_id}/question-drafts", status_code=201)
def create_question_draft(
    course_id: str,
    payload: schemas.FacultyQuestionDraftCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    course = _owned_course(db, course_id, current_user)
    if not 1 <= payload.num_questions <= 20:
        raise HTTPException(status_code=400, detail="Question count must be between 1 and 20")
    topic = (
        db.query(models.Topic)
        .filter(
            models.Topic.id == payload.topic_id,
            models.Topic.document_id == course.document_id,
        )
        .first()
    )
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found in this course")

    try:
        generated_attempt = generate_quiz(
            db,
            get_llm_provider(),
            current_user.id,
            topic.id,
            payload.num_questions,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    questions = generated_attempt.questions
    db.delete(generated_attempt)
    draft = models.FacultyQuestionDraft(
        course_id=course.id,
        topic_id=topic.id,
        instructor_id=current_user.id,
        questions=questions,
        status="pending",
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return {
        "id": draft.id,
        "course_id": draft.course_id,
        "topic_id": draft.topic_id,
        "topic_title": topic.title,
        "questions": draft.questions,
        "status": draft.status,
        "created_at": draft.created_at,
        "reviewed_at": draft.reviewed_at,
    }


@router.patch("/faculty/question-drafts/{draft_id}")
def review_question_draft(
    draft_id: str,
    payload: schemas.FacultyQuestionDraftReview,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.role != models.RoleEnum.instructor:
        raise HTTPException(status_code=403, detail="Faculty role required")
    if payload.status not in {"approved", "rejected"}:
        raise HTTPException(status_code=400, detail="Status must be approved or rejected")
    draft = (
        db.query(models.FacultyQuestionDraft)
        .filter(
            models.FacultyQuestionDraft.id == draft_id,
            models.FacultyQuestionDraft.instructor_id == current_user.id,
        )
        .first()
    )
    if not draft:
        raise HTTPException(status_code=404, detail="Question draft not found")
    if draft.status != "pending":
        raise HTTPException(status_code=409, detail="Question draft has already been reviewed")
    draft.status = payload.status
    draft.reviewed_at = utc_now()
    db.commit()
    return {"id": draft.id, "status": draft.status, "reviewed_at": draft.reviewed_at}


@router.get("/faculty/courses/{course_id}/assessments")
def list_course_assessments(
    course_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _owned_course(db, course_id, current_user)
    assessments = (
        db.query(models.ScheduledAssessment)
        .filter(models.ScheduledAssessment.course_id == course_id)
        .order_by(models.ScheduledAssessment.scheduled_at, models.ScheduledAssessment.created_at.desc())
        .all()
    )
    return [_assessment_out(item) for item in assessments]


@router.post("/faculty/courses/{course_id}/assessments", status_code=201)
def create_assessment(
    course_id: str,
    payload: schemas.FacultyAssessmentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    course = _owned_course(db, course_id, current_user)
    if not 5 <= payload.duration_minutes <= 240:
        raise HTTPException(status_code=400, detail="Duration must be between 5 and 240 minutes")
    topic = (
        db.query(models.Topic)
        .filter(
            models.Topic.id == payload.topic_id,
            models.Topic.document_id == course.document_id,
        )
        .first()
    )
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found in this course")
    approved_draft = None
    if payload.question_draft_id:
        approved_draft = (
            db.query(models.FacultyQuestionDraft)
            .filter(
                models.FacultyQuestionDraft.id == payload.question_draft_id,
                models.FacultyQuestionDraft.course_id == course.id,
                models.FacultyQuestionDraft.topic_id == topic.id,
                models.FacultyQuestionDraft.status == "approved",
            )
            .first()
        )
        if not approved_draft:
            raise HTTPException(status_code=400, detail="Choose an approved question set for this topic")
    assessment = models.ScheduledAssessment(
        course_id=course.id,
        topic_id=topic.id,
        question_draft_id=approved_draft.id if approved_draft else None,
        instructor_id=current_user.id,
        title=payload.title.strip(),
        scheduled_at=payload.scheduled_at,
        duration_minutes=payload.duration_minutes,
        ai_support_enabled=payload.ai_support_enabled,
        status="scheduled" if payload.scheduled_at else "draft",
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return _assessment_out(assessment)


@router.get("/assessments/mine")
def list_student_assessments(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.role != models.RoleEnum.student:
        raise HTTPException(status_code=403, detail="Student role required")
    course_ids = [
        enrollment.course_id
        for enrollment in db.query(models.CourseEnrollment)
        .filter(models.CourseEnrollment.user_id == current_user.id)
        .all()
    ]
    if not course_ids:
        return []
    assessments = (
        db.query(models.ScheduledAssessment)
        .filter(
            models.ScheduledAssessment.course_id.in_(course_ids),
            models.ScheduledAssessment.status == "scheduled",
        )
        .order_by(models.ScheduledAssessment.scheduled_at)
        .all()
    )
    return [_assessment_out(item) for item in assessments]


@router.post("/assessments/{assessment_id}/start")
def start_student_assessment(
    assessment_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.role != models.RoleEnum.student:
        raise HTTPException(status_code=403, detail="Student role required")
    assessment = (
        db.query(models.ScheduledAssessment)
        .join(models.CourseEnrollment, models.CourseEnrollment.course_id == models.ScheduledAssessment.course_id)
        .filter(
            models.ScheduledAssessment.id == assessment_id,
            models.ScheduledAssessment.status == "scheduled",
            models.CourseEnrollment.user_id == current_user.id,
        )
        .first()
    )
    if not assessment or not assessment.scheduled_at:
        raise HTTPException(status_code=404, detail="Scheduled assessment not found")
    scheduled_at = assessment.scheduled_at.replace(tzinfo=None)
    now = utc_now()
    if now < scheduled_at:
        raise HTTPException(status_code=409, detail="This assessment is not open yet")
    ends_at = scheduled_at + timedelta(minutes=assessment.duration_minutes)
    if now >= ends_at:
        raise HTTPException(status_code=410, detail="The assessment window has closed")

    previous = (
        db.query(models.AssessmentAttempt)
        .filter(
            models.AssessmentAttempt.assessment_id == assessment.id,
            models.AssessmentAttempt.user_id == current_user.id,
        )
        .first()
    )
    if previous:
        if previous.completed_at:
            raise HTTPException(status_code=409, detail="You have already completed this assessment")
        quiz_attempt = (
            db.query(models.QuizAttempt)
            .filter(models.QuizAttempt.id == previous.quiz_attempt_id)
            .first()
        )
        if not quiz_attempt:
            raise HTTPException(status_code=409, detail="The assessment attempt is unavailable")
    else:
        if assessment.question_draft_id:
            draft = (
                db.query(models.FacultyQuestionDraft)
                .filter(
                    models.FacultyQuestionDraft.id == assessment.question_draft_id,
                    models.FacultyQuestionDraft.status == "approved",
                )
                .first()
            )
            if not draft:
                raise HTTPException(status_code=409, detail="The approved question set is unavailable")
            quiz_attempt = models.QuizAttempt(
                user_id=current_user.id,
                topic_id=assessment.topic_id,
                questions=draft.questions,
                answers=None,
                score=None,
            )
            db.add(quiz_attempt)
            db.flush()
        else:
            try:
                quiz_attempt = generate_quiz(
                    db,
                    get_llm_provider(),
                    current_user.id,
                    assessment.topic_id,
                    num_questions=10,
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        db.add(
            models.AssessmentAttempt(
                assessment_id=assessment.id,
                user_id=current_user.id,
                quiz_attempt_id=quiz_attempt.id,
                started_at=now,
            )
        )
        db.commit()
        db.refresh(quiz_attempt)

    return {
        "assessment_id": assessment.id,
        "title": assessment.title,
        "topic_id": assessment.topic_id,
        "topic_title": assessment.topic.title if assessment.topic else "Assessment",
        "quiz_id": quiz_attempt.id,
        "duration_minutes": assessment.duration_minutes,
        "ends_at": ends_at,
        "ai_support_enabled": assessment.ai_support_enabled,
        "questions": [
            {"question": item.get("question", ""), "options": item.get("options", [])}
            for item in quiz_attempt.questions
        ],
    }
