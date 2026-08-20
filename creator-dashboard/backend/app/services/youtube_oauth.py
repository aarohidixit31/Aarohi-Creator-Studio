import base64
import hashlib
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from .. import models
from ..auth import ALGORITHM, SECRET_KEY


PROVIDER = "youtube"
SCOPES = (
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
)


def oauth_configured() -> bool:
    return all(os.getenv(name, "").strip() for name in (
        "GOOGLE_OAUTH_CLIENT_ID",
        "GOOGLE_OAUTH_CLIENT_SECRET",
        "GOOGLE_OAUTH_REDIRECT_URI",
    ))


def _config() -> tuple[str, str, str]:
    client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
    redirect_uri = os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "").strip()
    if not client_id or not client_secret or not redirect_uri:
        raise RuntimeError("Add GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET and GOOGLE_OAUTH_REDIRECT_URI")
    return client_id, client_secret, redirect_uri


def _fernet() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(SECRET_KEY.encode("utf-8")).digest())
    return Fernet(key)


def _encrypt(value: str | None) -> str | None:
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii") if value else None


def _decrypt(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError("The saved YouTube connection can no longer be decrypted. Reconnect YouTube.") from exc


def authorization_url() -> str:
    client_id, _, redirect_uri = _config()
    state = jwt.encode({
        "purpose": "youtube_oauth",
        "nonce": secrets.token_urlsafe(16),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=10),
    }, SECRET_KEY, algorithm=ALGORITHM)
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": state,
    })


def validate_state(state: str) -> None:
    try:
        payload = jwt.decode(state, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise RuntimeError("The YouTube connection request expired or is invalid") from exc
    if payload.get("purpose") != "youtube_oauth":
        raise RuntimeError("The YouTube connection request is invalid")


def _request_json(url: str, *, data: dict | None = None, token: str | None = None) -> dict:
    body = urlencode(data).encode("utf-8") if data is not None else None
    headers = {"Accept": "application/json", "User-Agent": "AarohiCreatorDashboard/1.0"}
    if data is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, data=body, headers=headers, method="POST" if data is not None else "GET")
    try:
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode("utf-8"))
            detail = payload.get("error_description") or (payload.get("error") or {}).get("message") or payload.get("error")
        except (ValueError, AttributeError):
            detail = None
        raise RuntimeError(str(detail or f"Google returned HTTP {exc.code}")) from exc
    except (URLError, TimeoutError) as exc:
        raise RuntimeError("Could not reach Google. Try connecting YouTube again.") from exc


def _connection(db: Session) -> models.OAuthConnection | None:
    return db.query(models.OAuthConnection).filter(models.OAuthConnection.provider == PROVIDER).first()


def complete_authorization(db: Session, code: str) -> models.OAuthConnection:
    client_id, client_secret, redirect_uri = _config()
    token = _request_json("https://oauth2.googleapis.com/token", data={
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    })
    access_token = token.get("access_token")
    if not access_token:
        raise RuntimeError("Google did not return an access token")
    channel_payload = _request_json(
        "https://www.googleapis.com/youtube/v3/channels?part=id,snippet&mine=true",
        token=access_token,
    )
    channels = channel_payload.get("items") or []
    if not channels:
        raise RuntimeError("The selected Google account does not have a YouTube channel")
    channel = channels[0]
    connection = _connection(db) or models.OAuthConnection(provider=PROVIDER, access_token="")
    previous_refresh = _decrypt(connection.refresh_token) if connection.id and connection.refresh_token else None
    connection.access_token = _encrypt(access_token)
    connection.refresh_token = _encrypt(token.get("refresh_token") or previous_refresh)
    connection.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(token.get("expires_in") or 3600))
    connection.scopes = (token.get("scope") or " ".join(SCOPES)).split()
    connection.provider_account_id = channel.get("id")
    connection.account_name = (channel.get("snippet") or {}).get("title")
    db.add(connection)
    db.commit()
    db.refresh(connection)
    return connection


def connection_status(db: Session) -> dict:
    connection = _connection(db)
    return {
        "configured": oauth_configured(),
        "connected": bool(connection),
        "account_id": connection.provider_account_id if connection else None,
        "account_name": connection.account_name if connection else None,
        "scopes": connection.scopes or [] if connection else [],
        "expires_at": connection.token_expires_at if connection else None,
    }


def disconnect(db: Session) -> None:
    connection = _connection(db)
    if connection:
        db.delete(connection)
        db.commit()


def access_token(db: Session) -> str | None:
    connection = _connection(db)
    if not connection:
        return None
    now = datetime.now(timezone.utc)
    expires = connection.token_expires_at
    if expires and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if not expires or expires > now + timedelta(minutes=2):
        return _decrypt(connection.access_token)
    refresh_token = _decrypt(connection.refresh_token)
    if not refresh_token:
        raise RuntimeError("YouTube authorization expired. Reconnect the channel.")
    client_id, client_secret, _ = _config()
    refreshed = _request_json("https://oauth2.googleapis.com/token", data={
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    })
    connection.access_token = _encrypt(refreshed["access_token"])
    connection.token_expires_at = now + timedelta(seconds=int(refreshed.get("expires_in") or 3600))
    db.commit()
    return refreshed["access_token"]


def video_analytics(db: Session, video_ids: list[str]) -> dict[str, dict]:
    token = access_token(db)
    if not token or not video_ids:
        return {}
    params = {
        "ids": "channel==MINE",
        "startDate": "2006-01-01",
        "endDate": datetime.now(timezone.utc).date().isoformat(),
        "metrics": "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained,shares",
        "dimensions": "video",
        "filters": f"video=={','.join(video_ids[:500])}",
        "maxResults": min(500, len(video_ids)),
    }
    payload = _request_json(
        "https://youtubeanalytics.googleapis.com/v2/reports?" + urlencode(params),
        token=token,
    )
    headers = [column.get("name") for column in payload.get("columnHeaders") or []]
    result = {}
    for row in payload.get("rows") or []:
        values = dict(zip(headers, row))
        video_id = values.pop("video", None)
        if video_id:
            result[video_id] = values
    return result
