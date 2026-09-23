from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models import Repo
from app.schemas.api import SubscribeRequest
from app.services import notification_service

router = APIRouter(tags=["subscribers"])


@router.post("/api/repos/{repo_id}/subscribe")
def subscribe(repo_id: int, request: SubscribeRequest, db: Session = Depends(get_db)):
    repo = db.get(Repo, repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repo not found")
    subscriber = notification_service.subscribe(db, request.email, repo_id)
    return {"status": "subscribed", "email": subscriber.email}


@router.get("/api/unsubscribe/{token}", response_class=HTMLResponse)
def unsubscribe(token: str, db: Session = Depends(get_db)):
    ok = notification_service.unsubscribe(db, token)
    if not ok:
        raise HTTPException(status_code=404, detail="Unknown unsubscribe token")
    return "<html><body><p>You've been unsubscribed from Sentinel SRE alerts.</p></body></html>"
