from typing import Generator
import os
from sqlmodel import SQLModel, Session, create_engine
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# PostgreSQL bağlantı URL'si al
DATABASE_URL = settings.POSTGRES_DSN

# Engine oluştur - bağlantı hatalarına karşı dirençli
try:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,  # Bağlantıları otomatik yenile
        pool_recycle=3600,   # 1 saat sonra bağlantıları yenile
        pool_size=20,        # Bağlantı havuzunda 20 bağlantı tut (eski: 10)
        max_overflow=40,     # İhtiyaç durumunda 40 bağlantı daha oluştur (eski: 20)
        pool_timeout=60,     # Bağlantı havuzu zaman aşımını artır (60 saniye)
        echo=getattr(settings, 'SQL_ECHO', False)  # SQL komutlarını logla
    )
    logger.info("Veritabanı engine başarıyla oluşturuldu")
except Exception as e:
    logger.error(f"Veritabanı engine oluşturulurken hata: {e}")
    raise

# Bağlantı oturumu oluşturma fonksiyonu
def get_session() -> Generator[Session, None, None]:
    """SQLModel oturumu oluşturur ve yönetir."""
    try:
        with Session(engine) as session:
            try:
                yield session
            finally:
                # Oturum kullanıldıktan sonra bağlantıları serbest bırak
                session.close()
    except Exception as e:
        logger.error(f"Veritabanı oturumu oluşturulurken hata: {e}")
        # Hatayı yeniden fırlat (daha yüksek seviyedeki kod ele almalı)
        raise
        
# Tabloları oluştur
def create_db_and_tables() -> None:
    """Tüm tabloları veritabanında oluşturur."""
    # Tüm modelleri import et (SQLModel otomatik kaydeder)
    from app.models import BaseModel
    
    # Tabloları oluştur
    SQLModel.metadata.create_all(engine)
    
def init_db() -> None:
    """Veritabanını başlatır ve gerekli seed verileri ekler."""
    create_db_and_tables()
    
    # İlk kez çalıştırılıyorsa seed verilerini ekle
    with Session(engine) as session:
        # Admin kullanıcısını kontrol et ve oluştur
        from app.models import User
        admin_exists = session.query(User).filter(User.username == "admin").first()
        
        if not admin_exists:
            from app.core.security import get_password_hash
            from app.models import User
            
            admin = User(
                username="admin",
                first_name="Admin",
                is_active=True,
                is_superuser=True
            )
            
            session.add(admin)
            session.commit() 