#!/usr/bin/env python3
"""
PostgreSQL veritabanı şemasını oluşturmak ve yeni tabloları eklemek için yardımcı script.
"""
import os
import sys
import logging
import argparse
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Log ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Çevre değişkenlerini yükle
load_dotenv()

# Modelleri içe aktar
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.models import Base, Group, TelegramUser, GroupMember, GroupAnalytics, DataMining, MessageTracking

def get_db_url():
    """
    Veritabanı bağlantı URL'sini oluşturur
    """
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        user = os.getenv('DB_USER', 'postgres')
        password = os.getenv('DB_PASSWORD', 'postgres')
        host = os.getenv('DB_HOST', 'localhost')
        port = os.getenv('DB_PORT', '5432')
        db_name = os.getenv('DB_NAME', 'telegram_bot')
        db_url = f"postgresql://{user}:{password}@{host}:{port}/{db_name}"
    
    return db_url

def create_tables(engine):
    """
    Eksik tabloları oluşturur
    """
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    
    # Eklenecek tabloları belirle
    all_tables = [cls.__tablename__ for cls in [Group, TelegramUser, GroupMember, GroupAnalytics, DataMining, MessageTracking]]
    
    # Eksik tabloları oluştur
    for table_name in all_tables:
        if table_name not in existing_tables:
            logger.info(f"'{table_name}' tablosu oluşturuluyor...")
        else:
            logger.info(f"'{table_name}' tablosu zaten mevcut.")
    
    # Tabloları oluştur
    Base.metadata.create_all(engine)
    logger.info("Veritabanı tabloları güncellendi.")

def add_missing_columns(engine):
    """
    Var olan tablolara eksik kolonları ekler
    """
    inspector = inspect(engine)
    
    # Group tablosu için eksik kolonları ekle
    if 'groups' in inspector.get_table_names():
        cols = [c['name'] for c in inspector.get_columns('groups')]
        with engine.begin() as conn:
            if 'username' not in cols:
                logger.info("'groups' tablosuna 'username' kolonu ekleniyor...")
                conn.execute(text("ALTER TABLE groups ADD COLUMN username VARCHAR"))
            
            if 'description' not in cols:
                logger.info("'groups' tablosuna 'description' kolonu ekleniyor...")
                conn.execute(text("ALTER TABLE groups ADD COLUMN description VARCHAR"))
            
            if 'is_admin' not in cols:
                logger.info("'groups' tablosuna 'is_admin' kolonu ekleniyor...")
                conn.execute(text("ALTER TABLE groups ADD COLUMN is_admin BOOLEAN DEFAULT FALSE"))
            
            if 'is_public' not in cols:
                logger.info("'groups' tablosuna 'is_public' kolonu ekleniyor...")
                conn.execute(text("ALTER TABLE groups ADD COLUMN is_public BOOLEAN DEFAULT TRUE"))
            
            if 'invite_link' not in cols:
                logger.info("'groups' tablosuna 'invite_link' kolonu ekleniyor...")
                conn.execute(text("ALTER TABLE groups ADD COLUMN invite_link VARCHAR"))
            
            if 'source' not in cols:
                logger.info("'groups' tablosuna 'source' kolonu ekleniyor...")
                conn.execute(text("ALTER TABLE groups ADD COLUMN source VARCHAR"))
                
            if 'last_active' not in cols:
                logger.info("'groups' tablosuna 'last_active' kolonu ekleniyor...")
                conn.execute(text("ALTER TABLE groups ADD COLUMN last_active TIMESTAMP DEFAULT NOW()"))
    
    # data_mining tablosu için eksik kolonları ekle
    if 'data_mining' in inspector.get_table_names():
        cols = [c['name'] for c in inspector.get_columns('data_mining')]
        with engine.begin() as conn:
            if 'is_processed' not in cols:
                logger.info("'data_mining' tablosuna 'is_processed' kolonu ekleniyor...")
                conn.execute(text("ALTER TABLE data_mining ADD COLUMN is_processed BOOLEAN DEFAULT FALSE"))
            
            if 'processed_at' not in cols:
                logger.info("'data_mining' tablosuna 'processed_at' kolonu ekleniyor...")
                conn.execute(text("ALTER TABLE data_mining ADD COLUMN processed_at TIMESTAMP"))
            
            if 'group_id' not in cols:
                logger.info("'data_mining' tablosuna 'group_id' kolonu ekleniyor...")
                conn.execute(text("ALTER TABLE data_mining ADD COLUMN group_id BIGINT"))
                
            if 'updated_at' not in cols:
                logger.info("'data_mining' tablosuna 'updated_at' kolonu ekleniyor...")
                conn.execute(text("ALTER TABLE data_mining ADD COLUMN updated_at TIMESTAMP DEFAULT NOW()"))

def create_indexes(engine):
    """
    Performans için önemli indeksleri oluşturur
    """
    with engine.begin() as conn:
        # Grup indeksleri
        logger.info("Grup indeksleri oluşturuluyor...")
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_groups_is_active ON groups(is_active)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_groups_is_admin ON groups(is_admin)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_groups_join_date ON groups(join_date)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_groups_last_active ON groups(last_active)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_groups_last_message ON groups(last_message)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_groups_name_pattern ON groups(name varchar_pattern_ops)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_groups_username_pattern ON groups(username varchar_pattern_ops)"))
        
        # Kullanıcı indeksleri
        logger.info("Kullanıcı indeksleri oluşturuluyor...")
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_telegram_users_username ON telegram_users(username)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_telegram_users_is_active ON telegram_users(is_active)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_telegram_users_last_seen ON telegram_users(last_seen)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_telegram_users_first_seen ON telegram_users(first_seen)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_telegram_users_is_bot ON telegram_users(is_bot)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_telegram_users_username_pattern ON telegram_users(username varchar_pattern_ops)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_telegram_users_first_name_pattern ON telegram_users(first_name varchar_pattern_ops)"))
        
        # Grup üyeleri indeksleri
        logger.info("Grup üyeleri indeksleri oluşturuluyor...")
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_group_members_user_id ON group_members(user_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_group_members_group_id ON group_members(group_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_group_members_is_admin ON group_members(is_admin)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_group_members_joined_at ON group_members(joined_at)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_group_members_last_seen ON group_members(last_seen)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_group_members_is_active ON group_members(is_active)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_group_members_composite ON group_members(group_id, is_active, last_seen)"))
        
        # Data mining indeksleri
        logger.info("Data mining indeksleri oluşturuluyor...")
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_data_mining_user_id ON data_mining(user_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_data_mining_group_id ON data_mining(group_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_data_mining_type ON data_mining(type)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_data_mining_telegram_id ON data_mining(telegram_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_data_mining_is_processed ON data_mining(is_processed)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_data_mining_created_at ON data_mining(created_at)"))
        
        # Mesaj izleme indeksleri
        logger.info("Mesaj izleme indeksleri oluşturuluyor...")
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_message_tracking_group_id ON message_tracking(group_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_message_tracking_user_id ON message_tracking(user_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_message_tracking_message_id ON message_tracking(message_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_message_tracking_sent_at ON message_tracking(sent_at)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_message_tracking_content_type ON message_tracking(content_type)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_message_tracking_is_outgoing ON message_tracking(is_outgoing)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_message_tracking_grp_user ON message_tracking(group_id, user_id)"))
        
        # Grup analitiği indeksleri 
        logger.info("Grup analitiği indeksleri oluşturuluyor...")
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_group_analytics_group_id ON group_analytics(group_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_group_analytics_date ON group_analytics(date)"))
        
        # Tablo istatistiklerini güncelle
        logger.info("Tablo istatistiklerini güncelleniyor...")
        conn.execute(text("ANALYZE"))

def update_integer_columns_to_bigint(engine):
    """
    Integer ID sütunlarını BigInteger'a dönüştür
    """
    logger.info("Tüm ID sütunlarını BigInteger tipine dönüştürmek için veritabanı güncelleniyor...")
    
    # PostgreSQL ile çalışıyoruz, sütunları ALTER COLUMN ile güncelleyebiliriz
    with engine.begin() as conn:
        # groups tablosu
        logger.info("'groups' tablosundaki group_id sütunu BigInteger'a dönüştürülüyor...")
        conn.execute(text("ALTER TABLE groups ALTER COLUMN group_id TYPE BIGINT"))
        
        # telegram_users tablosu
        logger.info("'telegram_users' tablosundaki user_id sütunu BigInteger'a dönüştürülüyor...")
        conn.execute(text("ALTER TABLE telegram_users ALTER COLUMN user_id TYPE BIGINT"))
        
        # group_members tablosu
        logger.info("'group_members' tablosundaki user_id ve group_id sütunları BigInteger'a dönüştürülüyor...")
        conn.execute(text("ALTER TABLE group_members ALTER COLUMN user_id TYPE BIGINT"))
        conn.execute(text("ALTER TABLE group_members ALTER COLUMN group_id TYPE BIGINT"))
        
        # data_mining tablosu
        logger.info("'data_mining' tablosundaki user_id, telegram_id ve group_id sütunları BigInteger'a dönüştürülüyor...")
        conn.execute(text("ALTER TABLE data_mining ALTER COLUMN user_id TYPE BIGINT"))
        conn.execute(text("ALTER TABLE data_mining ALTER COLUMN telegram_id TYPE BIGINT"))
        conn.execute(text("ALTER TABLE data_mining ALTER COLUMN group_id TYPE BIGINT"))
        
        # message_tracking tablosu
        logger.info("'message_tracking' tablosundaki message_id, group_id ve user_id sütunları BigInteger'a dönüştürülüyor...")
        conn.execute(text("ALTER TABLE message_tracking ALTER COLUMN message_id TYPE BIGINT"))
        conn.execute(text("ALTER TABLE message_tracking ALTER COLUMN group_id TYPE BIGINT"))
        conn.execute(text("ALTER TABLE message_tracking ALTER COLUMN user_id TYPE BIGINT"))
        
        # group_analytics tablosu 
        logger.info("'group_analytics' tablosundaki group_id sütunu BigInteger'a dönüştürülüyor...")
        conn.execute(text("ALTER TABLE group_analytics ALTER COLUMN group_id TYPE BIGINT"))
        
        # debug_bot_users tablosu
        logger.info("'debug_bot_users' tablosundaki user_id sütunu BigInteger'a dönüştürülüyor...")
        conn.execute(text("ALTER TABLE debug_bot_users ALTER COLUMN user_id TYPE BIGINT"))
        
        # user_group_relation tablosu
        logger.info("'user_group_relation' tablosundaki user_id ve group_id sütunları BigInteger'a dönüştürülüyor...")
        conn.execute(text("ALTER TABLE user_group_relation ALTER COLUMN user_id TYPE BIGINT"))
        conn.execute(text("ALTER TABLE user_group_relation ALTER COLUMN group_id TYPE BIGINT"))
    
    logger.info("Tüm ID sütunları BigInteger tipine dönüştürüldü.")

def check_and_fix_bigint_columns(engine):
    """
    Tüm integer ID sütunlarını kontrol eder ve gerekirse BigInteger'a dönüştürür
    """
    logger.info("ID sütunlarının BigInteger tipinde olup olmadığı kontrol ediliyor...")
    
    inspector = inspect(engine)
    tables_to_check = {
        'groups': ['group_id'],
        'telegram_users': ['user_id'],
        'group_members': ['user_id', 'group_id'],
        'data_mining': ['user_id', 'telegram_id', 'group_id'],
        'message_tracking': ['message_id', 'group_id', 'user_id'],
        'group_analytics': ['group_id'],
        'debug_bot_users': ['user_id'],
        'user_group_relation': ['user_id', 'group_id']
    }
    
    columns_to_update = []
    
    # Her tabloyu ve sütunu kontrol et
    for table, columns in tables_to_check.items():
        if table not in inspector.get_table_names():
            logger.warning(f"'{table}' tablosu bulunamadı, atlanıyor...")
            continue
            
        table_columns = {col['name']: col for col in inspector.get_columns(table)}
        
        for column in columns:
            if column not in table_columns:
                logger.warning(f"'{table}.{column}' sütunu bulunamadı, atlanıyor...")
                continue
                
            col_type = str(table_columns[column]['type']).lower()
            if 'int' in col_type and 'bigint' not in col_type:
                columns_to_update.append((table, column))
    
    if not columns_to_update:
        logger.info("Tüm ID sütunları zaten BigInteger tipinde.")
        return
    
    logger.info(f"{len(columns_to_update)} sütun BigInteger'a dönüştürülecek:")
    for table, column in columns_to_update:
        logger.info(f"  - {table}.{column}")
    
    # Sütunları güncelle
    with engine.begin() as conn:
        for table, column in columns_to_update:
            logger.info(f"'{table}.{column}' sütunu BigInteger'a dönüştürülüyor...")
            conn.execute(text(f"ALTER TABLE {table} ALTER COLUMN {column} TYPE BIGINT"))
    
    logger.info("BigInteger dönüştürme işlemi tamamlandı.")

def add_unique_constraints(engine):
    """
    Tablolara gerekli unique constraint'leri ekler
    """
    logger.info("Tablolara unique constraint'ler ekleniyor...")
    
    with engine.begin() as conn:
        # group_members tablosuna unique constraint ekle
        try:
            logger.info("'group_members' tablosuna (user_id, group_id) için unique constraint ekleniyor...")
            # Önce önceden var olan constrainti kontrol et
            inspector = inspect(engine)
            constraints = inspector.get_unique_constraints('group_members')
            constraint_names = [constraint['name'] for constraint in constraints]
            
            # Eğer unique_user_group constraint yoksa ekle
            if 'unique_user_group' not in constraint_names:
                conn.execute(text("""
                    ALTER TABLE group_members 
                    ADD CONSTRAINT unique_user_group 
                    UNIQUE (user_id, group_id)
                """))
                logger.info("'group_members' tablosuna unique constraint eklendi.")
            else:
                logger.info("'group_members' tablosunda unique constraint zaten mevcut.")
        except Exception as e:
            logger.error(f"Unique constraint eklenirken hata: {str(e)}")

def check_and_optimize_database(engine):
    """
    Veritabanı şemasını ve tablolarını kontrol eder, gerekirse optimize eder
    """
    logger.info("Veritabanı şema kontrolü ve optimizasyonu başlatılıyor...")
    
    # 1. Tablo analizi ve VACUUM
    with engine.begin() as conn:
        logger.info("Tablo analizleri yapılıyor...")
        conn.execute(text("ANALYZE"))
        
        logger.info("VACUUM işlemi başlatılıyor...")
        conn.execute(text("VACUUM ANALYZE"))
    
    # 2. Eksik indeksleri kontrol et ve oluştur
    create_indexes(engine)
    
    # 3. BigInt dönüşümünü kontrol et
    check_and_fix_bigint_columns(engine)
    
    # 4. Unique constraint'leri kontrol et
    add_unique_constraints(engine)
    
    # 5. Tablo istatistiklerini güncelle
    with engine.begin() as conn:
        logger.info("Tablo istatistikleri güncelleniyor...")
        conn.execute(text("ANALYZE"))
    
    logger.info("Veritabanı optimizasyonu tamamlandı.")

def main():
    """
    Ana fonksiyon
    """
    parser = argparse.ArgumentParser(description='PostgreSQL veritabanı şemasını oluşturur veya günceller')
    parser.add_argument('--drop', action='store_true', help='Tabloları düşür ve yeniden oluştur (DİKKAT: Tüm veriler silinecek)')
    parser.add_argument('--update-bigint', action='store_true', help='ID sütunlarını BigInteger\'a dönüştür')
    parser.add_argument('--add-constraints', action='store_true', help='Gerekli kısıtlamaları ekle')
    parser.add_argument('--check-bigint', action='store_true', help='ID sütunlarının BigInteger tipinde olup olmadığını kontrol et')
    parser.add_argument('--optimize', action='store_true', help='Veritabanını optimize et (indeksler, VACUUM, analizler)')
    args = parser.parse_args()
    
    db_url = get_db_url()
    logger.info(f"Veritabanı URL: {db_url}")
    
    engine = create_engine(db_url)
    
    if args.drop:
        answer = input("UYARI: Tüm veritabanı tabloları düşürülecek ve veriler silinecek. Devam etmek istiyor musunuz? (evet/hayır): ")
        if answer.lower() == 'evet':
            Base.metadata.drop_all(engine)
            logger.info("Tüm tablolar düşürüldü.")
        else:
            logger.info("İşlem iptal edildi.")
            return
    
    # Tabloları oluştur
    create_tables(engine)
    
    # Eksik kolonları ekle
    add_missing_columns(engine)
    
    # İndeksleri oluştur
    create_indexes(engine)
    
    # ID sütunlarını BigInteger'a dönüştür (eğer istenmişse)
    if args.update_bigint:
        update_integer_columns_to_bigint(engine)
    
    # ID sütunlarını kontrol et (eğer istenmişse)
    if args.check_bigint:
        check_and_fix_bigint_columns(engine)
    
    # Unique constraint'leri ekle (eğer istenmişse)
    if args.add_constraints:
        add_unique_constraints(engine)
    
    # Veritabanını optimize et (eğer istenmişse)
    if args.optimize:
        check_and_optimize_database(engine)
    
    logger.info("Veritabanı şeması başarıyla oluşturuldu/güncellendi.")

if __name__ == "__main__":
    main() 