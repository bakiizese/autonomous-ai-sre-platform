from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.db.models import PollRun
from app.schemas.api import PollStatusOut
from app.services.poller_service import poll_trigger_event

router = APIRouter(prefix="/api/poll", tags=["poll"])


@router.post("/trigger-now", status_code=status.HTTP_202_ACCEPTED)
async def trigger_poll_now():
    """Signals the running poll loop rather than running a second concurrent
    cycle — see poller_service.poll_loop()'s asyncio.wait_for on this event."""
    poll_trigger_event.set()
    return {"status": "triggered"}


@router.get("/status", response_model=PollStatusOut)
def poll_status(db: Session = Depends(get_db)):
    last_run = db.query(PollRun).order_by(PollRun.started_at.desc()).first()
    return PollStatusOut(
        poll_interval_seconds=settings.POLL_INTERVAL_SECONDS,
        last_run=(
            {
                "id": last_run.id,
                "started_at": last_run.started_at.isoformat(),
                "completed_at": last_run.completed_at.isoformat() if last_run.completed_at else None,
                "trigger_type": last_run.trigger_type.value,
                "repos_polled": last_run.repos_polled,
                "new_issues_found": last_run.new_issues_found,
                "error_message": last_run.error_message,
            }
            if last_run
            else None
        ),
    )
