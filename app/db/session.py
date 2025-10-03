from typing import Generator
import os
from sqlmodel import SQLModel, Session, create_engine
from app.core.config import settings
import logging
import asyncio
import time
import random
from contextlib import contextmanager
import asyncpg
from sqlalchemy.pool import QueuePool

logger = logging.getLogger(__name__)

# PostgreSQL bağlantı URL'si
DATABASE_URL = settings.POSTGRES_DSN

# Veritabanını atla özelliği
if os.getenv("DB_SKIP") == "True":
    logger.warning("Veritabanı bağlantısı DB_SKIP=True nedeniyle atlanıyor!")
    # Bellek tabanlı geçici SQLite veritabanı oluştur
    engine = create_engine("sqlite:///:memory:")
    logger.info("Bellek tabanlı geçici SQLite veritabanı kullanılıyor")
# SQLite kontrolünü tamamen kaldır, sadece PostgreSQL kullan
elif not DATABASE_URL.startswith('postgresql'):
    # Eğer PostgreSQL kullanılmıyorsa, hata ver ve PostgreSQL bağlantı URL'sini düzelt
    logger.error("PostgreSQL kullanılmıyor! Sistem PostgreSQL gerektiriyor.")
    # PostgreSQL URL'sini zorla
    DATABASE_URL = f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    logger.info(f"Bağlantı PostgreSQL'e yönlendirildi: {DATABASE_URL}")

# PostgreSQL için bağlantı argümanları
connect_args = {
    "connect_timeout": 10,  # Bağlantı zaman aşımı (saniye)
    "application_name": f"telegram-bot-{random.randint(1000, 9999)}"  # Tanımlayıcı bağlantı adı
}
# PostgreSQL için optimize edilmiş havuz
pool_size = 20  # Daha yüksek eşzamanlı bağlantı sayısı
max_overflow = 40
pool_recycle = 1800  # 30 dakikada bir bağlantıları yenile
pool_timeout = 30
pool_pre_ping = True

# Engine oluştur - bağlantı hatalarına karşı dirençli
retry_count = 5
for attempt in range(retry_count):
    try:
        engine = create_engine(
            DATABASE_URL,
            pool_pre_ping=pool_pre_ping,  # Bağlantıları otomatik yenile
            pool_recycle=pool_recycle,   # Belirli süre sonra bağlantıları yenile
            pool_size=pool_size,        # Bağlantı havuzunda belirli sayıda bağlantı tut
            max_overflow=max_overflow,     # İhtiyaç durumunda ek bağlantı oluştur
            pool_timeout=pool_timeout,     # Bağlantı havuzu zaman aşımı
            connect_args=connect_args,  # Bağlantı argümanları
            echo=getattr(settings, 'SQL_ECHO', False),  # SQL komutlarını logla
            # PostgreSQL için ek optimize ayarlar
            isolation_level="READ COMMITTED",  # İzolasyon seviyesi
            pool_use_lifo=True,  # Son kullanılan bağlantıyı önce kullan (cache verimliliği)
            poolclass=QueuePool,  # Queue tabanlı connection pooling kullan
            future=True,  # SQLAlchemy 2.0 uyumlu mod
        )
        logger.info("PostgreSQL veritabanı engine başarıyla oluşturuldu")
        break
    except Exception as e:
        logger.error(f"Veritabanı engine oluşturulurken hata ({attempt+1}/{retry_count}): {e}")
        if attempt < retry_count - 1:
            time.sleep(2)  # Yeniden denemeden önce bekle
        else:
            raise

# Bağlantı havuzu kilidini yönetmek için semaphore - paralel bağlantıların sayısını kontrol eder
_db_lock = asyncio.Semaphore(10)  # 10 paralel bağlantıya izin ver

# Bağlantı oturumu oluşturma fonksiyonu
def get_session() -> Generator[Session, None, None]:
    """SQLModel oturumu oluşturur ve yönetir."""
    session = None
    try:
        session = Session(engine)
        yield session
    except Exception as e:
        logger.error(f"Veritabanı oturumu oluşturulurken hata: {e}")
        # Hata durumunda transaction'ı geri al
        if session:
            try:
                session.rollback()
                logger.info("Veritabanı işlemi geri alındı")
            except Exception as rollback_error:
                logger.error(f"Transaction geri alma hatası: {rollback_error}")
        # Hatayı yeniden fırlat
        raise
    finally:
        # Oturum kullanıldıktan sonra bağlantıları serbest bırak
        if session:
            try:
                session.close()
            except Exception as close_error:
                logger.error(f"Oturum kapatma hatası: {close_error}")

# Asenkron kullanım için bağlantı yöneticisi
@contextmanager
def get_db_session():
    """Veritabanı oturumunu context manager ile yönetir."""
    session = None
    try:
        session = Session(engine)
        yield session
    except Exception as e:
        logger.error(f"get_db_session hatası: {e}")
        if session:
            try:
                session.rollback()
            except:
                pass
        raise
    finally:
        if session:
            try:
                session.close()
            except Exception as e:
                logger.error(f"Oturum kapatma hatası: {e}")

# AsyncIO kullanımı için async context manager
async def get_async_session():
    """AsyncIO uyumlu veritabanı oturumu sağlar."""
    async with _db_lock:
        session = None
        try:
            session = Session(engine)
            yield session
        except Exception as e:
            logger.error(f"Async oturum hatası: {e}")
            if session:
                try:
                    session.rollback()
                except:
                    pass
            raise
        finally:
            if session:
                try:
                    session.close()
                except Exception as e:
                    logger.error(f"Async oturum kapatma hatası: {e}")

# FastAPI uyumlu veritabanı oturumu sağlayan fonksiyon
def get_db():
    """FastAPI uyumlu veritabanı oturumu sağlar (dependency)."""
    session = None
    try:
        session = Session(engine)
        yield session
    except Exception as e:
        logger.error(f"get_db oturumu oluşturulurken hata: {e}")
        if session:
            try:
                session.rollback()
            except:
                pass
        raise
    finally:
        if session:
            try:
                session.close()
            except Exception as e:
                logger.error(f"Oturum kapatma hatası: {e}")

# asyncpg ile asenkron bağlantı havuzu
async def init_asyncpg_pool():
    """AsyncPG bağlantı havuzunu başlatır."""
    try:
        # PostgreSQL kullanıcı adı, şifre, sunucu, port ve veritabanı adını ayır
        # postgresql://user:password@host:port/dbname formatından
        dsn_parts = DATABASE_URL.replace('postgresql://', '').split('@')
        user_pass = dsn_parts[0].split(':')
        host_port_db = dsn_parts[1].split('/')
        
        user = user_pass[0]
        password = user_pass[1] if len(user_pass) > 1 else ''
        
        host_port = host_port_db[0].split(':')
        host = host_port[0]
        port = int(host_port[1]) if len(host_port) > 1 else 5432
        
        database = host_port_db[1]
        
        # AsyncPG bağlantı havuzunu oluştur
        pool = await asyncpg.create_pool(
            user=user,
            password=password,
            host=host,
            port=port,
            database=database,
            min_size=5,
            max_size=20,
            command_timeout=60,
            timeout=10,
        )
        logger.info("AsyncPG bağlantı havuzu başarıyla oluşturuldu")
        return pool
    except Exception as e:
        logger.error(f"AsyncPG havuzu oluşturulurken hata: {e}")
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
                user_id=0,  # admin kullanıcısı için varsayılan user_id
                username="admin",
                first_name="Admin",
                is_active=True
            )
            
            session.add(admin)
            session.commit()