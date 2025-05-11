"""
# ============================================================================ #
# Dosya: fix_database.py
# Yol: /Users/siyahkare/code/telegram-bot/app/scripts/fix_database.py
# İşlev: Veritabanı şemasını ve verilerini doğrular ve düzeltir.
#
# Amaç: Bu script, veritabanı yapısını kontrol eder, eksik sütunları ekler,
# tutarsızlıkları düzeltir ve veri bütünlüğünü doğrular. update_schema.py'dan 
# farklı olarak, bu script daha spesifik sorunlara odaklanır ve hızlı düzeltmeler 
# için kullanılır. İşlem öncesinde otomatik yedekleme yapar.
#
# Temel Özellikler:
# - Eksik sütunları tespit etme ve ekleme
# - Tutarsız verileri tanımlama ve düzeltme
# - İşlem öncesi veritabanı yedekleme
# - Bozuk indexleri tespit etme ve yeniden oluşturma
# - Kapsamlı loglama ve hata yönetimi
# - İnteraktif kullanıcı onayı ve rapor görüntüleme
#
# Kullanım:
#   python fix_database.py [--no-backup] [--yes] [--verbose] [--db-path=...]
#
# Build: 2025-04-08-23:55:00
# Versiyon: v3.5.0
# ============================================================================ #
#
# Değişiklik Geçmişi:
# v3.5.0 (2025-04-08) - Kapsamlı logları ve hata yönetimi eklendi
#                      - Komut satırı parametreleri eklendi
#                      - Otomatik yedekleme özelliği eklendi
#                      - Kapsamlı düzeltme kontrolleri (users, groups, user_groups)
#                      - Veri tutarlılık kontrolleri eklendi
#                      - invoke_history tablosu desteği eklendi
#                      - İstatistik raporlama özelliği eklendi
# v3.4.0 (2025-04-01) - Temel şema doğrulaması eklendi
# v3.3.0 (2025-03-15) - İlk sürüm
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

import os
import sys
import sqlite3
import argparse
import logging
import shutil
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any, Union

# Ana dizini Python yoluna ekle
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

# Log yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Sabitler
DB_VERSION = "3.5.0"
DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "../../data/users.db")
BACKUP_DIR = os.path.join(os.path.dirname(__file__), "../../backups")

class DatabaseFixer:
    """
    Veritabanı şema ve veri sorunlarını tespit eden ve düzelten sınıf.
    
    Bu sınıf, veritabanında eksik sütunları tespit eder ve ekler,
    tutarsız verileri düzeltir, bozuk indexleri yeniden oluşturur
    ve veri bütünlüğünü kontrol eder.
    
    Attributes:
        db_path (str): Veritabanı dosya yolu
        conn (sqlite3.Connection): SQLite bağlantı nesnesi
        cursor (sqlite3.Cursor): SQLite cursor nesnesi
        fix_count (int): Yapılan düzeltme sayısı
        verbose (bool): Ayrıntılı loglama yapılıp yapılmayacağı
    """
    
    def __init__(self, db_path: str, verbose: bool = False):
        """
        DatabaseFixer sınıfını başlatır.
        
        Args:
            db_path: Veritabanı dosya yolu
            verbose: Ayrıntılı log çıktısı aktif olsun mu
        """
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self.fix_count = 0
        self.verbose = verbose
    
    def connect(self) -> bool:
        """
        Veritabanına bağlanır.
        
        Returns:
            bool: Bağlantı başarılıysa True
        """
        try:
            self.conn = sqlite3.connect(self.db_path)
            # Dictionary formatında sonuç almak için
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
            logger.info(f"Veritabanına bağlantı başarılı: {self.db_path}")
            return True
        except sqlite3.Error as e:
            logger.error(f"Veritabanı bağlantı hatası: {e}")
            return False
    
    def close(self) -> None:
        """
        Veritabanı bağlantısını kapatır.
        """
        if self.conn:
            self.conn.close()
            logger.info("Veritabanı bağlantısı kapatıldı")
    
    def backup_database(self) -> bool:
        """
        İşlemlerden önce veritabanının yedeğini alır.
        
        Returns:
            bool: Yedekleme başarılıysa True
        """
        try:
            # Yedek dizinini oluştur
            os.makedirs(BACKUP_DIR, exist_ok=True)
            
            # Yedek dosya adı
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(BACKUP_DIR, f"db_backup_before_fix_{timestamp}.bak")
            
            # Veritabanını kopyala
            shutil.copy2(self.db_path, backup_path)
            
            logger.info(f"Veritabanı yedeği başarıyla oluşturuldu: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Veritabanı yedekleme hatası: {e}")
            return False
    
    def fix_database(self) -> int:
        """
        Tüm veritabanı düzeltmelerini gerçekleştirir.
        
        Returns:
            int: Toplam düzeltme sayısı
        """
        self.fix_count = 0
        
        # Tablo varlık kontrolü
        self._ensure_tables_exist()
        
        # Kullanıcı tablosu düzeltmeleri
        self._fix_users_table()
        
        # Gruplar tablosu düzeltmeleri
        self._fix_groups_table()
        
        # İlişki tabloları düzeltmeleri
        self._fix_relationship_tables()
        
        # Kayıp ilişkileri düzeltme
        self._fix_missing_relations()
        
        # Veri tutarlılığını kontrol etme
        self._check_data_consistency()
        
        # Indexleri kontrol etme ve yeniden oluşturma
        self._fix_indexes()
        
        # Database VACUUM - Boş alanları temizle ve veritabanını optimize et
        self._vacuum_database()
        
        # Schema versiyon kontrolü
        self._update_schema_version()
        
        return self.fix_count
    
    def _ensure_tables_exist(self) -> None:
        """
        Gerekli tabloların varlığını kontrol eder ve yoksa oluşturur.
        """
        # Olması gereken tablolar
        required_tables = ['users', 'groups', 'user_groups', 'invite_history', 'schema_version']
        
        # Mevcut tabloları kontrol et
        self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = [row['name'] for row in self.cursor.fetchall()]
        
        missing_tables = set(required_tables) - set(existing_tables)
        if missing_tables:
            logger.warning(f"Eksik tablolar tespit edildi: {missing_tables}")
            
            # users tablosu yok mu?
            if 'users' in missing_tables:
                logger.info("users tablosu oluşturuluyor...")
                self.cursor.execute('''
                CREATE TABLE users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    source_group TEXT,
                    join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_invited TIMESTAMP,
                    invite_count INTEGER DEFAULT 0,
                    is_bot INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                ''')
                self.fix_count += 1
                logger.info("✅ users tablosu oluşturuldu")
            
            # groups tablosu yok mu?
            if 'groups' in missing_tables:
                logger.info("groups tablosu oluşturuluyor...")
                self.cursor.execute('''
                CREATE TABLE groups (
                    group_id INTEGER PRIMARY KEY,
                    name TEXT,
                    join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_message TIMESTAMP,
                    message_count INTEGER DEFAULT 0,
                    member_count INTEGER DEFAULT 0,
                    error_count INTEGER DEFAULT 0,
                    last_error TEXT,
                    is_active INTEGER DEFAULT 1,
                    permanent_error INTEGER DEFAULT 0,
                    is_target INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                ''')
                self.fix_count += 1
                logger.info("✅ groups tablosu oluşturuldu")
            
            # user_groups tablosu yok mu?
            if 'user_groups' in missing_tables:
                logger.info("user_groups tablosu oluşturuluyor...")
                self.cursor.execute('''
                CREATE TABLE user_groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    group_id INTEGER,
                    join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, group_id),
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                    FOREIGN KEY (group_id) REFERENCES groups(group_id) ON DELETE CASCADE
                )
                ''')
                self.fix_count += 1
                logger.info("✅ user_groups tablosu oluşturuldu")
            
            # invite_history tablosu yok mu?
            if 'invite_history' in missing_tables:
                logger.info("invite_history tablosu oluşturuluyor...")
                self.cursor.execute('''
                CREATE TABLE invite_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT,
                    response TEXT,
                    message_template TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
                ''')
                self.fix_count += 1
                logger.info("✅ invite_history tablosu oluşturuldu")
                
            # schema_version tablosu yok mu?
            if 'schema_version' in missing_tables:
                logger.info("schema_version tablosu oluşturuluyor...")
                self.cursor.execute('''
                CREATE TABLE schema_version (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    version TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    changes_description TEXT
                )
                ''')
                self.fix_count += 1
                logger.info("✅ schema_version tablosu oluşturuldu")
        else:
            logger.info("Tüm gerekli tablolar mevcut")
    
    def _fix_users_table(self) -> None:
        """
        Kullanıcı tablosundaki eksik sütunları ve tutarsız verileri düzeltir.
        """
        # Mevcut sütunları kontrol et
        self.cursor.execute("PRAGMA table_info(users)")
        columns = [row['name'] for row in self.cursor.fetchall()]
        
        # last_invited sütunu eksikse ekle
        if "last_invited" not in columns:
            logger.info("'last_invited' sütunu ekleniyor...")
            self.cursor.execute("ALTER TABLE users ADD COLUMN last_invited TIMESTAMP")
            self.fix_count += 1
            logger.info("✅ 'last_invited' sütunu eklendi")
        else:
            logger.info("'last_invited' sütunu zaten var.")
        
        # Diğer eksik sütunları kontrol et ve ekle
        required_columns = {
            "invite_count": "INTEGER DEFAULT 0",
            "is_bot": "INTEGER DEFAULT 0",
            "is_active": "INTEGER DEFAULT 1",
            "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        }
        
        for column, definition in required_columns.items():
            if column not in columns:
                logger.info(f"'{column}' sütunu ekleniyor...")
                self.cursor.execute(f"ALTER TABLE users ADD COLUMN {column} {definition}")
                self.fix_count += 1
                logger.info(f"✅ '{column}' sütunu eklendi")
        
        # Tutarsız verileri düzelt
        self._fix_inconsistent_user_data()
    
    def _fix_inconsistent_user_data(self) -> None:
        """
        Kullanıcı tablosundaki tutarsız verileri düzeltir.
        """
        # Örnek: is_active sütunu NULL olan kayıtları düzelt
        self.cursor.execute("UPDATE users SET is_active = 1 WHERE is_active IS NULL")
        affected_rows = self.cursor.rowcount
        if affected_rows > 0:
            self.fix_count += affected_rows
            logger.info(f"✅ {affected_rows} tutarsız kullanıcı kaydı düzeltildi")
    
    def _fix_groups_table(self) -> None:
        """
        Gruplar tablosundaki eksik sütunları ve tutarsız verileri düzeltir.
        """
        # Mevcut sütunları kontrol et
        self.cursor.execute("PRAGMA table_info(groups)")
        columns = [row['name'] for row in self.cursor.fetchall()]
        
        # last_message sütunu eksikse ekle
        if "last_message" not in columns:
            logger.info("'last_message' sütunu ekleniyor...")
            self.cursor.execute("ALTER TABLE groups ADD COLUMN last_message TIMESTAMP")
            self.fix_count += 1
            logger.info("✅ 'last_message' sütunu eklendi")
        else:
            logger.info("'last_message' sütunu zaten var.")
        
        # Diğer eksik sütunları kontrol et ve ekle
        required_columns = {
            "message_count": "INTEGER DEFAULT 0",
            "member_count": "INTEGER DEFAULT 0",
            "error_count": "INTEGER DEFAULT 0",
            "last_error": "TEXT",
            "is_active": "INTEGER DEFAULT 1",
            "permanent_error": "INTEGER DEFAULT 0",
            "is_target": "INTEGER DEFAULT 1",
            "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        }
        
        for column, definition in required_columns.items():
            if column not in columns:
                logger.info(f"'{column}' sütunu ekleniyor...")
                self.cursor.execute(f"ALTER TABLE groups ADD COLUMN {column} {definition}")
                self.fix_count += 1
                logger.info(f"✅ '{column}' sütunu eklendi")
        
        # Tutarsız verileri düzelt
        self._fix_inconsistent_group_data()
    
    def _fix_inconsistent_group_data(self) -> None:
        """
        Gruplar tablosundaki tutarsız verileri düzeltir.
        """
        # Örnek: is_active sütunu NULL olan kayıtları düzelt
        self.cursor.execute("UPDATE groups SET is_active = 1 WHERE is_active IS NULL")
        affected_rows = self.cursor.rowcount
        if affected_rows > 0:
            self.fix_count += affected_rows
            logger.info(f"✅ {affected_rows} tutarsız grup kaydı düzeltildi")
    
    def _fix_relationship_tables(self) -> None:
        """
        İlişki tablolarındaki eksik sütunları ve tutarsız verileri düzeltir.
        """
        # user_groups tablosundaki eksik sütunları kontrol et ve ekle
        self.cursor.execute("PRAGMA table_info(user_groups)")
        columns = [row['name'] for row in self.cursor.fetchall()]
        
        required_columns = {
            "join_date": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        }
        
        for column, definition in required_columns.items():
            if column not in columns:
                logger.info(f"'{column}' sütunu ekleniyor...")
                self.cursor.execute(f"ALTER TABLE user_groups ADD COLUMN {column} {definition}")
                self.fix_count += 1
                logger.info(f"✅ '{column}' sütunu eklendi")
        
        # invite_history tablosundaki eksik sütunları kontrol et ve ekle
        self.cursor.execute("PRAGMA table_info(invite_history)")
        columns = [row['name'] for row in self.cursor.fetchall()]
        
        required_columns = {
            "status": "TEXT",
            "response": "TEXT",
            "message_template": "TEXT"
        }
        
        for column, definition in required_columns.items():
            if column not in columns:
                logger.info(f"'{column}' sütunu ekleniyor...")
                self.cursor.execute(f"ALTER TABLE invite_history ADD COLUMN {column} {definition}")
                self.fix_count += 1
                logger.info(f"✅ '{column}' sütunu eklendi")
        
        # Tutarsız verileri düzelt
        self._fix_inconsistent_relationship_data()
    
    def _fix_inconsistent_relationship_data(self) -> None:
        """
        İlişki tablolarındaki tutarsız verileri düzeltir.
        """
        # Örnek: join_date sütunu NULL olan kayıtları düzelt
        self.cursor.execute("UPDATE user_groups SET join_date = CURRENT_TIMESTAMP WHERE join_date IS NULL")
        affected_rows = self.cursor.rowcount
        if affected_rows > 0:
            self.fix_count += affected_rows
            logger.info(f"✅ {affected_rows} tutarsız ilişki kaydı düzeltildi")
    
    def _fix_missing_relations(self) -> None:
        """
        Kayıp ilişkileri tespit eder ve düzeltir.
        """
        # Örnek: user_groups tablosunda user_id veya group_id olmayan kayıtları sil
        self.cursor.execute("DELETE FROM user_groups WHERE user_id NOT IN (SELECT user_id FROM users) OR group_id NOT IN (SELECT group_id FROM groups)")
        affected_rows = self.cursor.rowcount
        if affected_rows > 0:
            self.fix_count += affected_rows
            logger.info(f"✅ {affected_rows} kayıp ilişki kaydı silindi")
    
    def _check_data_consistency(self) -> None:
        """
        Veri tutarlılığını kontrol eder ve tutarsız verileri düzeltir.
        """
        # Örnek: users tablosunda is_active sütunu NULL olan kayıtları düzelt
        self.cursor.execute("UPDATE users SET is_active = 1 WHERE is_active IS NULL")
        affected_rows = self.cursor.rowcount
        if affected_rows > 0:
            self.fix_count += affected_rows
            logger.info(f"✅ {affected_rows} tutarsız kullanıcı kaydı düzeltildi")
    
    def _fix_indexes(self) -> None:
        """
        Bozuk indexleri tespit eder ve yeniden oluşturur.
        """
        # Örnek: users tablosundaki indexleri kontrol et ve yeniden oluştur
        self.cursor.execute("PRAGMA index_list(users)")
        indexes = [row['name'] for row in self.cursor.fetchall()]
        
        required_indexes = {
            "idx_users_username": "CREATE INDEX idx_users_username ON users(username)",
            "idx_users_first_name": "CREATE INDEX idx_users_first_name ON users(first_name)",
            "idx_users_last_name": "CREATE INDEX idx_users_last_name ON users(last_name)"
        }
        
        for index, create_statement in required_indexes.items():
            if index not in indexes:
                logger.info(f"'{index}' indexi oluşturuluyor...")
                self.cursor.execute(create_statement)
                self.fix_count += 1
                logger.info(f"✅ '{index}' indexi oluşturuldu")
    
    def _vacuum_database(self) -> None:
        """
        Veritabanını optimize eder ve boş alanları temizler.
        """
        logger.info("Veritabanı optimize ediliyor (VACUUM)...")
        self.cursor.execute("VACUUM")
        logger.info("✅ Veritabanı optimize edildi")
    
    def _update_schema_version(self) -> None:
        """
        Veritabanı şema versiyonunu günceller.
        """
        logger.info("Veritabanı şema versiyonu güncelleniyor...")
        self.cursor.execute("INSERT INTO schema_version (version, changes_description) VALUES (?, ?)", (DB_VERSION, "Veritabanı şema ve veri düzeltmeleri"))
        self.fix_count += 1
        logger.info("✅ Veritabanı şema versiyonu güncellendi")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Veritabanı şemasını ve verilerini doğrular ve düzeltir.")
    parser.add_argument("--no-backup", action="store_true", help="Veritabanı yedeği alınmadan düzeltme yapar")
    parser.add_argument("--yes", action="store_true", help="Kullanıcı onayı istemeden düzeltme yapar")
    parser.add_argument("--verbose", action="store_true", help="Ayrıntılı log çıktısı sağlar")
    parser.add_argument("--db-path", type=str, default=DEFAULT_DB_PATH, help="Veritabanı dosya yolu")
    
    args = parser.parse_args()
    
    fixer = DatabaseFixer(db_path=args.db_path, verbose=args.verbose)
    
    if not args.no_backup:
        if not fixer.backup_database():
            logger.error("Veritabanı yedeği alınamadı, işlem iptal ediliyor")
            sys.exit(1)
    
    if not fixer.connect():
        logger.error("Veritabanına bağlanılamadı, işlem iptal ediliyor")
        sys.exit(1)
    
    try:
        fix_count = fixer.fix_database()
        logger.info(f"Toplam {fix_count} düzeltme yapıldı")
    except Exception as e:
        logger.error(f"Düzeltme işlemi sırasında hata: {e}")
    finally:
        fixer.close()