from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .database import Base


class Facility(Base):
    __tablename__ = "facilities"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    location = Column(String, nullable=False)  # AU / NA / UK
    voice_lang = Column(String, default="en-au")
    twilio_phone_number = Column(String, nullable=True)

    zones = relationship("Zone", back_populates="facility", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="facility", cascade="all, delete-orphan")
    roster = relationship("RosterEntry", back_populates="facility", cascade="all, delete-orphan")


class Zone(Base):
    __tablename__ = "zones"

    id = Column(Integer, primary_key=True, index=True)
    facility_id = Column(Integer, ForeignKey("facilities.id"), nullable=False)
    name = Column(String, nullable=False)
    sip_address = Column(String, nullable=True)
    twilio_number = Column(String, nullable=True)

    facility = relationship("Facility", back_populates="zones")
    roster = relationship("RosterEntry", back_populates="zone")


class RosterEntry(Base):
    __tablename__ = "roster"

    id = Column(Integer, primary_key=True, index=True)
    facility_id = Column(Integer, ForeignKey("facilities.id"), nullable=False)
    zone_id = Column(Integer, ForeignKey("zones.id"), nullable=True)
    staff_name = Column(String, nullable=False)
    role = Column(String, nullable=False)
    phone_number = Column(String, nullable=False)
    on_duty = Column(Boolean, default=True)

    facility = relationship("Facility", back_populates="roster")
    zone = relationship("Zone", back_populates="roster")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    facility_id = Column(Integer, ForeignKey("facilities.id"), nullable=False)
    zone_id = Column(Integer, ForeignKey("zones.id"), nullable=True)
    alert_type = Column(String, nullable=False)
    room_number = Column(String, nullable=False)
    risk_level = Column(String, default="high")  # low / high
    timestamp_received = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="pending")  # pending / calling / acknowledged / escalated / no_response
    acknowledged_at = Column(DateTime, nullable=True)
    response_time_seconds = Column(Float, nullable=True)
    used_telephony = Column(String, nullable=True)  # twilio / pjsua2 / simulated
    full_log = Column(Text, default="")

    facility = relationship("Facility", back_populates="alerts")
