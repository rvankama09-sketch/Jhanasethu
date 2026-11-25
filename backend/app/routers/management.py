from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.core.security import get_current_user
from app.core.time import utc_now
from app.database import get_db

router = APIRouter(prefix="/management", tags=["management"])


@router.get("/metrics")
def platform_metrics(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.role != models.RoleEnum.management:
        raise HTTPException(status_code=403, detail="Management role required")

    active_since = utc_now() - timedelta(days=7)
    active_students = (
        db.query(func.count(func.distinct(models.LearningActivity.user_id)))
        .join(models.User, models.User.id == models.LearningActivity.user_id)
        .filter(
            models.User.role == models.RoleEnum.student,
            models.LearningActivity.created_at >= active_since,
        )
        .scalar()
    )
    average_mastery = (
        db.query(func.avg(models.MasteryScore.score))
        .join(models.User, models.User.id == models.MasteryScore.user_id)
        .filter(models.User.role == models.RoleEnum.student)
        .scalar()
    )
    return {
        "student_count": db.query(models.User).filter(models.User.role == models.RoleEnum.student).count(),
        "faculty_count": db.query(models.User).filter(models.User.role == models.RoleEnum.instructor).count(),
        "course_count": db.query(models.Course).count(),
        "enrollment_count": db.query(models.CourseEnrollment).count(),
        "topic_count": db.query(models.Topic).count(),
        "activity_last_7_days": (
            db.query(models.LearningActivity)
            .join(models.User, models.User.id == models.LearningActivity.user_id)
            .filter(models.LearningActivity.created_at >= active_since)
            .filter(models.User.role == models.RoleEnum.student)
            .count()
        ),
        "active_students_last_7_days": active_students or 0,
        "average_mastery": average_mastery or 0.0,
    }


def _require_management(current_user: models.User) -> None:
    if current_user.role != models.RoleEnum.management:
        raise HTTPException(status_code=403, detail="Management role required")


@router.get("/drilldown")
def course_drilldown(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Institution -> course -> topic drill-down for the dimensions in this schema."""
    _require_management(current_user)
    result = []
    courses = db.query(models.Course).order_by(models.Course.title).all()
    for course in courses:
        student_ids = [enrollment.user_id for enrollment in course.enrollments]
        topics = (
            db.query(models.Topic)
            .filter(models.Topic.document_id == course.document_id)
            .order_by(models.Topic.order_index)
            .all()
        )
        scores = []
        if student_ids and topics:
            topic_ids = [topic.id for topic in topics]
            scores = (
                db.query(models.MasteryScore)
                .filter(
                    models.MasteryScore.user_id.in_(student_ids),
                    models.MasteryScore.topic_id.in_(topic_ids),
                )
                .all()
            )
        scores_by_topic: dict[str, list[float]] = {}
        for score in scores:
            scores_by_topic.setdefault(score.topic_id, []).append(score.score)
        result.append(
            {
                "course_id": course.id,
                "course_title": course.title,
                "faculty_email": course.owner.email,
                "student_count": len(student_ids),
                "topic_count": len(topics),
                "assessments_completed": sum(
                    activity.activity_type in {"quiz", "diagnostic_quiz"}
                    for activity in course.activities
                ),
                "average_mastery": (
                    sum(score.score for score in scores) / len(scores) if scores else 0.0
                ),
                "topics": [
                    {
                        "topic_id": topic.id,
                        "topic_title": topic.title,
                        "average_mastery": (
                            sum(scores_by_topic[topic.id]) / len(scores_by_topic[topic.id])
                            if scores_by_topic.get(topic.id)
                            else 0.0
                        ),
                        "student_count": len(scores_by_topic.get(topic.id, [])),
                    }
                    for topic in topics
                ],
            }
        )
    return result


@router.get("/adoption")
def adoption_and_interventions(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Operational signals and follow-up queue derived from recorded activity."""
    _require_management(current_user)
    now = utc_now()
    week_start = now - timedelta(days=7)
    month_start = now - timedelta(days=30)
    student_role = models.RoleEnum.student
    faculty_role = models.RoleEnum.instructor

    active_students = (
        db.query(func.count(func.distinct(models.LearningActivity.user_id)))
        .join(models.User, models.User.id == models.LearningActivity.user_id)
        .filter(
            models.User.role == student_role,
            models.LearningActivity.created_at >= week_start,
        )
        .scalar()
        or 0
    )
    active_faculty = (
        db.query(func.count(func.distinct(models.LearningActivity.user_id)))
        .join(models.User, models.User.id == models.LearningActivity.user_id)
        .filter(
            models.User.role == faculty_role,
            models.LearningActivity.created_at >= week_start,
        )
        .scalar()
        or 0
    )
    faculty_count = db.query(models.User).filter(models.User.role == faculty_role).count()
    completed_assessments = (
        db.query(models.QuizAttempt)
        .join(models.User, models.User.id == models.QuizAttempt.user_id)
        .filter(
            models.User.role == student_role,
            models.QuizAttempt.score.is_not(None),
            models.QuizAttempt.created_at >= month_start,
        )
        .count()
    )
    ready_syllabi = (
        db.query(models.Document)
        .filter(
            models.Document.document_type == "syllabus",
            models.Document.status == "ready",
        )
        .count()
    )
    mapped_topics = db.query(models.Topic).count()
    activity_rows = (
        db.query(models.LearningActivity)
        .join(models.User, models.User.id == models.LearningActivity.user_id)
        .filter(
            models.User.role == student_role,
            models.LearningActivity.created_at >= week_start,
        )
        .all()
    )
    daily_counts = {}
    for activity in activity_rows:
        day = activity.created_at.date().isoformat()
        daily_counts[day] = daily_counts.get(day, 0) + 1
    daily_activity = [
        {
            "date": (now - timedelta(days=offset)).date().isoformat(),
            "count": daily_counts.get((now - timedelta(days=offset)).date().isoformat(), 0),
        }
        for offset in range(6, -1, -1)
    ]

    weak_scores = (
        db.query(models.MasteryScore)
        .join(models.User, models.User.id == models.MasteryScore.user_id)
        .filter(
            models.User.role == student_role,
            models.MasteryScore.score < 0.60,
        )
        .all()
    )
    interventions_by_topic: dict[str, dict] = {}
    for score in weak_scores:
        if not score.topic:
            continue
        course = (
            db.query(models.Course)
            .filter(models.Course.document_id == score.topic.document_id)
            .first()
        )
        key = f"{course.id if course else 'unassigned'}:{score.topic_id}"
        row = interventions_by_topic.setdefault(
            key,
            {
                "topic_id": score.topic_id,
                "topic_title": score.topic.title,
                "course_title": course.title if course else "Unassigned syllabus",
                "total_score": 0.0,
                "student_count": 0,
            },
        )
        row["total_score"] += score.score
        row["student_count"] += 1
    interventions = [
        {
            **row,
            "average_mastery": row.pop("total_score") / row["student_count"],
        }
        for row in interventions_by_topic.values()
    ]
    interventions.sort(key=lambda row: row["average_mastery"])
    students_needing_support = len({score.user_id for score in weak_scores})

    return {
        "period_days": 7,
        "active_students": active_students,
        "active_faculty": active_faculty,
        "faculty_count": faculty_count,
        "completed_assessments_last_30_days": completed_assessments,
        "ready_syllabi": ready_syllabi,
        "mapped_topics": mapped_topics,
        "students_needing_support": students_needing_support,
        "course_count": db.query(models.Course).count(),
        "enrollment_count": db.query(models.CourseEnrollment).count(),
        "daily_activity": daily_activity,
        "interventions": interventions,
    }
