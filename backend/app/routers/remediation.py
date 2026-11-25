from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.agent.remediation import generate_remediation
from app.core.security import can_access_topic, get_current_user
from app.database import get_db
from app.llm.factory import get_llm_provider

router = APIRouter(prefix="/remediation", tags=["remediation"])


@router.post("/micro-module", response_model=schemas.RemediationOut)
def micro_module(
    payload: schemas.RemediationRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    topic = db.query(models.Topic).filter(models.Topic.id == payload.topic_id).first()
    if not topic or not can_access_topic(db, current_user, topic):
        raise HTTPException(status_code=404, detail="Topic not found")

    llm = get_llm_provider()
    try:
        result = generate_remediation(
            db, llm, current_user.id, payload.topic_id, payload.sub_concept
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return schemas.RemediationOut(**result)
