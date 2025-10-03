from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
from .config import settings
import logging

logger = logging.getLogger(__name__)

SQLALCHEMY_DATABASE_URL = settings.POSTGRES_DSN

# PostgreSQL kullanımını kontrol et
if not SQLALCHEMY_DATABASE_URL.startswith('postgresql'):
    # PostgreSQL URL'sini zorla
    SQLALCHEMY_DATABASE_URL = f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    logger.warning(f"Bağlantı PostgreSQL'e yönlendirildi: {SQLALCHEMY_DATABASE_URL}")

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    echo=settings.SQL_ECHO,
    # PostgreSQL için ek optimizasyonlar
    pool_pre_ping=True,
    poolclass=QueuePool,
    pool_use_lifo=True,
    isolation_level="READ COMMITTED",
    connect_args={
        "connect_timeout": 10,
        "application_name": "telegram-bot-core"
    }
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()

def init_db():
    """Veritabanı bağlantısını başlat"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Veritabanı şeması başarıyla oluşturuldu")
    except Exception as e:
        logger.error(f"Veritabanı başlatılırken hata oluştu: {e}")
        raise

def get_db():
    """Veritabanı bağlantısı oluştur"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
