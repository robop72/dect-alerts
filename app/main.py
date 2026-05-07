import logging
import math
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from .config import settings
from .database import Base, engine, get_db
from .models import Alert, Facility, RosterEntry, Zone
from .routers import alerts, reports, roster
from .services.escalation import start_scheduler, stop_scheduler
from .services.reporting import get_recent_alerts, get_summary
from .templating import templates

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _seed_demo_data()
    start_scheduler()
    yield
    stop_scheduler()


def _seed_demo_data():
    """Insert a demo facility, zone, and roster if the DB is empty."""
    from .database import SessionLocal

    db = SessionLocal()
    try:
        if db.query(Facility).count() == 0:
            facility = Facility(
                name="Sunrise Aged Care — Melbourne",
                location="AU",
                voice_lang="en-au",
                twilio_phone_number="",
            )
            db.add(facility)
            db.flush()

            zone_a = Zone(facility_id=facility.id, name="Zone A1 — East Wing", sip_address="sip:zone-a1@pbx.local")
            db.add(zone_a)
            db.flush()

            staff = RosterEntry(
                facility_id=facility.id,
                zone_id=zone_a.id,
                staff_name="Sarah Mitchell",
                role="Registered Nurse",
                phone_number="+61417327131",
                on_duty=True,
            )
            db.add(staff)
            db.commit()
            logger.info("Demo data seeded — facility ID 1 ready")
    except Exception as e:
        logger.error(f"Seed error: {e}")
        db.rollback()
    finally:
        db.close()


app = FastAPI(title="Pontosense Response Assurance Layer", version="1.2.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
app.include_router(alerts.router)
app.include_router(roster.router)
app.include_router(reports.router)


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    facilities = db.query(Facility).all()
    recent = get_recent_alerts(db, limit=20)
    summary = get_summary(db)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "facilities": facilities,
            "alerts": recent,
            "summary": summary,
            "demo_mode": settings.DEMO_MODE,
        },
    )


@app.get("/partials/alerts", response_class=HTMLResponse)
def partial_alerts(request: Request, facility_id: int = None, db: Session = Depends(get_db)):
    alerts_list = get_recent_alerts(db, limit=20, facility_id=facility_id)
    summary = get_summary(db, facility_id)
    return templates.TemplateResponse(
        "partials/alerts_table.html",
        {
            "request": request,
            "alerts": alerts_list,
            "summary": summary,
            "demo_mode": settings.DEMO_MODE,
        },
    )
