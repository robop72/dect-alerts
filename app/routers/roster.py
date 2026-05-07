import csv
import io
import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Facility, RosterEntry, Zone
from ..schemas import FacilityCreate, FacilityResponse, RosterEntryCreate, RosterEntryResponse, ZoneCreate, ZoneResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["roster"])


# ── Facilities ────────────────────────────────────────────────────────────────

@router.post("/facilities", response_model=FacilityResponse)
def create_facility(payload: FacilityCreate, db: Session = Depends(get_db)):
    facility = Facility(**payload.model_dump())
    db.add(facility)
    db.commit()
    db.refresh(facility)
    return facility


@router.get("/facilities", response_model=list[FacilityResponse])
def list_facilities(db: Session = Depends(get_db)):
    return db.query(Facility).all()


# ── Zones ─────────────────────────────────────────────────────────────────────

@router.post("/zones", response_model=ZoneResponse)
def create_zone(payload: ZoneCreate, db: Session = Depends(get_db)):
    if not db.get(Facility, payload.facility_id):
        raise HTTPException(status_code=404, detail="Facility not found")
    zone = Zone(**payload.model_dump())
    db.add(zone)
    db.commit()
    db.refresh(zone)
    return zone


@router.get("/zones", response_model=list[ZoneResponse])
def list_zones(facility_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(Zone)
    if facility_id:
        q = q.filter(Zone.facility_id == facility_id)
    return q.all()


# ── Roster ────────────────────────────────────────────────────────────────────

@router.post("/roster", response_model=RosterEntryResponse)
def add_roster_entry(payload: RosterEntryCreate, db: Session = Depends(get_db)):
    entry = RosterEntry(**payload.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/roster", response_model=list[RosterEntryResponse])
def list_roster(facility_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(RosterEntry)
    if facility_id:
        q = q.filter(RosterEntry.facility_id == facility_id)
    return q.all()


@router.post("/roster/upload-csv")
async def upload_roster_csv(
    facility_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload a CSV roster. Expected columns:
    staff_name, role, phone_number, zone_id (optional), on_duty (optional, default true)
    """
    if not db.get(Facility, facility_id):
        raise HTTPException(status_code=404, detail="Facility not found")

    content = await file.read()
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    added = 0
    for row in reader:
        entry = RosterEntry(
            facility_id=facility_id,
            staff_name=row["staff_name"].strip(),
            role=row["role"].strip(),
            phone_number=row["phone_number"].strip(),
            zone_id=int(row["zone_id"]) if row.get("zone_id", "").strip() else None,
            on_duty=row.get("on_duty", "true").strip().lower() != "false",
        )
        db.add(entry)
        added += 1

    db.commit()
    return {"added": added, "facility_id": facility_id}
