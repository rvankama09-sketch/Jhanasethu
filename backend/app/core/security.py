from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.time import utc_now
from app.database import get_db
from app import models

settings = get_settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

# Using the `bcrypt` library directly (rather than passlib's CryptContext)
# sidesteps a passlib<->bcrypt>=4.1 backend-detection incompatibility.
# bcrypt has a hard 72-byte input limit; truncate defensively like the
# library itself recommends.


def hash_password(password: str) -> str:
    truncated = password.encode("utf-8")[:72]
    return bcrypt.hashpw(truncated, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    truncated = plain.encode("utf-8")[:72]
    try:
        return bcrypt.checkpw(truncated, hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(subject: str, expires_minutes: Optional[int] = None) -> str:
    expire = utc_now() + timedelta(
        minutes=expires_minutes or settings.access_token_expire_minutes
    )
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> str:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        user_id = payload.get("sub")
        if not user_id:
            raise JWTError("missing subject")
        return user_id
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> models.User:
    user_id = decode_token(token)
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def require_instructor(user: models.User = Depends(get_current_user)) -> models.User:
    if user.role != models.RoleEnum.instructor:
        raise HTTPException(status_code=403, detail="Instructor role required")
    return user


def can_access_topic(db: Session, user: models.User, topic: models.Topic) -> bool:
    document = topic.document
    if not document:
        return False
    if document.user_id == user.id:
        return True
    if user.role != models.RoleEnum.student:
        return False

    return (
        db.query(models.CourseEnrollment)
        .join(models.Course, models.Course.id == models.CourseEnrollment.course_id)
        .filter(
            models.CourseEnrollment.user_id == user.id,
            models.Course.document_id == document.id,
        )
        .first()
        is not None
    )


def activity_course_id(db: Session, user_id: str, topic: models.Topic | None) -> str | None:
    if topic is None:
        return None
    enrollment = (
        db.query(models.CourseEnrollment)
        .join(models.Course, models.Course.id == models.CourseEnrollment.course_id)
        .filter(
            models.CourseEnrollment.user_id == user_id,
            models.Course.document_id == topic.document_id,
        )
        .order_by(models.CourseEnrollment.joined_at)
        .first()
    )
    return enrollment.course_id if enrollment else None


def active_assessment(db: Session, user: models.User) -> models.ScheduledAssessment | None:
    if user.role != models.RoleEnum.student:
        return None
    now = utc_now()
    assessments = (
        db.query(models.ScheduledAssessment)
        .join(
            models.CourseEnrollment,
            models.CourseEnrollment.course_id == models.ScheduledAssessment.course_id,
        )
        .filter(
            models.CourseEnrollment.user_id == user.id,
            models.ScheduledAssessment.status == "scheduled",
            models.ScheduledAssessment.scheduled_at.is_not(None),
            models.ScheduledAssessment.scheduled_at <= now,
            models.ScheduledAssessment.ai_support_enabled.is_(False),
        )
        .all()
    )
    return next(
        (
            assessment
            for assessment in assessments
            if now
            < assessment.scheduled_at.replace(tzinfo=None)
            + timedelta(minutes=assessment.duration_minutes)
        ),
        None,
    )


def ensure_ai_support_allowed(db: Session, user: models.User) -> None:
    assessment = active_assessment(db, user)
    if assessment:
        raise HTTPException(
            status_code=403,
            detail="AI assistance is disabled during this scheduled assessment",
        )
