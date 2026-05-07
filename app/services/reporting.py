from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import Alert


def get_summary(db: Session, facility_id: Optional[int] = None) -> dict:
    q = db.query(Alert)
    if facility_id:
        q = q.filter(Alert.facility_id == facility_id)

    total = q.count()
    acknowledged = q.filter(Alert.status == "acknowledged").count()
    escalated = q.filter(Alert.status == "escalated").count()

    avg_q = db.query(func.avg(Alert.response_time_seconds)).filter(Alert.status == "acknowledged")
    if facility_id:
        avg_q = avg_q.filter(Alert.facility_id == facility_id)
    avg_response = avg_q.scalar()

    return {
        "total": total,
        "acknowledged": acknowledged,
        "escalated": escalated,
        "pending": q.filter(Alert.status.in_(["pending", "calling"])).count(),
        "avg_response_seconds": round(avg_response, 1) if avg_response else None,
    }


def get_recent_alerts(db: Session, limit: int = 50, facility_id: Optional[int] = None):
    q = db.query(Alert).order_by(Alert.timestamp_received.desc())
    if facility_id:
        q = q.filter(Alert.facility_id == facility_id)
    return q.limit(limit).all()
