"""
Kullanıcı veritabanı yönetimi
"""
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, List, Tuple
from pathlib import Path
import logging
import shutil
import time

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
            # Ana dizin oluştur
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Bağlantı oluştur
            self.connection = sqlite3.connect(self.db_path)
            with self.connection:
                self._create_tables()
                
            logger.info(f"Veritabanı başlatıldı: {self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"Veritabanı başlatma hatası: {str(e)}")
            # Veritabanı bozuk olabilir, yedekleme ve yeniden oluştur
            self._backup_and_recreate_if_needed()
        except Exception as e:
            logger.critical(f"Beklenmeyen veritabanı hatası: {str(e)}")
            raise
            
    def _backup_and_recreate_if_needed(self):
        """Bozuk veritabanını yedekler ve yeniden oluşturur"""
        try:
            # Yedek dosya adı oluştur
            backup_path = self.db_path.with_name(f"{self.db_path.stem}_backup_{int(time.time())}.db")
            
            # Yedekle
            if self.db_path.exists():
                shutil.copy2(self.db_path, backup_path)
                logger.warning(f"Bozuk veritabanı yedeklendi: {backup_path}")
                
                # Bozuk dosyayı sil
                self.db_path.unlink()
                
            # Yeniden oluştur
            self.connection = sqlite3.connect(self.db_path)
            with self.connection:
                self._create_tables()
                
            logger.info(f"Veritabanı yeniden oluşturuldu: {self.db_path}")
        except Exception as e:
            logger.critical(f"Veritabanı kurtarma hatası: {str(e)}")
            raise
            
    def _create_tables(self):
        """Veritabanı tablolarını oluştur ve güncelle."""
        with self.connection:
            # Önce ana tabloyu oluştur (ilk kez çalıştırıldığında)
            self.connection.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    invited INTEGER DEFAULT 0,
                    last_invited TIMESTAMP,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Hatalı gruplar tablosu
            self.connection.execute("""
                CREATE TABLE IF NOT EXISTS error_groups (
                    group_id INTEGER PRIMARY KEY,
                    group_title TEXT,
                    error_reason TEXT,
                    error_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    retry_after TIMESTAMP
                )
            """)
            
            # Tablo zaten var olduğundan, sütunları güvenli bir şekilde eklemeliyiz
            try:
                # Tablo sütunlarını kontrol et
                columns = [row[1] for row in self.connection.execute("PRAGMA table_info(users)")]
                
                # blocked sütunu yoksa ekle
                if 'blocked' not in columns:
                    self.connection.execute("ALTER TABLE users ADD COLUMN blocked INTEGER DEFAULT 0")
                    logger.info("Kullanıcılar tablosuna 'blocked' sütunu eklendi")
                    
                # is_admin sütunu yoksa ekle
                if 'is_admin' not in columns:
                    self.connection.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
                    logger.info("Kullanıcılar tablosuna 'is_admin' sütunu eklendi")
                    
                # İndeksler oluştur - hata olursa geç
                try:
                    self.connection.execute("CREATE INDEX IF NOT EXISTS idx_username ON users(username)")
                    self.connection.execute("CREATE INDEX IF NOT EXISTS idx_invited ON users(invited)")
                    self.connection.execute("CREATE INDEX IF NOT EXISTS idx_last_invited ON users(last_invited)")
                    if 'blocked' in columns:
                        self.connection.execute("CREATE INDEX IF NOT EXISTS idx_blocked ON users(blocked)")
                    if 'is_admin' in columns:
                        self.connection.execute("CREATE INDEX IF NOT EXISTS idx_is_admin ON users(is_admin)")
                        
                    # Hatalı gruplar için indeksler
                    self.connection.execute("CREATE INDEX IF NOT EXISTS idx_error_time ON error_groups(error_time)")
                    self.connection.execute("CREATE INDEX IF NOT EXISTS idx_retry_after ON error_groups(retry_after)")
                        
                except sqlite3.Error as e:
                    logger.warning(f"İndeks oluşturma hatası (önemli değil): {str(e)}")
                    
            except sqlite3.Error as e:
                logger.error(f"Tablo güncelleme hatası: {str(e)}")
            
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

    def update_last_invited(self, user_id: int):
        """Kullanıcının son davet gönderim zamanını güncelle"""
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with self.connection:
                self.connection.execute("""
                    UPDATE users
                    SET invited = invited + 1, last_invited = ?
                    WHERE user_id = ?
                """, (current_time, user_id))
                logger.debug(f"Kullanıcı davet bilgisi güncellendi - ID: {user_id}, Zaman: {current_time}")
        except sqlite3.Error as e:
            logger.error(f"Kullanıcı davet güncelleme hatası: {str(e)}")

    def mark_user_blocked(self, user_id: int):
        """Kullanıcıyı bloklu olarak işaretle"""
        try:
            with self.connection:
                self.connection.execute("""
                    UPDATE users
                    SET blocked = 1
                    WHERE user_id = ?
                """, (user_id,))
                logger.debug(f"Kullanıcı bloklu olarak işaretlendi - ID: {user_id}")
        except sqlite3.Error as e:
            logger.error(f"Kullanıcı bloklama hatası: {str(e)}")
            
    def mark_as_invited(self, user_id: int) -> None:
        """Kullanıcıyı davet edilmiş olarak işaretler"""
        try:
            with self.connection:
                self.connection.execute("""
                    UPDATE users
                    SET invited = 1, last_invited = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                """, (user_id,))
                logger.debug(f"Kullanıcı davet edildi olarak işaretlendi - ID: {user_id}")
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
            
    def was_recently_invited(self, user_id: int, hours: int = 4) -> bool:
        """Kullanıcının son X saat içinde davet edilip edilmediğini kontrol eder"""
        try:
            with self.connection:
                cursor = self.connection.execute("""
                    SELECT last_invited FROM users WHERE user_id = ?
                """, (user_id,))
                result = cursor.fetchone()
                
                if result and result[0]:
                    last_invited = datetime.fromisoformat(result[0].replace(' ', 'T'))
                    return (datetime.now() - last_invited) < timedelta(hours=hours)
                return False
        except sqlite3.Error as e:
            logger.error(f"Son davet kontrolü hatası: {str(e)}")
            return False
    
    def get_users_to_invite(self, limit: int = 10, min_hours_between_invites: int = 4) -> List[Tuple[int, str]]:
        """Davet edilecek kullanıcıları döndürür"""
        try:
            min_time = datetime.now() - timedelta(hours=min_hours_between_invites)
            min_time_str = min_time.strftime("%Y-%m-%d %H:%M:%S")
            
            # Hiç davet edilmemiş veya son davetten beri yeterince zaman geçmiş kullanıcıları getir
            with self.connection:
                cursor = self.connection.execute("""
                    SELECT user_id, username FROM users
                    WHERE (last_invited IS NULL OR last_invited < ?)
                    AND (blocked = 0 OR blocked IS NULL)
                    ORDER BY RANDOM()
                    LIMIT ?
                """, (min_time_str, limit))
                return cursor.fetchall()
        except sqlite3.Error as e:
            logger.error(f"Kullanıcı listeleme hatası: {str(e)}")
            return []
    
    # ---- Hata veren grupların yönetimi için yeni metotlar ----
    
    def add_error_group(self, group_id: int, group_title: str, error_reason: str, retry_hours: int = 8):
        """Hata veren grubu veritabanına ekler"""
        try:
            retry_time = datetime.now() + timedelta(hours=retry_hours)
            retry_time_str = retry_time.strftime("%Y-%m-%d %H:%M:%S")
            
            with self.connection:
                self.connection.execute("""
                    INSERT OR REPLACE INTO error_groups
                    (group_id, group_title, error_reason, error_time, retry_after)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?)
                """, (group_id, group_title, error_reason, retry_time_str))
                
            logger.info(f"Hatalı grup eklendi: {group_title} (ID:{group_id}) - {retry_hours} saat sonra tekrar denenecek")
            return True
        except sqlite3.Error as e:
            logger.error(f"Hatalı grup ekleme hatası: {str(e)}")
            return False
        
    def get_error_groups(self) -> list:
        """Veritabanındaki hatalı grupları döndürür"""
        try:
            with self.connection:
                cursor = self.connection.execute("""
                    SELECT group_id, group_title, error_reason, error_time, retry_after
                    FROM error_groups
                """)
                return cursor.fetchall()
        except sqlite3.Error as e:
            logger.error(f"Hatalı grup getirme hatası: {str(e)}")
            return []
        
    def clear_expired_error_groups(self) -> int:
        """Süresi dolmuş hataları temizler ve temizlenen sayısını döndürür"""
        try:
            with self.connection:
                cursor = self.connection.execute("""
                    DELETE FROM error_groups
                    WHERE retry_after < CURRENT_TIMESTAMP
                """)
                return cursor.rowcount
        except sqlite3.Error as e:
            logger.error(f"Hata temizleme hatası: {str(e)}")
            return 0
        
    def clear_all_error_groups(self) -> int:
        """Tüm hata kayıtlarını temizler ve temizlenen sayısını döndürür"""
        try:
            with self.connection:
                cursor = self.connection.execute("DELETE FROM error_groups")
                return cursor.rowcount
        except sqlite3.Error as e:
            logger.error(f"Tüm hataları temizleme hatası: {str(e)}")
            return 0
            
    # Veritabanı performans ve bakım fonksiyonlarını ekle
    def optimize_database(self):
        """Veritabanı performans optimizasyonları yapar"""
        try:
            with self.connection:
                self.connection.execute("VACUUM")
                self.connection.execute("ANALYZE")
                logger.info("Veritabanı optimize edildi")
            return True
        except sqlite3.Error as e:
            logger.error(f"Veritabanı optimizasyon hatası: {str(e)}")
            return False
        
    def get_database_stats(self):
        """Veritabanı istatistiklerini döndürür"""
        stats = {
            "total_users": 0,
            "invited_users": 0,
            "blocked_users": 0,
            "error_groups": 0
        }
        
        try:
            with self.connection:
                # Toplam kullanıcı sayısı
                cursor = self.connection.execute("SELECT COUNT(*) FROM users")
                stats["total_users"] = cursor.fetchone()[0]
                
                # Davet edilen kullanıcı sayısı
                cursor = self.connection.execute("SELECT COUNT(*) FROM users WHERE invited > 0")
                stats["invited_users"] = cursor.fetchone()[0]
                
                # Engellenen kullanıcı sayısı
                cursor = self.connection.execute("SELECT COUNT(*) FROM users WHERE blocked = 1")
                stats["blocked_users"] = cursor.fetchone()[0]
                
                # Hata veren grup sayısı
                cursor = self.connection.execute("SELECT COUNT(*) FROM error_groups")
                stats["error_groups"] = cursor.fetchone()[0]
                
            return stats
        except sqlite3.Error as e:
            logger.error(f"Veritabanı istatistikleri alma hatası: {str(e)}")
            return stats
            
    def get_all_users(self):
        """Tüm kullanıcıları getirir"""
        try:
            with self.connection:
                cursor = self.connection.execute("""
                    SELECT user_id, username, invited, last_invited, 
                           first_seen, blocked, is_admin 
                    FROM users
                    ORDER BY user_id
                """)
                return cursor.fetchall()
        except sqlite3.Error as e:
            logger.error(f"Tüm kullanıcıları getirme hatası: {str(e)}")
            return []
        
    def backup_database(self):
        """Veritabanının yedeğini alır"""
        try:
            # Yedek dosya adı oluştur
            backup_dir = self.db_path.parent / "backups"
            backup_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = backup_dir / f"users_backup_{timestamp}.db"
            
            # Bağlantıyı kapatma
            if hasattr(self, 'connection') and self.connection:
                self.connection.close()
                
            # Dosyayı kopyala
            import shutil
            shutil.copy2(self.db_path, backup_path)
            
            # Bağlantıyı yeniden aç
            self.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=20,
                isolation_level=None
            )
            
            logger.info(f"Veritabanı yedeklendi: {backup_path}")
            return True, str(backup_path)
        except Exception as e:
            logger.error(f"Veritabanı yedekleme hatası: {str(e)}")
            return False, str(e)
            
    def close(self):
        """Veritabanı bağlantısını kapatır"""
        if self.connection:
            try:
                self.connection.close()
                logger.info("Veritabanı bağlantısı kapatıldı")
            except sqlite3.Error as e:
                logger.error(f"Veritabanı kapatma hatası: {str(e)}")
                
    def close_connection(self):
        """Veritabanı bağlantısını güvenli şekilde kapatır"""
        try:
            if self.connection:
                self.connection.close()
                logger.info("Veritabanı bağlantısı kapatıldı")
        except Exception as e:
            logger.error(f"Veritabanı kapatma hatası: {str(e)}")