"""
Kullanıcı veritabanı yönetimi
"""
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, List, Tuple
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class UserDatabase:
    """
    Kullanıcı bilgilerini SQLite veritabanında yöneten sınıf
    """
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._initialize_database()
        
        # SQLite için performans ayarları
        self.connection = sqlite3.connect(
            self.db_path,
            check_same_thread=False,  # Birden fazla thread'den erişim için
            timeout=20,               # Maksimum bekleme süresi
            isolation_level=None      # Otomatik commit için
        )
        
        # Performans optimize et
        self.connection.execute("PRAGMA journal_mode = WAL;")  # Write-ahead logging
        self.connection.execute("PRAGMA synchronous = NORMAL;")  # Daha hızlı yazma
        self.connection.execute("PRAGMA cache_size = 10000;")    # Önbellek boyutu
        self.connection.execute("PRAGMA temp_store = MEMORY;")   # Geçici verileri RAM'de sakla
        
    def _initialize_database(self):
        """Veritabanını başlatır"""
        try:
            self.connection = sqlite3.connect(self.db_path)
            with self.connection:
                self.connection.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        username TEXT,
                        invited INTEGER DEFAULT 0,
                        last_invited TIMESTAMP,
                        is_admin INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                self.connection.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON users (user_id)")
                self.connection.execute("CREATE INDEX IF NOT EXISTS idx_invited ON users (invited)")
                
            logger.info(f"Veritabanı başlatıldı: {self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"Veritabanı başlatma hatası: {str(e)}")
            raise
            
    def add_user(self, user_id: int, username: Optional[str]) -> None:
        """Kullanıcıyı veritabanına ekler"""
        try:
            with self.connection:
                self.connection.execute("""
                    INSERT OR IGNORE INTO users (user_id, username, invited, last_invited)
                    VALUES (?, ?, 0, NULL)
                """, (user_id, username))
                logger.debug(f"Kullanıcı eklendi - ID: {user_id}, Username: {username}")
        except sqlite3.Error as e:
            logger.error(f"Kullanıcı ekleme hatası: {str(e)}")
            
    def mark_as_invited(self, user_id: int) -> None:
        """Kullanıcıyı davet edilmiş olarak işaretler"""
        try:
            with self.connection:
                self.connection.execute("""
                    UPDATE users
                    SET invited = 1, last_invited = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                """, (user_id,))
        except sqlite3.Error as e:
            logger.error(f"Kullanıcı işaretleme hatası: {str(e)}")
            
    def is_invited(self, user_id: int) -> bool:
        """Kullanıcının davet edilip edilmediğini kontrol eder"""
        try:
            with self.connection:
                cursor = self.connection.execute("""
                    SELECT invited FROM users WHERE user_id = ?
                """, (user_id,))
                result = cursor.fetchone()
                return result is not None and result[0] == 1
        except sqlite3.Error as e:
            logger.error(f"Kullanıcı kontrol hatası: {str(e)}")
            return False
            
    def was_recently_invited(self, user_id: int, hours: int = 6) -> bool:
        """Kullanıcının son X saat içinde davet edilip edilmediğini kontrol eder"""
        try:
            with self.connection:
                cursor = self.connection.execute("""
                    SELECT last_invited FROM users WHERE user_id = ?
                """, (user_id,))
                result = cursor.fetchone()
                
                if result and result[0]:
                    last_invited = datetime.fromisoformat(result[0])
                    return (datetime.now() - last_invited) < timedelta(hours=hours)
                return False
        except sqlite3.Error as e:
            logger.error(f"Son davet kontrolü hatası: {str(e)}")
            return False
    
    def get_users_to_invite(self, limit: int = 10) -> List[Tuple[int, str]]:
        """Davet edilecek kullanıcıları döndürür"""
        try:
            with self.connection:
                cursor = self.connection.execute("""
                    SELECT user_id, username FROM users
                    WHERE invited = 0 AND is_admin = 0
                    LIMIT ?
                """, (limit,))
                return cursor.fetchall()
        except sqlite3.Error as e:
            logger.error(f"Kullanıcı listeleme hatası: {str(e)}")
            return []
            
    def close(self):
        """Veritabanı bağlantısını kapatır"""
        if self.connection:
            try:
                self.connection.close()
                logger.info("Veritabanı bağlantısı kapatıldı")
            except sqlite3.Error as e:
                logger.error(f"Veritabanı kapatma hatası: {str(e)}")