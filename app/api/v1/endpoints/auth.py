"""
Authentication API

Kimlik doğrulama için API endpoint'leri.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.core.config import settings
from app.db.session import get_db
from app.db import models
from app.api.v1.schemas.auth import Token, TokenData, UserLogin, UserCreate

# JWT konfigürasyonu
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

router = APIRouter()
logger = get_logger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/token")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """JWT token oluşturur."""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> models.DebugBotUser:
    """JWT tokenı doğrular ve kullanıcıyı döndürür."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Geçersiz kimlik bilgileri",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Token'ı doğrula
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        
        if username is None:
            raise credentials_exception
            
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
        
    # Kullanıcıyı bul
    user = db.query(models.DebugBotUser).filter(models.DebugBotUser.username == token_data.username).first()
    
    if user is None:
        raise credentials_exception
        
    return user

async def get_current_active_user(current_user: models.DebugBotUser = Depends(get_current_user)) -> models.DebugBotUser:
    """Aktif kullanıcıyı döndürür."""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Deaktif kullanıcı")
        
    return current_user

@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    OAuth2 ile token alır.
    
    - **username**: Kullanıcı adı
    - **password**: Şifre
    """
    # Kullanıcıyı bul
    user = db.query(models.DebugBotUser).filter(models.DebugBotUser.username == form_data.username).first()
    
    if not user or not user.verify_password(form_data.password):
        logger.warning(f"Başarısız giriş denemesi: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Hatalı kullanıcı adı veya şifre",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    # Son görülme tarihini güncelle
    user.last_seen = datetime.utcnow()
    db.commit()
    
    # Token oluştur
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    logger.info(f"Kullanıcı başarıyla giriş yaptı: {user.username}")
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/login", response_model=Token)
async def login(
    login_data: UserLogin,
    db: Session = Depends(get_db)
):
    """
    Kullanıcı girişi yapar ve token döndürür.
    
    - **username**: Kullanıcı adı
    - **password**: Şifre
    """
    # Kullanıcıyı bul
    user = db.query(models.DebugBotUser).filter(models.DebugBotUser.username == login_data.username).first()
    
    if not user or not user.verify_password(login_data.password):
        logger.warning(f"Başarısız giriş denemesi: {login_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Hatalı kullanıcı adı veya şifre"
        )
        
    # Son görülme tarihini güncelle
    user.last_seen = datetime.utcnow()
    db.commit()
    
    # Token oluştur
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    logger.info(f"Kullanıcı başarıyla giriş yaptı: {user.username}")
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/register", response_model=Dict[str, Any])
async def register(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    """
    Yeni kullanıcı kaydeder.
    
    - **username**: Kullanıcı adı
    - **password**: Şifre
    - **first_name**: Ad
    - **last_name**: Soyad
    - **access_level**: Erişim seviyesi
    """
    # Kullanıcı adı kullanılıyor mu kontrol et
    existing_user = db.query(models.DebugBotUser).filter(models.DebugBotUser.username == user_data.username).first()
    
    if existing_user:
        logger.warning(f"Kullanıcı adı zaten kullanılıyor: {user_data.username}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kullanıcı adı zaten kullanılıyor"
        )
        
    # Yeni kullanıcı oluştur
    new_user = models.DebugBotUser(
        username=user_data.username,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        access_level=user_data.access_level,
        first_seen=datetime.utcnow(),
        last_seen=datetime.utcnow(),
        is_active=True
    )
    
    # Şifreyi hashle
    new_user.set_password(user_data.password)
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    logger.info(f"Yeni kullanıcı oluşturuldu: {new_user.username}")
    
    return {
        "status": "success",
        "message": "Kullanıcı başarıyla oluşturuldu",
        "user_id": new_user.id
    }

@router.get("/me", response_model=Dict[str, Any])
async def read_users_me(
    current_user: models.DebugBotUser = Depends(get_current_active_user)
):
    """
    Giriş yapmış kullanıcı bilgilerini döndürür.
    """
    logger.info(f"Kullanıcı bilgileri görüntülendi: {current_user.username}")
    
    return {
        "id": current_user.id,
        "username": current_user.username,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "access_level": current_user.access_level,
        "is_developer": current_user.is_developer,
        "is_superuser": current_user.is_superuser,
        "last_seen": current_user.last_seen,
        "created_at": current_user.created_at
    } 