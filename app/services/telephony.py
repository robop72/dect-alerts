import logging
from typing import Optional

logger = logging.getLogger(__name__)


def make_twilio_call(
    to_number: str,
    twiml_url: str,
    from_number: str,
    account_sid: str,
    auth_token: str,
) -> Optional[str]:
    """Initiate a Twilio call and return the call SID, or None on failure."""
    if not account_sid or not auth_token or not from_number:
        logger.warning("Twilio credentials not configured — call skipped")
        return None
    try:
        from twilio.rest import Client

        client = Client(account_sid, auth_token)
        call = client.calls.create(to=to_number, from_=from_number, url=twiml_url)
        logger.info(f"Twilio call started: {call.sid} → {to_number}")
        return call.sid
    except Exception as e:
        logger.error(f"Twilio call failed: {e}")
        return None


def make_pjsua2_call(sip_address: str, wav_path: str) -> Optional[str]:
    """pjsua2 stub — swap this service in when Grandstream hardware arrives."""
    logger.info(f"[pjsua2 STUB] Would call {sip_address} playing {wav_path}")
    return None
