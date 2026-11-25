import hmac

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import func

from app import models, schemas
from app.core.security import hash_password, verify_password, create_access_token, get_current_user
from app.core.config import get_settings
from app.database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=schemas.Token, status_code=201)
def signup(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    email = payload.email.lower()
    existing = db.query(models.User).filter(func.lower(models.User.email) == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    settings = get_settings()
    is_management_email = email in settings.management_email_list
    if payload.role == "management" and not is_management_email:
        raise HTTPException(status_code=403, detail="Management signup is not authorized for this email")
    if payload.management_token and not is_management_email:
        raise HTTPException(status_code=403, detail="Management signup is not authorized for this email")
    if is_management_email:
        if not settings.management_signup_token:
            raise HTTPException(status_code=503, detail="Management signup is not configured")
        if not payload.management_token or not hmac.compare_digest(
            payload.management_token, settings.management_signup_token
        ):
            raise HTTPException(status_code=403, detail="Invalid Management signup token")
        role = models.RoleEnum.management
    else:
        role = models.RoleEnum.instructor if payload.role == "instructor" else models.RoleEnum.student
    user = models.User(email=email, hashed_password=hash_password(payload.password), role=role)
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(subject=user.id)
    return schemas.Token(access_token=token)


@router.post("/login", response_model=schemas.Token)
def login(payload: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(func.lower(models.User.email) == payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(subject=user.id)
    return schemas.Token(access_token=token)

@router.post("/token", response_model=schemas.Token)
def token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = (
        db.query(models.User)
        .filter(func.lower(models.User.email) == form_data.username.lower())
        .first()
    )

    if not user or not verify_password(
        form_data.password,
        user.hashed_password,
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        )

    token = create_access_token(subject=user.id)
    return schemas.Token(access_token=token)

@router.get("/me", response_model=schemas.UserOut)
def me(current_user: models.User = Depends(get_current_user)):
    return current_user
