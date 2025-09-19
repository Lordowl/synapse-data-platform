# my_fastapi_backend/core/security.py

from datetime import datetime, timedelta, timezone
from typing import Optional, List
from functools import lru_cache

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import logging

from .config import settings
from db import schemas, models, crud
from db.database import get_db

logger = logging.getLogger(__name__)

# --------------------------
# 1. Hashing delle Password
# --------------------------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica la password in plain text contro quella hashata."""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error(f"Error verifying password: {e}")
        return False

def get_password_hash(password: str) -> str:
    """Genera l'hash della password."""
    if not password or len(password.strip()) == 0:
        raise ValueError("Password cannot be empty")
    return pwd_context.hash(password)


# --------------------------
# 2. Logica JWT
# --------------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Crea un JWT token con i dati forniti."""
    if not data:
        raise ValueError("Token data cannot be empty")
    
    to_encode = data.copy()
    
    # Usa un tempo di scadenza più ragionevole per default
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    
    try:
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return encoded_jwt
    except Exception as e:
        logger.error(f"Error creating JWT token: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create access token"
        )

def create_refresh_token(data: dict) -> str:
    """Crea un refresh token con scadenza più lunga."""
    refresh_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return create_access_token(data, refresh_expires)


# --------------------------
# 3. Dependency per ottenere l'utente corrente
# --------------------------
@lru_cache(maxsize=100)
def _get_cached_user(username: str, db_session_id: int):
    """Cache per ridurre le query al database per lo stesso utente."""
    # Nota: in produzione considera Redis o altro sistema di cache distribuito
    pass

async def get_current_user(
    token: str = Depends(oauth2_scheme), 
    db: Session = Depends(get_db)
) -> models.User:
    """Dependency per ottenere l'utente corrente dal JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Decodifica il token
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        
        if username is None:
            logger.warning("Token without 'sub' claim received")
            raise credentials_exception
            
        # Validazione aggiuntiva del token
        if payload.get("exp", 0) < datetime.now(timezone.utc).timestamp():
            logger.warning(f"Expired token for user: {username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )
            
    except JWTError as e:
        logger.warning(f"JWT decode error: {e}")
        raise credentials_exception
    except Exception as e:
        logger.error(f"Unexpected error decoding token: {e}")
        raise credentials_exception
    
    # Ottieni l'utente dal database
    try:
        user = crud.get_user_by_username(db, username=username)
        if user is None:
            logger.warning(f"User not found: {username}")
            raise credentials_exception
            
        if not user.is_active:
            logger.warning(f"Inactive user attempted access: {username}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="User account is deactivated"
            )
            
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Database error getting user {username}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


# --------------------------
# 4. Dipendenze per permessi
# --------------------------
async def get_current_active_admin(
    current_user: models.User = Depends(get_current_user)
) -> models.User:
    """Dependency che richiede privilegi di admin."""
    if not current_user.role or current_user.role.lower() != "admin":
        logger.warning(f"Non-admin user {current_user.username} attempted admin access")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Administrator privileges required"
        )
    return current_user

async def require_permission(
    required_permission: str, 
    current_user: models.User = Depends(get_current_user)
) -> models.User:
    """Dependency generica per controllo permessi."""
    if not current_user.permissions:
        permissions = []
    else:
        # Supporta sia lista che stringa separata da virgole
        if isinstance(current_user.permissions, str):
            permissions = [p.strip() for p in current_user.permissions.split(',')]
        else:
            permissions = current_user.permissions
    
    # Admin ha tutti i permessi
    if current_user.role and current_user.role.lower() == "admin":
        return current_user
        
    if required_permission not in permissions:
        logger.warning(
            f"User {current_user.username} lacks permission: {required_permission}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission '{required_permission}' is required"
        )
    return current_user

async def require_ingest_permission(
    current_user: models.User = Depends(get_current_user)
) -> models.User:
    """Dependency che richiede il permesso 'ingest'."""
    return await require_permission("ingest", current_user)

async def require_report_permission(
    current_user: models.User = Depends(get_current_user)
) -> models.User:
    """Dependency che richiede il permesso 'report'."""
    return await require_permission("report", current_user)

async def require_settings_permission(
    current_user: models.User = Depends(get_current_user)
) -> models.User:
    """Dependency che richiede il permesso 'settings' o ruolo admin."""
    # Admin ha accesso automatico alle settings
    if current_user.role and current_user.role.lower() == "admin":
        return current_user
        
    return await require_permission("settings", current_user)

async def require_any_permission(
    required_permissions: List[str],
    current_user: models.User = Depends(get_current_user)
) -> models.User:
    """Dependency che richiede almeno uno dei permessi specificati."""
    if not current_user.permissions:
        permissions = []
    else:
        if isinstance(current_user.permissions, str):
            permissions = [p.strip() for p in current_user.permissions.split(',')]
        else:
            permissions = current_user.permissions
    
    # Admin ha tutti i permessi
    if current_user.role and current_user.role.lower() == "admin":
        return current_user
        
    if not any(perm in permissions for perm in required_permissions):
        logger.warning(
            f"User {current_user.username} lacks any of permissions: {required_permissions}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"One of these permissions is required: {', '.join(required_permissions)}"
        )
    return current_user


# --------------------------
# 5. Utility functions
# --------------------------
def has_permission(user: models.User, permission: str) -> bool:
    """Utility per controllare se un utente ha un permesso specifico."""
    if not user:
        return False
        
    # Admin ha tutti i permessi
    if user.role and user.role.lower() == "admin":
        return True
        
    if not user.permissions:
        return False
        
    if isinstance(user.permissions, str):
        permissions = [p.strip() for p in user.permissions.split(',')]
    else:
        permissions = user.permissions
        
    return permission in permissions

def is_admin(user: models.User) -> bool:
    """Utility per controllare se un utente è admin."""
    return user and user.role and user.role.lower() == "admin"