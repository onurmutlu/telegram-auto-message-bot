#!/usr/bin/env python3
"""
Özellikle groups tablosunu düzeltmek için script.
"""
import os
import psycopg2
from urllib.parse import urlparse
from dotenv import load_dotenv
import logging
import sys

# Log formatını ayarla
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# .env dosyasından ayarları yükle
load_dotenv()

# Veritabanı bağlantı bilgilerini al
db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/telegram_bot')

# Bağlantı parametrelerini ayrıştır
url = urlparse(db_url)
db_name = url.path[1:]  # / işaretini kaldır
db_user = url.username or 'postgres'
db_password = url.password or 'postgres'
db_host = url.hostname or 'localhost'
db_port = url.port or 5432

logger.info(f"Veritabanı: {db_host}:{db_port}/{db_name} (Kullanıcı: {db_user})")

def fix_groups_table():
    """
    groups tablosunu düzeltir
    """
    try:
        # Veritabanına bağlan
        conn = psycopg2.connect(
            dbname=db_name,
            user=db_user,
            password=db_password,
            host=db_host,
            port=db_port
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        logger.info("Veritabanına bağlandı")
        
        # 1. Superuser yetkisi
        try:
            cursor.execute(f"ALTER ROLE {db_user} WITH SUPERUSER;")
            logger.info(f"{db_user} kullanıcısı superuser yapıldı")
        except Exception as e:
            logger.error(f"Superuser yapılırken hata: {str(e)}")
            
        # 2. Örnek grup verileri
        sample_groups = [
            (-1, 'Örnek Grup', True, True),
            (-2, 'Test Grubu', False, True),
            (-3, 'Duyuru Grubu', True, True)
        ]
        
        # 3. Mevcut groups tablosunu yedekle
        try:
            # Mevcut tabloyu kontrol et
            cursor.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'groups')")
            if cursor.fetchone()[0]:
                try:
                    # Mevcut verileri yedekle
                    backup_table = "groups_backup"
                    # Önce eski yedeği sil (varsa)
                    cursor.execute(f"DROP TABLE IF EXISTS {backup_table}")
                    # Yeni yedek oluştur
                    cursor.execute(f"CREATE TABLE {backup_table} AS SELECT * FROM groups")
                    logger.info(f"groups tablosu yedeklendi: {backup_table}")
                    
                    # Mevcut verileri say
                    cursor.execute("SELECT COUNT(*) FROM groups")
                    count = cursor.fetchone()[0]
                    logger.info(f"groups tablosunda {count} kayıt bulundu")
                except Exception as e:
                    logger.error(f"groups tablosu yedeği oluşturulurken hata: {str(e)}")
        except Exception as e:
            logger.error(f"groups tablosu yedeklenirken genel hata: {str(e)}")
            
        # 4. Mevcut groups tablosunu düşür
        try:
            cursor.execute("DROP TABLE IF EXISTS groups CASCADE")
            logger.info("groups tablosu silindi (CASCADE)")
        except Exception as e:
            logger.error(f"groups tablosu silinirken hata: {str(e)}")
            
        # 5. groups tablosunu yeniden oluştur
        try:
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS groups (
                id SERIAL PRIMARY KEY,
                group_id BIGINT UNIQUE NOT NULL,
                name TEXT,
                join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_message TIMESTAMP,
                message_count INTEGER DEFAULT 0,
                member_count INTEGER DEFAULT 0,
                error_count INTEGER DEFAULT 0,
                last_error TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                permanent_error BOOLEAN DEFAULT FALSE,
                is_target BOOLEAN DEFAULT FALSE,
                retry_after TIMESTAMP,
                is_admin BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_groups_group_id ON groups(group_id);
            CREATE INDEX IF NOT EXISTS idx_groups_is_active ON groups(is_active);
            """)
            logger.info("groups tablosu yeniden oluşturuldu")
            
            # Sahiplik ve yetkileri ayarla
            cursor.execute(f"""
            ALTER TABLE groups OWNER TO {db_user};
            ALTER SEQUENCE groups_id_seq OWNER TO {db_user};
            GRANT ALL PRIVILEGES ON TABLE groups TO {db_user};
            GRANT ALL PRIVILEGES ON SEQUENCE groups_id_seq TO {db_user};
            """)
            logger.info("groups tablosu için sahiplik ve yetkiler ayarlandı")
        except Exception as e:
            logger.error(f"groups tablosu oluşturulurken hata: {str(e)}")
            
        # 6. Yedekteki verileri geri yükle
        try:
            backup_table = "groups_backup"
            # Yedek tablo var mı kontrol et
            cursor.execute(f"SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '{backup_table}')")
            if cursor.fetchone()[0]:
                try:
                    # Verileri geri yükle (mümkün olduğunca çok sütun eşleştirmeye çalış)
                    cursor.execute(f"""
                    INSERT INTO groups (id, group_id, name, join_date, last_message, 
                                       message_count, member_count, error_count, last_error,
                                       is_active, permanent_error, is_target, retry_after, is_admin)
                    SELECT id, group_id, name, join_date, last_message, 
                           message_count, member_count, error_count, last_error,
                           is_active, permanent_error, is_target, retry_after, is_admin
                    FROM {backup_table}
                    ON CONFLICT (group_id) DO NOTHING
                    """)
                    
                    # Kaç kayıt eklendi
                    cursor.execute("SELECT COUNT(*) FROM groups")
                    count = cursor.fetchone()[0]
                    logger.info(f"groups tablosuna {count} kayıt geri yüklendi")
                except Exception as e:
                    logger.error(f"groups tablosuna veriler geri yüklenirken hata: {str(e)}")
            else:
                logger.warning("groups_backup tablosu bulunamadı, örnek veriler eklenecek")
        except Exception as e:
            logger.error(f"Veri geri yüklemede genel hata: {str(e)}")
            
        # 7. Kayıt yoksa örnek verileri ekle
        try:
            cursor.execute("SELECT COUNT(*) FROM groups")
            count = cursor.fetchone()[0]
            
            if count == 0:
                for group in sample_groups:
                    try:
                        cursor.execute("""
                        INSERT INTO groups (group_id, name, is_admin, is_active)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (group_id) DO NOTHING
                        """, group)
                    except Exception as e:
                        logger.error(f"Örnek grup eklenirken hata: {str(e)}")
                
                logger.info("Örnek gruplar eklendi")
        except Exception as e:
            logger.error(f"Örnek grup verilerini eklerken hata: {str(e)}")
            
        # 8. Veritabanını temizle ve yedekleri sil
        try:
            cursor.execute("VACUUM ANALYZE groups")
            cursor.execute("REINDEX TABLE groups")
            logger.info("groups tablosu optimize edildi")
        except Exception as e:
            logger.error(f"Veritabanı temizleme hatası: {str(e)}")
        
        # Bağlantıyı kapat
        cursor.close()
        conn.close()
        logger.info("İşlem başarıyla tamamlandı")
        
    except Exception as e:
        logger.error(f"Genel hata: {str(e)}")
        
if __name__ == "__main__":
    fix_groups_table() 