from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.security import get_current_user
from app.core.time import utc_now
from app.database import get_db

router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("/trends", response_model=schemas.ProgressOut)
def trends(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    scores = (
        db.query(models.MasteryScore)
        .filter(models.MasteryScore.user_id == current_user.id)
        .all()
    )
    trend_list = [
        schemas.ProgressTrend(
            topic_id=score.topic_id,
            topic_title=score.topic.title if score.topic else "Unknown",
            score=score.score,
            attempts=score.attempts,
            status="mastered" if score.score >= 0.75 else "needs_remediation",
        )
        for score in scores
    ]
    overall = sum(score.score for score in scores) / len(scores) if scores else 0.0
    return schemas.ProgressOut(overall_mastery=overall, trends=trend_list)


@router.get("/activity")
def student_activity(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.role != models.RoleEnum.student:
        raise HTTPException(status_code=403, detail="Student role required")

    now = utc_now()
    week_start = now - timedelta(days=7)
    previous_week_start = now - timedelta(days=14)
    activities = (
        db.query(models.LearningActivity)
        .filter(
            models.LearningActivity.user_id == current_user.id,
            models.LearningActivity.created_at >= previous_week_start,
        )
        .order_by(models.LearningActivity.created_at.desc())
        .all()
    )
    current_week = [activity for activity in activities if activity.created_at >= week_start]
    current_week_days = {activity.created_at.date() for activity in current_week}
    previous_week_count = sum(activity.created_at < week_start for activity in activities)
    quizzes = [
        activity for activity in current_week
        if activity.activity_type in {"quiz", "diagnostic_quiz"}
    ]
    scored_quizzes = [activity.score for activity in quizzes if activity.score is not None]

    recent = (
        db.query(models.LearningActivity)
        .filter(models.LearningActivity.user_id == current_user.id)
        .order_by(models.LearningActivity.created_at.desc())
        .limit(12)
        .all()
    )
    daily = []
    for day_offset in range(6, -1, -1):
        day = (now - timedelta(days=day_offset)).date()
        daily.append({
            "date": day.isoformat(),
            "count": sum(activity.created_at.date() == day for activity in current_week),
        })

    weak_scores = (
        db.query(models.MasteryScore)
        .filter(
            models.MasteryScore.user_id == current_user.id,
            models.MasteryScore.score < 0.75,
        )
        .order_by(models.MasteryScore.score.asc(), models.MasteryScore.updated_at.desc())
        .limit(5)
        .all()
    )
    recommendations = [
        {
            "topic_id": score.topic_id,
            "topic_title": score.topic.title if score.topic else "Unknown",
            "score": score.score,
            "reason": "Review this topic and try another quiz to improve mastery.",
        }
        for score in weak_scores
    ]

    return {
        "weekly": {
            "activity_count": len(current_week),
            "active_days": len(current_week_days),
            "quiz_count": len(quizzes),
            "average_quiz_score": (
                sum(scored_quizzes) / len(scored_quizzes) if scored_quizzes else None
            ),
            "previous_activity_count": previous_week_count,
        },
        "daily_activity": daily,
        "recommendations": recommendations,
        "recent_activity": [
            {
                "id": activity.id,
                "activity_type": activity.activity_type,
                "title": activity.title,
                "topic_title": activity.topic.title if activity.topic else None,
                "score": activity.score,
                "created_at": activity.created_at,
            }
            for activity in recent
        ],
    }


@router.get("/cohort")
def cohort_dashboard(
    course_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.role != models.RoleEnum.instructor:
        raise HTTPException(status_code=403, detail="Faculty role required")
    course = (
        db.query(models.Course)
        .filter(
            models.Course.id == course_id,
            models.Course.owner_id == current_user.id,
        )
        .first()
    )
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    student_ids = [
        enrollment.user_id
        for enrollment in db.query(models.CourseEnrollment)
        .filter(models.CourseEnrollment.course_id == course.id)
        .all()
    ]
    topic_ids = [
        topic.id
        for topic in db.query(models.Topic)
        .filter(models.Topic.document_id == course.document_id)
        .all()
    ]
    scores = (
        db.query(models.MasteryScore)
        .filter(
            models.MasteryScore.user_id.in_(student_ids),
            models.MasteryScore.topic_id.in_(topic_ids),
        )
        .all()
    ) if student_ids and topic_ids else []
    by_topic: dict[str, list[float]] = {}
    titles: dict[str, str] = {}
    for score in scores:
        by_topic.setdefault(score.topic_id, []).append(score.score)
        if score.topic:
            titles[score.topic_id] = score.topic.title

    activities_last_week = (
        db.query(models.LearningActivity)
        .filter(
            models.LearningActivity.course_id == course.id,
            models.LearningActivity.created_at >= utc_now() - timedelta(days=7),
        )
        .count()
    )
    return {
        "course_id": course.id,
        "course_title": course.title,
        "student_count": len(student_ids),
        "topic_count": len(topic_ids),
        "activity_last_7_days": activities_last_week,
        "topics": [
            {
                "topic_id": topic_id,
                "topic_title": titles.get(topic_id, "Unknown"),
                "average_mastery": sum(values) / len(values),
                "student_count": len(values),
            }
            for topic_id, values in sorted(
                by_topic.items(),
                key=lambda item: sum(item[1]) / len(item[1]),
            )
        ],
    }


@router.get("/cohort/heatmap")
def cohort_heatmap(
    course_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Return an instructor-authorized student-by-topic mastery matrix."""
    if current_user.role != models.RoleEnum.instructor:
        raise HTTPException(status_code=403, detail="Faculty role required")
    course = (
        db.query(models.Course)
        .filter(
            models.Course.id == course_id,
            models.Course.owner_id == current_user.id,
        )
        .first()
    )
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    students = (
        db.query(models.User)
        .join(models.CourseEnrollment, models.CourseEnrollment.user_id == models.User.id)
        .filter(models.CourseEnrollment.course_id == course.id)
        .order_by(models.User.email)
        .all()
    )
    topics = (
        db.query(models.Topic)
        .filter(models.Topic.document_id == course.document_id)
        .order_by(models.Topic.order_index)
        .all()
    )
    student_ids = [student.id for student in students]
    topic_ids = [topic.id for topic in topics]
    scores = (
        db.query(models.MasteryScore)
        .filter(
            models.MasteryScore.user_id.in_(student_ids),
            models.MasteryScore.topic_id.in_(topic_ids),
        )
        .all()
    ) if student_ids and topic_ids else []
    score_map = {(score.user_id, score.topic_id): score for score in scores}

    return {
        "course_id": course.id,
        "course_title": course.title,
        "topics": [{"id": topic.id, "title": topic.title} for topic in topics],
        "students": [
            {
                "id": student.id,
                "email": student.email,
                "mastery": {
                    topic.id: score_map[(student.id, topic.id)].score
                    if (student.id, topic.id) in score_map
                    else None
                    for topic in topics
                },
            }
            for student in students
        ],
    }
