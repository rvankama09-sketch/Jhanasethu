from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.security import get_current_user
from app.database import get_db

router = APIRouter(prefix="/topics", tags=["topics"])


@router.get("/", response_model=list[schemas.TopicOut])
def list_topics(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if current_user.role == models.RoleEnum.management:
        raise HTTPException(status_code=403, detail="Learning content is not available for this role")

    course_document_ids = []
    if current_user.role == models.RoleEnum.student:
        course_document_ids = [
            course.document_id
            for course in db.query(models.Course)
            .join(models.CourseEnrollment)
            .filter(models.CourseEnrollment.user_id == current_user.id)
            .all()
        ]
    topics = (
        db.query(models.Topic)
        .join(models.Document)
        .filter(
            (models.Document.user_id == current_user.id)
            | models.Document.id.in_(course_document_ids)
        )
        .order_by(models.Topic.order_index)
        .all()
    )
    return topics
