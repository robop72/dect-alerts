import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import Alert, Facility, RosterEntry
from ..schemas import AlertCreate, AlertResponse
from ..services import telephony, tts

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/alerts", tags=["alerts"])


def _log(alert: Alert, message: str):
    ts = datetime.utcnow().isoformat()
    alert.full_log = (alert.full_log or "") + f"\n[{ts}] {message}"


@router.post("/simulate-alert", response_model=AlertResponse)
def simulate_alert(payload: AlertCreate, db: Session = Depends(get_db)):
    facility = db.get(Facility, payload.facility_id)
    if not facility:
        raise HTTPException(status_code=404, detail="Facility not found")

    # Low-risk bed exit → log only, no call
    if payload.risk_level == "low":
        alert = Alert(
            facility_id=payload.facility_id,
            zone_id=payload.zone_id,
            alert_type=payload.alert_type,
            room_number=payload.room_number,
            risk_level="low",
            status="acknowledged",
            acknowledged_at=datetime.utcnow(),
            response_time_seconds=0,
            used_telephony="none",
            full_log="",
        )
        _log(alert, f"LOW-RISK alert received — {payload.alert_type} Room {payload.room_number} — no escalation")
        db.add(alert)
        db.commit()
        db.refresh(alert)
        return alert

    alert = Alert(
        facility_id=payload.facility_id,
        zone_id=payload.zone_id,
        alert_type=payload.alert_type,
        room_number=payload.room_number,
        risk_level=payload.risk_level,
        status="pending",
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    _log(alert, f"Alert received — {payload.alert_type} Room {payload.room_number} ({payload.risk_level} risk)")

    # Roster lookup — find on-duty staff for this zone/facility
    staff = (
        db.query(RosterEntry)
        .filter(
            RosterEntry.facility_id == payload.facility_id,
            RosterEntry.on_duty == True,
        )
        .first()
    )

    if not staff:
        _log(alert, "No on-duty staff found — alert pending manual response")
        db.commit()
        return alert

    _log(alert, f"Roster match: {staff.staff_name} ({staff.role}) → {staff.phone_number}")

    if settings.DEMO_MODE and not settings.TWILIO_ACCOUNT_SID:
        alert.status = "calling"
        _log(alert, "DEMO MODE — simulated call initiated (use 'Simulate Press 1' to acknowledge)")
        alert.used_telephony = "simulated"
        db.commit()
        db.refresh(alert)
        return alert

    # Generate TTS audio
    try:
        tts.generate_alert_audio(payload.alert_type, payload.room_number, facility.location, alert.id)
        _log(alert, f"TTS audio generated ({facility.location} voice)")
    except Exception as e:
        _log(alert, f"TTS generation failed: {e} — falling back to Twilio <Say>")

    # Build TwiML webhook URL
    twiml_url = f"{settings.PUBLIC_BASE_URL}/alerts/twiml/{alert.id}"

    call_sid = telephony.make_twilio_call(
        to_number=staff.phone_number,
        twiml_url=twiml_url,
        from_number=settings.TWILIO_FROM_NUMBER,
        account_sid=settings.TWILIO_ACCOUNT_SID,
        auth_token=settings.TWILIO_AUTH_TOKEN,
    )

    if call_sid:
        alert.status = "calling"
        alert.used_telephony = "twilio"
        _log(alert, f"Twilio call started — SID: {call_sid}")
    else:
        _log(alert, "Twilio call failed — alert remains pending")

    db.commit()
    db.refresh(alert)
    return alert


@router.api_route("/twiml/{alert_id}", methods=["GET", "POST"], response_class=HTMLResponse)
def twiml_handler(alert_id: int, db: Session = Depends(get_db)):
    """Returns TwiML that plays the alert and waits for DTMF '1'."""
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    facility = db.get(Facility, alert.facility_id)
    location = facility.location if facility else "NA"
    lang_map  = {"AU": "en-AU",       "NA": "en-US",        "UK": "en-GB"}
    voice_map = {"AU": "alice", "NA": "alice", "UK": "alice"}
    lang  = lang_map.get(location.upper(), "en-US")
    voice = voice_map.get(location.upper(), "Polly.Joanna")

    message = f"{alert.alert_type} in Room {alert.room_number}."
    action_url = f"{settings.PUBLIC_BASE_URL}/alerts/dtmf/{alert_id}"

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Gather numDigits="1" action="{action_url}" method="POST" timeout="60">
    <Say language="{lang}" voice="{voice}">{message}</Say>
    <Say language="{lang}" voice="{voice}">Press 1 now to acknowledge this alert.</Say>
  </Gather>
  <Redirect method="POST">{settings.PUBLIC_BASE_URL}/alerts/twiml/{alert_id}</Redirect>
</Response>"""
    return HTMLResponse(content=twiml, media_type="application/xml")


@router.post("/dtmf/{alert_id}", response_class=HTMLResponse)
def dtmf_handler(alert_id: int, Digits: str = Form(default=""), db: Session = Depends(get_db)):
    """Twilio posts DTMF digits here after the caller presses a key."""
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    if Digits == "1":
        _acknowledge_alert(alert)
        db.commit()
        _log(alert, f"DTMF '1' received — acknowledged via Twilio call")
        db.commit()
        twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response><Say>Alert acknowledged. Thank you.</Say><Hangup/></Response>"""
    else:
        _log(alert, f"DTMF '{Digits}' received — ignored (only '1' accepted)")
        db.commit()
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say>Invalid input. Please press 1 to acknowledge.</Say>
  <Redirect>{settings.PUBLIC_BASE_URL}/alerts/twiml/{alert_id}</Redirect>
</Response>"""

    return HTMLResponse(content=twiml, media_type="application/xml")


@router.post("/acknowledge/{alert_id}", response_model=AlertResponse)
def acknowledge_alert(alert_id: int, db: Session = Depends(get_db)):
    """Manual acknowledge endpoint."""
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert.status == "acknowledged":
        return alert
    _acknowledge_alert(alert)
    _log(alert, "Acknowledged via API")
    db.commit()
    db.refresh(alert)
    return alert


@router.post("/simulate-ack/{alert_id}", response_class=HTMLResponse)
def simulate_ack(alert_id: int, db: Session = Depends(get_db)):
    """Demo: simulate the user pressing '1' on their phone."""
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert.status == "acknowledged":
        return HTMLResponse(content="<span class='badge acknowledged'>Already acknowledged</span>")
    _acknowledge_alert(alert)
    _log(alert, "Simulated Press 1 — acknowledged via dashboard button")
    db.commit()
    db.refresh(alert)
    mins = max(1, round(alert.response_time_seconds / 60))
    return HTMLResponse(
        content=f"<span class='badge acknowledged'>Acknowledged in {mins} min</span>"
    )


def _acknowledge_alert(alert: Alert):
    now = datetime.now(timezone.utc)
    received = alert.timestamp_received
    if received.tzinfo is None:
        received = received.replace(tzinfo=timezone.utc)
    alert.acknowledged_at = now
    alert.response_time_seconds = (now - received).total_seconds()
    alert.status = "acknowledged"
