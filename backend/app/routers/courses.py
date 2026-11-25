import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.security import get_current_user
from app.database import get_db

router = APIRouter(prefix="/courses", tags=["courses"])


def _course_summary(course: models.Course, include_code: bool) -> dict:
    student_count = len(course.enrollments)
    return {
        "id": course.id,
        "title": course.title,
        "description": course.description,
        "document_id": course.document_id,
        "document_name": course.document.filename if course.document else "",
        "document_status": course.document.status if course.document else "failed",
        "join_code": course.join_code if include_code else None,
        "student_count": student_count,
        "created_at": course.created_at,
    }


@router.get("/")
def list_courses(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.role == models.RoleEnum.instructor:
        courses = (
            db.query(models.Course)
            .filter(models.Course.owner_id == current_user.id)
            .order_by(models.Course.created_at.desc())
            .all()
        )
        return [_course_summary(course, include_code=True) for course in courses]
    if current_user.role == models.RoleEnum.student:
        courses = (
            db.query(models.Course)
            .join(models.CourseEnrollment)
            .filter(models.CourseEnrollment.user_id == current_user.id)
            .order_by(models.Course.created_at.desc())
            .all()
        )
        return [_course_summary(course, include_code=False) for course in courses]
    raise HTTPException(status_code=403, detail="Courses are not available for this role")


@router.post("/", status_code=201)
def create_course(
    payload: schemas.CourseCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.role != models.RoleEnum.instructor:
        raise HTTPException(status_code=403, detail="Faculty role required")
    title = payload.title.strip()
    if not title or len(title) > 160:
        raise HTTPException(status_code=400, detail="Course title must be between 1 and 160 characters")

    document = (
        db.query(models.Document)
        .filter(
            models.Document.id == payload.document_id,
            models.Document.user_id == current_user.id,
            models.Document.document_type == "syllabus",
            models.Document.status == "ready",
        )
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail="Ready syllabus not found")

    join_code = secrets.token_hex(4).upper()
    while db.query(models.Course).filter(models.Course.join_code == join_code).first():
        join_code = secrets.token_hex(4).upper()
    course = models.Course(
        owner_id=current_user.id,
        document_id=document.id,
        title=title,
        description=payload.description.strip() if payload.description else None,
        join_code=join_code,
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return _course_summary(course, include_code=True)


@router.post("/join", status_code=201)
def join_course(
    payload: schemas.CourseJoin,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.role != models.RoleEnum.student:
        raise HTTPException(status_code=403, detail="Student role required")
    course = (
        db.query(models.Course)
        .filter(models.Course.join_code == payload.join_code.strip().upper())
        .first()
    )
    if not course:
        raise HTTPException(status_code=404, detail="Course code not found")
    enrollment = (
        db.query(models.CourseEnrollment)
        .filter(
            models.CourseEnrollment.course_id == course.id,
            models.CourseEnrollment.user_id == current_user.id,
        )
        .first()
    )
    if not enrollment:
        db.add(models.CourseEnrollment(course_id=course.id, user_id=current_user.id))
        db.commit()
        db.refresh(course)
    return _course_summary(course, include_code=False)


@router.get("/{course_id}")
def get_course(
    course_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    course = db.query(models.Course).filter(models.Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    owns_course = (
        current_user.role == models.RoleEnum.instructor
        and course.owner_id == current_user.id
    )
    enrolled = (
        current_user.role == models.RoleEnum.student
        and db.query(models.CourseEnrollment)
        .filter(
            models.CourseEnrollment.course_id == course.id,
            models.CourseEnrollment.user_id == current_user.id,
        )
        .first()
        is not None
    )
    if not owns_course and not enrolled:
        raise HTTPException(status_code=404, detail="Course not found")

    topics = (
        db.query(models.Topic)
        .filter(models.Topic.document_id == course.document_id)
        .order_by(models.Topic.order_index)
        .all()
    )
    return {
        **_course_summary(course, include_code=owns_course),
        "topics": [
            {"id": topic.id, "title": topic.title, "difficulty": topic.difficulty}
            for topic in topics
        ],
    }
