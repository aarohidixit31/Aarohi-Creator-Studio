"""
Minimal single-user auth (it's just you using the admin dashboard).

Set ADMIN_EMAIL and ADMIN_PASSWORD_HASH as environment variables.
Generate a password hash once with:

    python -c "from passlib.context import CryptContext; \
    print(CryptContext(schemes=['bcrypt']).hash('your-password-here'))"

and paste the result into ADMIN_PASSWORD_HASH.
"""
import os
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "change-this-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24 * 7  # 1 week — it's just you, no need to re-login daily

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "you@example.com")
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def verify_admin(email: str, password: str) -> bool:
    if email != ADMIN_EMAIL:
        return False
    if not ADMIN_PASSWORD_HASH:
        return False
    return pwd_context.verify(password, ADMIN_PASSWORD_HASH)


def create_access_token() -> str:
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    return jwt.encode({"sub": ADMIN_EMAIL, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def get_current_admin(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("sub") != ADMIN_EMAIL:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    return ADMIN_EMAIL
