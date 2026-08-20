import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from jose import JWTError, jwt
from sqlalchemy.orm import Session

from .. import models
from ..auth import ALGORITHM, SECRET_KEY
from .youtube_oauth import _decrypt, _encrypt


PROVIDER = "instagram"
FACEBOOK_SCOPES = ("pages_show_list", "pages_read_engagement", "instagram_basic", "instagram_manage_insights")
INSTAGRAM_SCOPES = ("instagram_business_basic", "instagram_business_manage_insights")
SCOPES = FACEBOOK_SCOPES


def _auth_mode() -> str:
    return "instagram" if os.getenv("INSTAGRAM_AUTH_MODE", "facebook").strip().lower() == "instagram" else "facebook"


def _active_scopes() -> tuple[str, ...]:
    return INSTAGRAM_SCOPES if _auth_mode() == "instagram" else FACEBOOK_SCOPES


def oauth_configured() -> bool:
    if _auth_mode() == "instagram":
        return all(os.getenv(name, "").strip() for name in (
            "INSTAGRAM_APP_ID", "INSTAGRAM_APP_SECRET", "INSTAGRAM_OAUTH_REDIRECT_URI",
        ))
    return bool(_setting("META_APP_ID", "INSTAGRAM_APP_ID") and
                _setting("META_APP_SECRET", "INSTAGRAM_APP_SECRET") and
                _setting("META_OAUTH_REDIRECT_URI", "INSTAGRAM_OAUTH_REDIRECT_URI"))


def _setting(primary: str, legacy: str) -> str:
    return os.getenv(primary, "").strip() or os.getenv(legacy, "").strip()


def _config() -> tuple[str, str, str]:
    if _auth_mode() == "instagram":
        values = tuple(os.getenv(name, "").strip() for name in (
            "INSTAGRAM_APP_ID", "INSTAGRAM_APP_SECRET", "INSTAGRAM_OAUTH_REDIRECT_URI",
        ))
        if not all(values):
            raise RuntimeError("Add INSTAGRAM_APP_ID, INSTAGRAM_APP_SECRET and INSTAGRAM_OAUTH_REDIRECT_URI")
        return values
    app_id = _setting("META_APP_ID", "INSTAGRAM_APP_ID")
    app_secret = _setting("META_APP_SECRET", "INSTAGRAM_APP_SECRET")
    redirect_uri = _setting("META_OAUTH_REDIRECT_URI", "INSTAGRAM_OAUTH_REDIRECT_URI")
    if not app_id or not app_secret or not redirect_uri:
        raise RuntimeError("Add META_APP_ID, META_APP_SECRET and META_OAUTH_REDIRECT_URI")
    return app_id, app_secret, redirect_uri


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
            error = payload.get("error") or {}
            detail = error.get("message") if isinstance(error, dict) else error
            detail = detail or payload.get("error_message")
        except (ValueError, AttributeError):
            detail = None
        raise RuntimeError(str(detail or f"Instagram returned HTTP {exc.code}")) from exc
    except (URLError, TimeoutError) as exc:
        raise RuntimeError("Could not reach Instagram. Try connecting again.") from exc


def _connection(db: Session) -> models.OAuthConnection | None:
    return db.query(models.OAuthConnection).filter(models.OAuthConnection.provider == PROVIDER).first()


def authorization_url() -> str:
    app_id, _, redirect_uri = _config()
    state = jwt.encode({
        "purpose": "instagram_oauth",
        "nonce": secrets.token_urlsafe(16),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=10),
    }, SECRET_KEY, algorithm=ALGORITHM)
    params = {
        "client_id": app_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": ",".join(_active_scopes()),
        "state": state,
    }
    if _auth_mode() == "instagram":
        params["enable_fb_login"] = "0"
        params["force_authentication"] = "1"
        return "https://www.instagram.com/oauth/authorize?" + urlencode(params)
    config_id = os.getenv("META_LOGIN_CONFIG_ID", "").strip()
    if config_id:
        params["config_id"] = config_id
        # Facebook Login for Business stores permissions in the configuration;
        # Meta requires config_id to replace the regular scope parameter.
        params.pop("scope", None)
        params["override_default_response_type"] = "true"
    version = os.getenv("META_GRAPH_VERSION", "v23.0").strip()
    return f"https://www.facebook.com/{version}/dialog/oauth?" + urlencode(params)


def validate_state(state: str) -> None:
    try:
        payload = jwt.decode(state, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise RuntimeError("The Instagram connection request expired or is invalid") from exc
    if payload.get("purpose") != "instagram_oauth":
        raise RuntimeError("The Instagram connection request is invalid")


def complete_authorization(db: Session, code: str) -> models.OAuthConnection:
    app_id, app_secret, redirect_uri = _config()
    version = os.getenv("META_GRAPH_VERSION", "v23.0").strip()
    if _auth_mode() == "instagram":
        short = _request_json("https://api.instagram.com/oauth/access_token", data={
            "client_id": app_id,
            "client_secret": app_secret,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
            "code": code,
        })
        short_token = short.get("access_token")
        account_id = str(short.get("user_id") or "")
        if not short_token or not account_id:
            raise RuntimeError("Instagram did not return an account and access token")
        long_lived = _request_json("https://graph.instagram.com/access_token?" + urlencode({
            "grant_type": "ig_exchange_token",
            "client_secret": app_secret,
            "access_token": short_token,
        }))
        access_token = long_lived.get("access_token") or short_token
        expires_in = int(long_lived.get("expires_in") or short.get("expires_in") or 3600)
        profile = _request_json(
            f"https://graph.instagram.com/{version}/{account_id}?fields=id,username,name,profile_picture_url,followers_count",
            token=access_token,
        )
        connection = _connection(db) or models.OAuthConnection(provider=PROVIDER, access_token="")
        connection.access_token = _encrypt(access_token)
        connection.refresh_token = None
        connection.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        connection.scopes = list(INSTAGRAM_SCOPES)
        connection.provider_account_id = account_id
        connection.account_name = profile.get("username") or profile.get("name")
        db.add(connection)
        db.commit()
        db.refresh(connection)
        return connection
    token_url = f"https://graph.facebook.com/{version}/oauth/access_token?" + urlencode({
        "client_id": app_id,
        "client_secret": app_secret,
        "redirect_uri": redirect_uri,
        "code": code,
    })
    short = _request_json(token_url)
    short_token = short.get("access_token")
    if not short_token:
        raise RuntimeError("Facebook did not return an access token")
    long_url = f"https://graph.facebook.com/{version}/oauth/access_token?" + urlencode({
        "grant_type": "fb_exchange_token",
        "client_id": app_id,
        "client_secret": app_secret,
        "fb_exchange_token": short_token,
    })
    long_lived = _request_json(long_url)
    user_token = long_lived.get("access_token") or short_token
    expires_in = int(long_lived.get("expires_in") or short.get("expires_in") or 3600)
    pages = _request_json(
        f"https://graph.facebook.com/{version}/me/accounts?" + urlencode({
            "fields": "id,name,access_token,instagram_business_account{id,username,name,profile_picture_url,followers_count}",
            "limit": 100,
        }),
        token=user_token,
    )
    page_rows = pages.get("data") or []
    if not page_rows:
        raise RuntimeError(
            "Facebook returned no managed Pages. Add pages_show_list to the Login for Business configuration "
            "and select the Aarohi Inframe Page during login."
        )
    page = None
    profile = None
    for candidate in page_rows:
        page_token = candidate.get("access_token") or user_token
        linked = candidate.get("instagram_business_account")
        if not linked and candidate.get("id"):
            try:
                page_details = _request_json(
                    f"https://graph.facebook.com/{version}/{candidate['id']}?fields=instagram_business_account",
                    token=page_token,
                )
                linked = page_details.get("instagram_business_account")
            except RuntimeError:
                continue
        account_id = str((linked or {}).get("id") or "")
        if not account_id:
            continue
        profile = linked
        if not profile.get("username"):
            try:
                profile = _request_json(
                    f"https://graph.facebook.com/{version}/{account_id}?fields=id,username,name,profile_picture_url,followers_count",
                    token=page_token,
                )
            except RuntimeError:
                profile = linked
        page = candidate
        break
    if not page or not profile:
        page_names = ", ".join(str(row.get("name") or row.get("id")) for row in page_rows[:3])
        raise RuntimeError(
            f"Facebook returned the Page(s) {page_names}, but none exposes a linked professional Instagram account. "
            "Link Instagram under that Page's Settings > Linked accounts, not only Accounts Center."
        )
    account_id = str(profile.get("id") or "")
    access_token = page.get("access_token") or user_token
    if not account_id:
        raise RuntimeError("The linked Facebook Page did not return an Instagram account ID")
    connection = _connection(db) or models.OAuthConnection(provider=PROVIDER, access_token="")
    connection.access_token = _encrypt(access_token)
    connection.refresh_token = None
    connection.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    connection.scopes = list(FACEBOOK_SCOPES)
    connection.provider_account_id = account_id
    connection.account_name = profile.get("username") or profile.get("name") or page.get("name")
    db.add(connection)
    db.commit()
    db.refresh(connection)
    return connection


def connection_status(db: Session) -> dict:
    connection = _connection(db)
    manual = bool(os.getenv("META_ACCESS_TOKEN", "").strip() and os.getenv("INSTAGRAM_ACCOUNT_ID", "").strip())
    return {
        "configured": oauth_configured(),
        "connected": bool(connection) or manual,
        "account_id": connection.provider_account_id if connection else os.getenv("INSTAGRAM_ACCOUNT_ID") or None,
        "account_name": connection.account_name if connection else None,
        "scopes": (connection.scopes or []) if connection else [],
        "expires_at": connection.token_expires_at if connection else None,
        "connection_type": "oauth" if connection else "environment" if manual else None,
    }


def access_credentials(db: Session) -> tuple[str, str]:
    connection = _connection(db)
    if not connection:
        token = os.getenv("META_ACCESS_TOKEN", "").strip()
        account_id = os.getenv("INSTAGRAM_ACCOUNT_ID", "").strip()
        if token and account_id:
            return token, account_id
        raise RuntimeError("Connect Instagram or add META_ACCESS_TOKEN and INSTAGRAM_ACCOUNT_ID")
    token = _decrypt(connection.access_token)
    expires = connection.token_expires_at
    if expires and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if "instagram_business_basic" in (connection.scopes or []) and expires and expires <= datetime.now(timezone.utc) + timedelta(days=7):
        refreshed = _request_json("https://graph.instagram.com/refresh_access_token?" + urlencode({
            "grant_type": "ig_refresh_token",
            "access_token": token,
        }))
        token = refreshed.get("access_token") or token
        connection.access_token = _encrypt(token)
        connection.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(refreshed.get("expires_in") or 5184000))
        db.commit()
    return token, str(connection.provider_account_id)


def _graph_base(db: Session) -> str:
    connection = _connection(db)
    direct = connection and "instagram_business_basic" in (connection.scopes or [])
    if direct or (not connection and _auth_mode() == "instagram"):
        return "https://graph.instagram.com"
    return "https://graph.facebook.com"


def graph_get(db: Session, path: str, params: dict | None = None) -> dict:
    token, _ = access_credentials(db)
    version = os.getenv("META_GRAPH_VERSION", "v23.0").strip()
    query = urlencode(params or {})
    url = f"{_graph_base(db)}/{version}/{path.lstrip('/')}"
    if query:
        url += f"?{query}"
    return _request_json(url, token=token)


def graph_get_url(db: Session, url: str) -> dict:
    if not url.startswith(_graph_base(db) + "/"):
        raise RuntimeError("Instagram returned an invalid pagination URL")
    token, _ = access_credentials(db)
    return _request_json(url, token=token)


def disconnect(db: Session) -> None:
    connection = _connection(db)
    if connection:
        db.delete(connection)
        db.commit()
