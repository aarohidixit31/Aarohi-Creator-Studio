import os
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from .. import schemas
from ..auth import get_current_admin
from ..database import get_db
from ..services.youtube_oauth import (
    authorization_url,
    complete_authorization,
    connection_status,
    disconnect,
    validate_state,
)


router = APIRouter(prefix="/api/youtube/oauth", tags=["youtube-oauth"])


@router.get("/status", response_model=schemas.YouTubeOAuthStatus)
def youtube_oauth_status(db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    return connection_status(db)


@router.get("/start")
def start_youtube_oauth(admin=Depends(get_current_admin)):
    try:
        return {"authorization_url": authorization_url()}
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/callback")
def youtube_oauth_callback(
    code: str = Query(default=""),
    state: str = Query(default=""),
    error: str = Query(default=""),
    db: Session = Depends(get_db),
):
    frontend = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
    try:
        validate_state(state)
        if error:
            raise RuntimeError("YouTube authorization was cancelled")
        if not code:
            raise RuntimeError("Google did not return an authorization code")
        complete_authorization(db, code)
        return RedirectResponse(f"{frontend}/admin/content?{urlencode({'youtube': 'connected'})}")
    except RuntimeError as exc:
        return RedirectResponse(f"{frontend}/admin/content?{urlencode({'youtube': 'error', 'message': str(exc)[:180]})}")


@router.delete("/connection", status_code=204)
def disconnect_youtube(db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    disconnect(db)
