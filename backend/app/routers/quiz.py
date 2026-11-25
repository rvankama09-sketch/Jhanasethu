from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.agent.quiz_tools import (
    generate_quiz,
    evaluate_quiz,
    generate_diagnostic_quiz,
    evaluate_diagnostic_quiz,
)
from app.agent.study_planner import MASTERY_THRESHOLD
from app.core.security import (
    activity_course_id,
    can_access_topic,
    ensure_ai_support_allowed,
    get_current_user,
)
from app.core.time import utc_now
from app.database import get_db
from app.llm.factory import get_llm_provider

router = APIRouter(prefix="/quiz", tags=["quiz"])


@router.post("/generate", response_model=schemas.QuizOut)
def generate(
    payload: schemas.QuizGenerateRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    ensure_ai_support_allowed(db, current_user)
    topic = db.query(models.Topic).filter(models.Topic.id == payload.topic_id).first()
    if not topic or not can_access_topic(db, current_user, topic):
        raise HTTPException(status_code=404, detail="Topic not found")

    llm = get_llm_provider()
    try:
        attempt = generate_quiz(db, llm, current_user.id, payload.topic_id, payload.num_questions)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Never send correct_index to the client before submission.
    sanitized = [{"question": q["question"], "options": q["options"]} for q in attempt.questions]
    return schemas.QuizOut(quiz_id=attempt.id, topic_id=attempt.topic_id, questions=sanitized)


@router.post("/submit", response_model=schemas.QuizResultOut)
def submit(
    payload: schemas.QuizSubmitRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    attempt = (
        db.query(models.QuizAttempt)
        .filter(
            models.QuizAttempt.id == payload.quiz_id,
            models.QuizAttempt.user_id == current_user.id,
            models.QuizAttempt.topic_id.is_not(None),
        )
        .first()
    )
    if not attempt:
        raise HTTPException(status_code=404, detail="Quiz attempt not found")
    topic = db.query(models.Topic).filter(models.Topic.id == attempt.topic_id).first()
    if not topic or not can_access_topic(db, current_user, topic):
        raise HTTPException(status_code=404, detail="Quiz attempt not found")
    if attempt.score is not None:
        raise HTTPException(status_code=409, detail="Quiz has already been submitted")
    if len(payload.answers) != len(attempt.questions) or any(
        answer < 0 or answer >= len(question.get("options", []))
        for answer, question in zip(payload.answers, attempt.questions)
    ):
        raise HTTPException(status_code=400, detail="Provide one valid answer for every question")

    scheduled_attempt = (
        db.query(models.AssessmentAttempt)
        .filter(models.AssessmentAttempt.quiz_attempt_id == attempt.id)
        .first()
    )
    if scheduled_attempt:
        assessment = (
            db.query(models.ScheduledAssessment)
            .filter(models.ScheduledAssessment.id == scheduled_attempt.assessment_id)
            .first()
        )
        if assessment and assessment.scheduled_at:
            assessment_end = assessment.scheduled_at.replace(tzinfo=None) + timedelta(
                minutes=assessment.duration_minutes
            )
            if utc_now() >= assessment_end:
                raise HTTPException(status_code=410, detail="The assessment window has closed")

    llm = get_llm_provider()
    try:
        result = evaluate_quiz(db, llm, payload.quiz_id, payload.answers)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Score gating: below threshold -> flag that remediation should run before
    # the student can advance. The frontend calls /remediation/micro-module next.
    remediation_triggered = result["mastery_score"] < MASTERY_THRESHOLD
    if scheduled_attempt:
        scheduled_attempt.completed_at = utc_now()
        scheduled_attempt.score = result["score"]
        db.add(scheduled_attempt)
    db.add(models.LearningActivity(
        user_id=current_user.id,
        course_id=activity_course_id(db, current_user.id, topic),
        topic_id=attempt.topic_id,
        activity_type="quiz",
        title=f"Completed quiz: {topic.title if topic else 'Topic'}",
        score=result["score"],
    ))
    db.commit()

    return schemas.QuizResultOut(
        quiz_id=payload.quiz_id,
        score=result["score"],
        mastery_score=result["mastery_score"],
        passed=result["passed"],
        explanations=result["explanations"],
        remediation_triggered=remediation_triggered,
    )

@router.post("/diagnostic/generate", response_model=schemas.DiagnosticQuizOut)
def generate_diagnostic(
    payload: schemas.DiagnosticQuizGenerateRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    llm = get_llm_provider()

    try:
        attempt = generate_diagnostic_quiz(
            db,
            llm,
            current_user.id,
            payload.num_questions,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    sanitized = [
        {
            "question": q["question"],
            "options": q["options"],
        }
        for q in attempt.questions
    ]

    return schemas.DiagnosticQuizOut(
        quiz_id=attempt.id,
        questions=sanitized,
    )


@router.post(
    "/diagnostic/submit",
    response_model=schemas.DiagnosticQuizResultOut,
)
def submit_diagnostic(
    payload: schemas.QuizSubmitRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    attempt = (
        db.query(models.QuizAttempt)
        .filter(
            models.QuizAttempt.id == payload.quiz_id,
            models.QuizAttempt.user_id == current_user.id,
            models.QuizAttempt.topic_id.is_(None),
        )
        .first()
    )
    if not attempt:
        raise HTTPException(status_code=404, detail="Diagnostic quiz attempt not found")
    if attempt.score is not None:
        raise HTTPException(status_code=409, detail="Diagnostic quiz has already been submitted")
    if len(payload.answers) != len(attempt.questions) or any(
        answer < 0 or answer >= len(question.get("options", []))
        for answer, question in zip(payload.answers, attempt.questions)
    ):
        raise HTTPException(status_code=400, detail="Provide one valid answer for every question")

    llm = get_llm_provider()

    try:
        result = evaluate_diagnostic_quiz(
            db,
            llm,
            payload.quiz_id,
            current_user.id,
            payload.answers,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    db.add(models.LearningActivity(
        user_id=current_user.id,
        activity_type="diagnostic_quiz",
        title="Completed diagnostic quiz",
        score=result["score"],
    ))
    db.commit()

    return schemas.DiagnosticQuizResultOut(
        quiz_id=payload.quiz_id,
        score=result["score"],
        level=result["level"],
        explanations=result["explanations"],
    )


@router.get("/{quiz_id}/explain-answer/{question_index}")
def explain_answer(
    quiz_id: str,
    question_index: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Returns the stored explanation for a specific incorrect answer (generated at submit time)."""
    attempt = (
        db.query(models.QuizAttempt)
        .filter(models.QuizAttempt.id == quiz_id, models.QuizAttempt.user_id == current_user.id)
        .first()
    )
    if not attempt or attempt.explanations is None:
        raise HTTPException(status_code=404, detail="No explanation available for this quiz yet")

    match = next((e for e in attempt.explanations if e["question_index"] == question_index), None)
    if not match:
        return {"question_index": question_index, "explanation": "That answer was correct — no explanation needed."}
    return match
