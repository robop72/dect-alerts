from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class FacilityCreate(BaseModel):
    name: str
    location: str  # AU / NA / UK
    voice_lang: str = "en-au"
    twilio_phone_number: Optional[str] = None


class FacilityResponse(BaseModel):
    id: int
    name: str
    location: str
    voice_lang: str
    twilio_phone_number: Optional[str]

    model_config = {"from_attributes": True}


class ZoneCreate(BaseModel):
    facility_id: int
    name: str
    sip_address: Optional[str] = None
    twilio_number: Optional[str] = None


class ZoneResponse(BaseModel):
    id: int
    facility_id: int
    name: str
    sip_address: Optional[str]
    twilio_number: Optional[str]

    model_config = {"from_attributes": True}


class AlertCreate(BaseModel):
    facility_id: int
    alert_type: str
    room_number: str
    zone_id: Optional[int] = None
    risk_level: str = "high"


class AlertResponse(BaseModel):
    id: int
    facility_id: int
    zone_id: Optional[int]
    alert_type: str
    room_number: str
    risk_level: str
    timestamp_received: datetime
    status: str
    acknowledged_at: Optional[datetime]
    response_time_seconds: Optional[float]
    used_telephony: Optional[str]
    full_log: str

    model_config = {"from_attributes": True}


class RosterEntryCreate(BaseModel):
    facility_id: int
    zone_id: Optional[int] = None
    staff_name: str
    role: str
    phone_number: str
    on_duty: bool = True


class RosterEntryResponse(BaseModel):
    id: int
    facility_id: int
    zone_id: Optional[int]
    staff_name: str
    role: str
    phone_number: str
    on_duty: bool

    model_config = {"from_attributes": True}
