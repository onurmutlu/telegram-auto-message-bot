"""
Telegram Bot API - Bağımlılıklar

FastAPI uygulaması için bağımlılık işlevleri ve yardımcı fonksiyonlar.
"""

from typing import Optional, Union
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from app.db.session import get_session
from app.core.config import settings

# OAuth2 ayarları
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    auto_error=False
)

# Şimdilik basit doğrulama (geliştirme aşamasında)
async def get_current_user(token: Optional[str] = Depends(oauth2_scheme)):
    """
    Basit bir kullanıcı doğrulama işlevi.
    
    Geliştirme aşamasında olduğu için şu an için her isteği kabul eder.
    Gerçek uygulamada JWT token doğrulaması ve kullanıcı veri tabanı kontrolü eklenecektir.
    """
    # Basitleştirilmiş doğrulama - geliştirme için
    return {"username": "admin"}

# JWT token işlevleri (ileride kullanılacak)
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    JWT erişim token'ı oluşturur.
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    
    return encoded_jwt

async def verify_token(token: str, db: AsyncSession) -> Optional[dict]:
    """
    JWT token'ını doğrular ve kullanıcı bilgilerini döndürür.
    """
    try:
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        username: str = payload.get("sub")
        
        if username is None:
            return None
        
        # Burada kullanıcı veritabanı kontrolü yapılabilir
        # Şimdilik basit bir kullanıcı nesnesi döndürüyoruz
        return {"username": username}
    except JWTError:
        return None 