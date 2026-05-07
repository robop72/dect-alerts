from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import AlertResponse
from ..services.reporting import get_recent_alerts, get_summary

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/summary")
def summary(facility_id: Optional[int] = None, db: Session = Depends(get_db)):
    return get_summary(db, facility_id)


@router.get("/recent", response_model=list[AlertResponse])
def recent_alerts(limit: int = 50, facility_id: Optional[int] = None, db: Session = Depends(get_db)):
    return get_recent_alerts(db, limit, facility_id)
