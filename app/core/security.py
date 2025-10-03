import secrets
from datetime import datetime, timedelta
from typing import Any, Optional, Union, Dict

from fastapi import Depends, HTTPException, status
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.core.config import settings

# Şifre hashleme
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Token oluşturma ve doğrulama
ALGORITHM = "HS256"

def create_access_token(
    subject: Union[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    """
    JWT access token oluşturur.
    
    Args:
        subject: Token sahibi (genellikle kullanıcı ID)
        expires_delta: Geçerlilik süresi
        
    Returns:
        str: JWT token
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Düz metin şifreyi hash ile karşılaştırır.
    
    Args:
        plain_password: Düz metin şifre
        hashed_password: Hashlı şifre
        
    Returns:
        bool: Şifreler eşleşirse True
    """
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """
    Şifreyi hashler.
    
    Args:
        password: Hashlenmemiş şifre
        
    Returns:
        str: Hashlı şifre
    """
    return pwd_context.hash(password)

def generate_random_token() -> str:
    """
    Rastgele güvenli bir token oluşturur.
    
    Returns:
        str: Rastgele token
    """
    return secrets.token_urlsafe(32)

# Kullanıcı doğrulama fonksiyonları
async def get_current_user(token: str) -> Dict[str, Any]:
    """
    JWT token'dan kullanıcı bilgilerini çıkarır.
    
    Args:
        token: JWT token
        
    Returns:
        Dict: Kullanıcı bilgileri
        
    Raises:
        HTTPException: Token geçersizse
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[ALGORITHM]
        )
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Geçersiz kimlik bilgileri",
                headers={"WWW-Authenticate": "Bearer"},
            )
        # Basitleştirilmiş kullanıcı nesnesi
        return {"username": username, "is_active": True}
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz kimlik bilgileri",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_active_user(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Kullanıcının aktif olup olmadığını kontrol eder.
    
    Args:
        current_user: Doğrulanmış kullanıcı bilgileri
        
    Returns:
        Dict: Aktif kullanıcı bilgileri
        
    Raises:
        HTTPException: Kullanıcı aktif değilse
    """
    if not current_user.get("is_active", False):
        raise HTTPException(status_code=400, detail="Devre dışı bırakılmış kullanıcı")
    return current_user 