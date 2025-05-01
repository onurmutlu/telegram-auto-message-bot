import os
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from database.models import Base, Group, DebugBotUser, UserGroupRelation, Setting
from database.schema import metadata, groups, debug_bot_users, user_group_relation, settings
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Logging yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# PostgreSQL bağlantı bilgileri
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'postgres')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'telegram_bot')

def create_database():
    """Veritabanını oluşturur"""
    try:
        # PostgreSQL sunucusuna bağlan
        engine = create_engine(f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/postgres')
        conn = engine.connect()
        conn.execute(text("COMMIT"))  # Açık işlemleri kapat
        
        # Veritabanını oluştur
        conn.execute(text(f"CREATE DATABASE {DB_NAME}"))
        logger.info(f"Veritabanı {DB_NAME} başarıyla oluşturuldu")
        
        conn.close()
        engine.dispose()
    except SQLAlchemyError as e:
        logger.error(f"Veritabanı oluşturulurken hata: {str(e)}")
        raise

def init_db():
    """Veritabanını başlatır ve tabloları oluşturur"""
    try:
        # Veritabanı bağlantı URL'si
        DATABASE_URL = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
        
        # Engine oluştur
        engine = create_engine(DATABASE_URL)
        
        # Tabloları oluştur
        Base.metadata.create_all(engine)
        logger.info("Tablolar başarıyla oluşturuldu")
        
        engine.dispose()
    except SQLAlchemyError as e:
        logger.error(f"Veritabanı başlatılırken hata: {str(e)}")
        raise

def get_session():
    """Yeni bir veritabanı oturumu oluşturur"""
    try:
        DATABASE_URL = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
        engine = create_engine(DATABASE_URL)
        Session = sessionmaker(bind=engine)
        return Session()
    except SQLAlchemyError as e:
        logger.error(f"Oturum oluşturulurken hata: {str(e)}")
        raise

def close_session(session):
    """Veritabanı oturumunu kapatır"""
    try:
        session.close()
    except SQLAlchemyError as e:
        logger.error(f"Oturum kapatılırken hata: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        create_database()
        init_db()
        logger.info("Veritabanı başarıyla oluşturuldu ve başlatıldı")
    except Exception as e:
        logger.error(f"İşlem sırasında hata: {str(e)}") 