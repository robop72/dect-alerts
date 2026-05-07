import csv
import io
import logging
from datetime import datetime
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
    Upload a CSV or XLSX roster.
    CSV: columns staff_name, role, phone_number, zone_id (opt), on_duty (opt)
    XLSX: weekly schedule with columns Staff Name, Monday…Sunday and values AM/PM/Night/OFF
    """
    if not db.get(Facility, facility_id):
        raise HTTPException(status_code=404, detail="Facility not found")

    content = await file.read()
    filename = (file.filename or "").lower()
    added = 0

    if filename.endswith(".xlsx"):
        import openpyxl

        wb = openpyxl.load_workbook(io.BytesIO(content))
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            raise HTTPException(status_code=400, detail="Empty spreadsheet")

        header = [str(c).strip() if c else "" for c in rows[0]]
        today_name = datetime.now().strftime("%A")  # e.g. "Wednesday"
        if today_name not in header:
            raise HTTPException(
                status_code=400,
                detail=f"Column '{today_name}' not found in spreadsheet. Headers: {header}",
            )
        day_col = header.index(today_name)
        name_col = next((i for i, h in enumerate(header) if "name" in h.lower()), 0)

        shift_role = {"AM": "Day Nurse", "PM": "Evening Nurse", "Night": "Night Nurse"}

        for row in rows[1:]:
            if not row or not row[name_col]:
                continue
            name = str(row[name_col]).strip()
            shift = str(row[day_col]).strip() if row[day_col] else "OFF"
            on_duty = shift.upper() != "OFF"
            role = shift_role.get(shift, shift if on_duty else "Staff")
            entry = RosterEntry(
                facility_id=facility_id,
                staff_name=name,
                role=role,
                phone_number="",
                on_duty=on_duty,
            )
            db.add(entry)
            added += 1

        db.commit()
        on_duty_count = sum(
            1 for r in rows[1:] if r and r[day_col] and str(r[day_col]).upper() != "OFF"
        )
        return {
            "added": added,
            "facility_id": facility_id,
            "on_duty_today": on_duty_count,
            "note": "Phone numbers not in spreadsheet — add them via the API or edit the DB before triggering calls.",
        }

    else:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
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
