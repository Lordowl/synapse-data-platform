# my_fastapi_backend/core/security.py

from datetime import datetime, timedelta, timezone
from typing import Optional, List
from functools import lru_cache
import logging

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from core.config import settings
from db import schemas, models, crud
from db.database import get_db

logger = logging.getLogger(__name__)

# Log SECRET_KEY for debugging
secret_preview = settings.SECRET_KEY[:10] + "..." if len(settings.SECRET_KEY) > 10 else "***"
logger.info(f"[SECURITY] Loaded with SECRET_KEY: {secret_preview}")

# --------------------------
# 1. Hashing delle Password
# --------------------------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error(f"Error verifying password: {e}")
        return False

def get_password_hash(password: str) -> str:
    if not password or len(password.strip()) == 0:
        raise ValueError("Password cannot be empty")
    return pwd_context.hash(password)

# --------------------------
# 2. Logica JWT
# --------------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    if not data:
        raise ValueError("Token data cannot be empty")

    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})

    try:
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    except Exception as e:
        logger.error(f"Error creating JWT token: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create access token")

def create_refresh_token(data: dict) -> str:
    refresh_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return create_access_token(data, refresh_expires)

# --------------------------
# 3. Dependency per ottenere l'utente corrente
# --------------------------
async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        bank: str = payload.get("bank")

        if not username or not bank:
            raise credentials_exception
    except JWTError as e:
        logger.warning(f"JWT decode error: {e}")
        raise credentials_exception
    except Exception as e:
        logger.error(f"Unexpected error decoding token: {e}")
        raise credentials_exception

    user = crud.get_user_by_username(db, username=username, bank=bank)
    if not user or not user.is_active:
        raise credentials_exception

    setattr(user, "current_bank", bank)
    return user

# --------------------------
# 4. Dipendenze per permessi
# --------------------------
async def get_current_active_admin(current_user: models.User = Depends(get_current_user)) -> models.User:
    if not current_user.role or current_user.role.lower() != "admin":
        logger.warning(f"Non-admin user {current_user.username} attempted admin access")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator privileges required")
    return current_user

async def require_permission(required_permission: str, current_user: models.User = Depends(get_current_user)) -> models.User:
    permissions = []
    if current_user.permissions:
        permissions = [p.strip() for p in current_user.permissions.split(',')] if isinstance(current_user.permissions, str) else current_user.permissions

    if current_user.role and current_user.role.lower() == "admin":
        return current_user

    if required_permission not in permissions:
        logger.warning(f"User {current_user.username} lacks permission: {required_permission}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Permission '{required_permission}' is required")
    return current_user

async def require_ingest_permission(current_user: models.User = Depends(get_current_user)) -> models.User:
    return await require_permission("ingest", current_user)

async def require_report_permission(current_user: models.User = Depends(get_current_user)) -> models.User:
    return await require_permission("report", current_user)

async def require_settings_permission(current_user: models.User = Depends(get_current_user)) -> models.User:
    if current_user.role and current_user.role.lower() == "admin":
        return current_user
    return await require_permission("settings", current_user)

async def require_any_permission(required_permissions: List[str], current_user: models.User = Depends(get_current_user)) -> models.User:
    permissions = []
    if current_user.permissions:
        permissions = [p.strip() for p in current_user.permissions.split(',')] if isinstance(current_user.permissions, str) else current_user.permissions

    if current_user.role and current_user.role.lower() == "admin":
        return current_user

    if not any(p in permissions for p in required_permissions):
        logger.warning(f"User {current_user.username} lacks any of permissions: {required_permissions}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"One of these permissions is required: {', '.join(required_permissions)}")
    return current_user

# --------------------------
# 5. Utility functions
# --------------------------
def has_permission(user: models.User, permission: str) -> bool:
    if not user:
        return False
    if user.role and user.role.lower() == "admin":
        return True
    permissions = []
    if user.permissions:
        permissions = [p.strip() for p in user.permissions.split(',')] if isinstance(user.permissions, str) else user.permissions
    return permission in permissions

def is_admin(user: models.User) -> bool:
    return user and user.role and user.role.lower() == "admin"
