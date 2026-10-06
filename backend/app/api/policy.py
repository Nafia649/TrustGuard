import json
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.policy import PolicyVersion
from app.schemas.policy import (
    PolicyConfig,
    PolicyUpdateRequest,
    PolicyResponse,
)
from app.services.policy_engine import (
    get_active_policy_record,
    update_policy_version,
)

router = APIRouter(tags=["Policy"])


@router.get(
    "/policy",
    response_model=PolicyResponse,
    summary="Get active policy configuration",
)
def get_policy(db: Session = Depends(get_db)):
    """
    Retrieves the currently active policy configuration including risk score thresholds,
    caps, and authorized signer roles.
    """
    record = get_active_policy_record(db)
    config = PolicyConfig(**json.loads(record.policy_json))
    return PolicyResponse(
        version=record.version,
        policy=config,
        created_at=record.created_at,
        created_by=record.created_by,
        active=record.active,
    )


@router.put(
    "/policy",
    response_model=PolicyResponse,
    summary="Update policy configuration (Creates new version)",
)
def update_policy(
    update_in: PolicyUpdateRequest,
    db: Session = Depends(get_db),
):
    """
    Updates the routing policy configuration.
    Enforces policy versioning: creates a new immutable PolicyVersion record,
    deactivates historical versions, and records a hash-chained audit event.
    """
    try:
        new_record = update_policy_version(
            db=db,
            update_data=update_in,
            user_id=update_in.changed_by,
        )
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        )

    config = PolicyConfig(**json.loads(new_record.policy_json))
    return PolicyResponse(
        version=new_record.version,
        policy=config,
        created_at=new_record.created_at,
        created_by=new_record.created_by,
        active=new_record.active,
    )


@router.get(
    "/policy/history",
    response_model=List[PolicyResponse],
    summary="List all historical policy versions",
)
def list_policy_history(db: Session = Depends(get_db)):
    """
    Returns the complete audit history of all policy versions.
    """
    records = db.query(PolicyVersion).order_by(PolicyVersion.version.desc()).all()
    history = []
    for r in records:
        config = PolicyConfig(**json.loads(r.policy_json))
        history.append(
            PolicyResponse(
                version=r.version,
                policy=config,
                created_at=r.created_at,
                created_by=r.created_by,
                active=r.active,
            )
        )
    return history
