"""
# ============================================================================ #
# Dosya: user_db.py
# Yol: /Users/siyahkare/code/telegram-bot/database/user_db.py
# İşlev: Telegram Bot Kullanıcı Veritabanı Yönetimi
#
# Amaç: Telegram bot uygulaması için kullanıcı bilgilerini saklamak, yönetmek ve sorgulamak.
#       Bu modül, SQLite veritabanı kullanarak kullanıcıların ID'lerini, kullanıcı adlarını,
#       davet durumlarını, engellenme durumlarını ve diğer ilgili bilgileri kaydeder.
#
# Build: 2025-04-01-00:07:55
# Versiyon: v3.4.0
# ============================================================================ #
#
# Bu modül, Telegram bot uygulamasının temel bileşenlerinden biridir ve aşağıdaki işlevleri sağlar:
# - Kullanıcı ekleme, güncelleme ve sorgulama
# - Davet durumlarını yönetme
# - Engellenen kullanıcıları takip etme
# - Hata yönetimi ve loglama
# - Veritabanı yedekleme ve optimizasyon
#
# ============================================================================ #
"""
import os
import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path
import time
import shutil
import json
from config.settings import Config
from typing import Optional, Dict, List, Any, Union, Tuple

logger = logging.getLogger(__name__)

class UserDatabase:
    """
    SQLite veritabanında kullanıcı bilgilerini yöneten sınıf.
    Bu sınıf, kullanıcı ekleme, güncelleme, sorgulama ve silme gibi temel veritabanı işlemlerini sağlar.
    Ayrıca, veritabanı bağlantısını yönetir, yedekleme yapar ve performans optimizasyonları uygular.
    """
    def __init__(self, db_path="data/users.db"):
        """Veritabanını başlatır."""
        self.db_path = Path(db_path)  # Path nesnesi kullan
        
        # Veritabanı dizinin var olduğundan emin ol
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path_str = str(self.db_path)  # String olarak sakla
        
        # Bağlantıyı tut
        self.conn = sqlite3.connect(self.db_path_str)
        self.connection = self.conn  # İki değişkeni aynı nesneye referans yap
        
        # Row factory ayarla
        self.conn.row_factory = sqlite3.Row
        
        # Cursor oluştur
        self.cursor = self.conn.cursor()
        
        # Tabloları oluştur
        self._create_tables()
        
        logger.info(f"Veritabanı bağlandı: {self.db_path_str}")

    def _initialize_database(self):
        """Veritabanını başlatır ve tabloları oluşturur."""
        import sqlite3
        import os
        
        try:
            # Veritabanı dizininin var olduğundan emin ol
            os.makedirs(self.db_path.parent, exist_ok=True)
            
            # SQLite bağlantısını oluştur
            self.conn = sqlite3.connect(self.db_path_str)
            self.connection = self.conn  # Alias olarak atayalım
            
            # Bağlantıyı ayarla
            self.conn.row_factory = sqlite3.Row
            
            # Tabloları oluştur
            self._create_tables()
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.critical(f"Beklenmeyen veritabanı hatası: {e}")
            raise

    def _backup_and_recreate_if_needed(self):
        """
        Bozuk veritabanını yedekler ve yeniden oluşturur.
        Veritabanı bağlantısı sırasında bir hata oluşursa, bu metot çalıştırılır.
        """
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
        """Gerekli tabloları oluşturur."""
        try:
            # Kullanıcılar tablosu - davet durumu için last_invited eklenecek
            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                message_count INTEGER DEFAULT 0,
                last_invited TIMESTAMP,
                invite_count INTEGER DEFAULT 0,
                source_group TEXT,
                is_active BOOLEAN DEFAULT 1
            )
            ''')
            
            # Grup istatistikleri tablosu - mesaj yoğunluğu için
            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS group_stats (
                group_id INTEGER PRIMARY KEY,
                group_name TEXT,
                message_count INTEGER DEFAULT 0,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                avg_messages_per_hour REAL DEFAULT 0,
                last_message_sent TIMESTAMP,
                optimal_interval INTEGER DEFAULT 60,  -- dakika cinsinden
                is_active BOOLEAN DEFAULT 1
            )
            ''')
            
            # Mevcut tablolar
            self.conn.commit()
            
        except sqlite3.Error as e:
            logger.error(f"Tablo oluşturma hatası: {str(e)}")

    def add_user(self, user_id: int, username: Optional[str] = None) -> None:
        """
        Veritabanına yeni kullanıcı ekler.
        
        Args:
            user_id: Kullanıcı ID'si
            username: Kullanıcı adı (opsiyonel)
        """
        try:
            self.cursor.execute(
                "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
                (user_id, username)
            )
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Kullanıcı eklerken hata: {str(e)}")

    def update_last_invited(self, user_id: int):
        """
        Kullanıcının son davet gönderim zamanını günceller.

        Args:
            user_id (int): Kullanıcının Telegram ID'si.
        """
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
        """
        Kullanıcıyı bloklu olarak işaretler.

        Args:
            user_id (int): Kullanıcının Telegram ID'si.
        """
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
        """
        Kullanıcıyı davet edilmiş olarak işaretler.

        Args:
            user_id (int): Kullanıcının Telegram ID'si.
        """
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
        """
        Kullanıcının davet edilip edilmediğini kontrol eder.

        Args:
            user_id (int): Kullanıcının Telegram ID'si.

        Returns:
            bool: Kullanıcı davet edilmişse True, aksi halde False.
        """
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
        """
        Kullanıcının son X saat içinde davet edilip edilmediğini kontrol eder.

        Args:
            user_id (int): Kullanıcının Telegram ID'si.
            hours (int, optional): Kontrol edilecek saat aralığı. Varsayılan: 4.

        Returns:
            bool: Kullanıcı son X saat içinde davet edilmişse True, aksi halde False.
        """
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
        """
        Davet edilecek kullanıcıları döndürür.

        Args:
            limit (int, optional): Döndürülecek maksimum kullanıcı sayısı. Varsayılan: 10.
            min_hours_between_invites (int, optional): Kullanıcıların tekrar davet edilebilmesi için geçmesi gereken minimum süre (saat). Varsayılan: 4.

        Returns:
            List[Tuple[int, str]]: Davet edilecek kullanıcıların ID'leri ve kullanıcı adları.
        """
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

    def add_error_group(self, group_id, group_title, error_reason, retry_hours=8):
        """
        Hata veren grubu veritabanına ekler.
        """
        try:
            # Sütun adlarını düzelt
            now = datetime.now()
            retry_time = now + timedelta(hours=retry_hours)
            
            with self.conn:  # self.connection değil, self.conn kullan
                self.conn.execute("""
                    INSERT OR REPLACE INTO error_groups
                    (group_id, title, error_reason, last_error_time, retry_after)
                    VALUES (?, ?, ?, ?, ?)
                """, (group_id, group_title, error_reason, now.strftime('%Y-%m-%d %H:%M:%S'), 
                      retry_time.strftime('%Y-%m-%d %H:%M:%S')))
            
            logger.debug(f"Hatalı grup eklendi: {group_title}, {retry_hours} saat sonra tekrar denenecek")
            return True
        except sqlite3.Error as e:
            logger.error(f"Hatalı grup ekleme hatası: {str(e)}")
            return False

    def get_error_groups(self) -> list:
        """
        Veritabanındaki hatalı grupları döndürür.

        Returns:
            list: Hatalı grupların listesi (group_id, group_title, error_reason, error_time, retry_after).
        """
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
        """
        Süresi dolmuş hataları temizler ve temizlenen sayısını döndürür.

        Returns:
            int: Temizlenen hatalı grup sayısı.
        """
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
        """
        Tüm hata kayıtlarını temizler ve temizlenen sayısını döndürür.

        Returns:
            int: Temizlenen hatalı grup sayısı.
        """
        try:
            with self.connection:
                cursor = self.connection.execute("DELETE FROM error_groups")
                return cursor.rowcount
        except sqlite3.Error as e:
            logger.error(f"Tüm hataları temizleme hatası: {str(e)}")
            return 0

    # Veritabanı performans ve bakım fonksiyonlarını ekle
    def optimize_database(self):
        """
        Veritabanı performans optimizasyonları yapar.
        VACUUM ve ANALYZE komutlarını kullanarak veritabanını optimize eder.
        """
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
        """
        Veritabanı istatistiklerini döndürür.

        Returns:
            dict: Veritabanı istatistikleri (toplam kullanıcı sayısı, davet edilen kullanıcı sayısı, engellenen kullanıcı sayısı, hatalı grup sayısı).
        """
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
        """
        Tüm kullanıcıları getirir.

        Returns:
            list: Tüm kullanıcıların listesi (user_id, username, invited, last_invited, first_seen, blocked, is_admin).
        """
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
        """
        Veritabanının yedeğini alır.
        Veritabanı dosyasını "backups" klasörüne kopyalar ve yedekleme işleminin başarılı olup olmadığını döndürür.
        """
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
        """
        Veritabanı bağlantısını kapatır.
        Veritabanı bağlantısını kapatır ve log kaydı oluşturur.
        """
        if self.connection:
            try:
                self.connection.close()
                logger.info("Veritabanı bağlantısı kapatıldı")
            except sqlite3.Error as e:
                logger.error(f"Veritabanı kapatma hatası: {str(e)}")

    def close_connection(self):
        """
        Veritabanı bağlantısını güvenli şekilde kapatır.
        Veritabanı bağlantısını kapatır ve log kaydı oluşturur.
        """
        try:
            if self.connection:
                self.connection.close()
                logger.info("Veritabanı bağlantısı kapatıldı")
        except Exception as e:
            logger.error(f"Veritabanı kapatma hatası: {str(e)}")

    # UserDatabase sınıfına yeni metodlar ekleyin

    def add_debug_user(self, user_id, username=None, first_name=None, last_name=None, access_level='basic'):
        """
        Debug bot kullanıcısı ekler veya günceller.

        Args:
            user_id (int): Kullanıcı ID'si
            username (str): Kullanıcı adı
            first_name (str): İsim
            last_name (str): Soyisim
            access_level (str): Erişim seviyesi ('basic', 'admin', 'developer')

        Returns:
            bool: İşlemin başarılı olup olmadığı
        """
        try:
            # Öncelikle normal kullanıcılar tablosuna ekle
            self.add_user(user_id, username, first_name, last_name)

            # Sonra debug_bot_users tablosuna ekle
            is_developer = user_id in self._get_developer_ids()
            is_superuser = username in self._get_superuser_names()

            with self.conn:
                self.conn.execute(
                    """
                    INSERT OR REPLACE INTO debug_bot_users 
                    (user_id, username, first_name, last_name, access_level, last_seen, is_developer, is_superuser) 
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?)
                    """,
                    (user_id, username, first_name, last_name, access_level, is_developer, is_superuser)
                )
            return True
        except Exception as e:
            logger.error(f"Debug kullanıcısı eklenirken hata: {e}")
            return False

    def add_premium_user(self, user_id, license_key, license_type='standard', api_id=None, api_hash=None, phone_number=None, validity_days=365):
        """
        Premium kullanıcı ekler veya günceller.

        Args:
            user_id (int): Kullanıcı ID'si
            license_key (str): Lisans anahtarı
            license_type (str): Lisans tipi ('standard', 'professional', 'enterprise')
            api_id (str): Kullanıcının API ID'si
            api_hash (str): Kullanıcının API Hash'i
            phone_number (str): Kullanıcının telefon numarası
            validity_days (int): Lisansın geçerlilik süresi (gün)

        Returns:
            bool: İşlemin başarılı olup olmadığı
        """
        try:
            import datetime
            expiration_date = datetime.datetime.now() + datetime.timedelta(days=validity_days)

            with self.conn:
                self.conn.execute(
                    """
                    INSERT OR REPLACE INTO premium_users 
                    (user_id, license_key, license_type, api_id, api_hash, phone_number, expiration_date) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (user_id, license_key, license_type, api_id, api_hash, phone_number, expiration_date)
                )
            return True
        except Exception as e:
            logger.error(f"Premium kullanıcısı eklenirken hata: {e}")
            return False

    def get_debug_users(self):
        """
        Tüm debug bot kullanıcılarını getirir.

        Returns:
            list: Kullanıcı sözlüklerinin listesi
        """
        try:
            cursor = self.conn.execute(
                """
                SELECT user_id, username, first_name, last_name, access_level, 
                       first_seen, last_seen, is_developer, is_superuser 
                FROM debug_bot_users
                """
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Debug kullanıcıları getirilirken hata: {e}")
            return []

    def get_premium_users(self):
        """
        Tüm premium kullanıcıları getirir.

        Returns:
            list: Kullanıcı sözlüklerinin listesi
        """
        try:
            cursor = self.conn.execute(
                """
                SELECT p.user_id, u.username, u.first_name, u.last_name,
                       p.license_key, p.license_type, p.api_id, p.api_hash, 
                       p.phone_number, p.activation_date, p.expiration_date, p.is_active
                FROM premium_users p
                JOIN users u ON p.user_id = u.user_id
                """
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Premium kullanıcıları getirilirken hata: {e}")
            return []

    def _get_developer_ids(self):
        """
        Geliştirici ID'lerini çevre değişkeninden alır.

        Returns:
            list: Geliştirici ID'lerinin listesi
        """
        import os
        dev_ids = os.environ.get('DEVELOPER_IDS', '')
        return [int(id.strip()) for id in dev_ids.split(',') if id.strip().isdigit()]

    def _get_superuser_names(self):
        """
        Süper kullanıcı adlarını çevre değişkeninden alır.

        Returns:
            list: Süper kullanıcı adlarının listesi
        """
        import os
        superusers = os.environ.get('SUPER_USERS', '')
        return [name.strip() for name in superusers.split(',') if name.strip()]

    def add_or_update_user(self, user_data: Dict[str, Any]) -> None:
        """
        Kullanıcı bilgilerini ekler veya günceller.
        
        Args:
            user_data: Kullanıcı bilgilerini içeren sözlük
                - user_id: Kullanıcı ID'si
                - username: Kullanıcı adı (opsiyonel)
                - first_name: Kullanıcının adı (opsiyonel)
                - last_name: Kullanıcının soyadı (opsiyonel)
        """
        try:
            user_id = user_data.get('user_id')
            username = user_data.get('username')
            first_name = user_data.get('first_name')
            last_name = user_data.get('last_name')
            
            if not user_id:
                logger.warning("Kullanıcı ID'si olmadan kullanıcı eklenemez")
                return
                
            self.cursor.execute("""
                INSERT INTO users (user_id, username, first_name, last_name)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = COALESCE(excluded.username, users.username),
                    first_name = COALESCE(excluded.first_name, users.first_name),
                    last_name = COALESCE(excluded.last_name, users.last_name),
                    last_activity = CURRENT_TIMESTAMP,
                    message_count = users.message_count + 1
            """, (user_id, username, first_name, last_name))
            
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Kullanıcı eklerken/güncellerken hata: {str(e)}")

    def get_users_to_invite(self, limit=10, min_hours_between_invites=6):
        """
        Davet edilmemiş veya belirli süreden önce davet edilmiş kullanıcıları getirir.
        
        Args:
            limit: Maksimum kullanıcı sayısı
            min_hours_between_invites: İki davet arasındaki minimum saat
            
        Returns:
            list: (user_id, username) içeren tuple listesi
        """
        try:
            now = datetime.now()
            min_time = now - timedelta(hours=min_hours_between_invites)
            
            self.cursor.execute("""
            SELECT user_id, username FROM users
            WHERE last_invited IS NULL 
               OR last_invited < ?
            LIMIT ?
            """, (min_time.strftime('%Y-%m-%d %H:%M:%S'), limit))
            
            return [(row[0], row[1]) for row in self.cursor.fetchall()]
            
        except sqlite3.Error as e:
            logger.error(f"Kullanıcı listeleme hatası: {str(e)}")
            return []

    def mark_user_invited(self, user_id):
        """
        Kullanıcıya davet gönderildiğini işaretler.
        
        Args:
            user_id: Kullanıcı ID'si
        """
        try:
            now = datetime.now()
            self.cursor.execute("""
            UPDATE users
            SET last_invited = ?,
                invite_count = invite_count + 1
            WHERE user_id = ?
            """, (now.strftime('%Y-%m-%d %H:%M:%S'), user_id))
            
            self.conn.commit()
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Kullanıcı davet işaretleme hatası: {str(e)}")
            return False

    def get_users_to_invite(self, limit=10, min_hours_between_invites=4, max_invites=3):
        """
        Davet edilmemiş veya belirli süreden önce davet edilmiş kullanıcıları getirir.
        
        Args:
            limit: Maksimum kullanıcı sayısı
            min_hours_between_invites: İki davet arasındaki minimum saat
            max_invites: Maksimum davet sayısı
            
        Returns:
            list: (user_id, username) içeren tuple listesi
        """
        try:
            now = datetime.now()
            min_time = now - timedelta(hours=min_hours_between_invites)
            
            self.cursor.execute("""
            SELECT user_id, username FROM users
            WHERE (last_invited IS NULL OR last_invited < ?)
                AND invite_count < ?
                AND is_active = 1
            ORDER BY 
                CASE WHEN last_invited IS NULL THEN 0 ELSE 1 END,
                last_activity DESC
            LIMIT ?
            """, (min_time.strftime('%Y-%m-%d %H:%M:%S'), max_invites, limit))
            
            return [(row[0], row[1]) for row in self.cursor.fetchall()]
            
        except sqlite3.Error as e:
            logger.error(f"Kullanıcı listeleme hatası: {str(e)}")
            return []

    def update_user_activity(self, user_id):
        """
        Kullanıcının son aktivite zamanını günceller.
        
        Args:
            user_id: Kullanıcı ID'si
        
        Returns:
            bool: İşlem başarılı ise True
        """
        try:
            now = datetime.now()
            self.cursor.execute("""
            UPDATE users
            SET last_activity = ?,
                message_count = message_count + 1
            WHERE user_id = ?
            """, (now.strftime('%Y-%m-%d %H:%M:%S'), user_id))
            
            self.conn.commit()
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Kullanıcı aktivite güncellemesi hatası: {str(e)}")
            return False

    # Grup istatistikleri için yeni metodlar:

    def update_group_stats(self, group_id, group_name=None, increment_message=False):
        """
        Grup istatistiklerini günceller.
        
        Args:
            group_id: Grup ID'si
            group_name: Grup adı (opsiyonel)
            increment_message: Mesaj sayısını artır (True/False)
        
        Returns:
            bool: İşlem başarılı ise True
        """
        try:
            now = datetime.now()
            
            # Grup var mı kontrol et
            self.cursor.execute("SELECT * FROM group_stats WHERE group_id = ?", (group_id,))
            group = self.cursor.fetchone()
            
            if group:
                # Mevcut grubu güncelle
                if increment_message:
                    self.cursor.execute("""
                    UPDATE group_stats
                    SET message_count = message_count + 1,
                        last_activity = ?
                    WHERE group_id = ?
                    """, (now.strftime('%Y-%m-%d %H:%M:%S'), group_id))
                elif group_name:
                    self.cursor.execute("""
                    UPDATE group_stats
                    SET group_name = ?
                    WHERE group_id = ?
                    """, (group_name, group_id))
            else:
                # Yeni grup ekle
                self.cursor.execute("""
                INSERT INTO group_stats (group_id, group_name, message_count, last_activity)
                VALUES (?, ?, ?, ?)
                """, (group_id, group_name, 1 if increment_message else 0, now.strftime('%Y-%m-%d %H:%M:%S')))
            
            self.conn.commit()
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Grup istatistikleri güncelleme hatası: {str(e)}")
            return False

    def calculate_group_message_frequency(self):
        """
        Grup mesaj sıklığını hesaplar ve optimal mesaj gönderim aralığını günceller.
        
        Returns:
            dict: {group_id: optimal_interval} şeklinde sözlük
        """
        try:
            now = datetime.now()
            one_week_ago = now - timedelta(days=7)
            
            self.cursor.execute("""
            SELECT 
                group_id,
                message_count,
                last_activity,
                (julianday(?) - julianday(last_activity)) * 24 as hours_since_activity
            FROM group_stats
            WHERE last_activity > ?
            """, (now.strftime('%Y-%m-%d %H:%M:%S'), one_week_ago.strftime('%Y-%m-%d %H:%M:%S')))
            
            results = self.cursor.fetchall()
            optimal_intervals = {}
            
            for group_id, message_count, last_activity, hours_since_activity in results:
                # Mesaj yoğunluk hesaplaması
                if hours_since_activity > 0:
                    messages_per_hour = message_count / max(hours_since_activity, 1)
                    
                    # Mesaj sıklığına göre optimal aralık hesaplaması
                    # Çok hızlı grup: 30-60dk, orta: 60-120dk, yavaş: 120-240dk
                    if messages_per_hour > 50:
                        optimal_interval = 30  # Çok aktif grup: 30 dakikada bir
                    elif messages_per_hour > 20:
                        optimal_interval = 60  # Aktif grup: 1 saatte bir
                    elif messages_per_hour > 5:
                        optimal_interval = 120  # Orta yoğunluk: 2 saatte bir
                    else:
                        optimal_interval = 240  # Düşük aktivite: 4 saatte bir
                    
                    # Veritabanını güncelle
                    self.cursor.execute("""
                    UPDATE group_stats
                    SET avg_messages_per_hour = ?,
                        optimal_interval = ?
                    WHERE group_id = ?
                    """, (messages_per_hour, optimal_interval, group_id))
                    
                    optimal_intervals[group_id] = optimal_interval
            
            self.conn.commit()
            return optimal_intervals
            
        except sqlite3.Error as e:
            logger.error(f"Grup mesaj frekansı hesaplama hatası: {str(e)}")
            return {}

    def get_group_optimal_interval(self, group_id):
        """
        Bir grup için optimal mesaj gönderim aralığını döndürür.
        
        Args:
            group_id: Grup ID'si
        
        Returns:
            int: Dakika cinsinden optimal aralık (varsayılan: 60)
        """
        try:
            self.cursor.execute("""
            SELECT optimal_interval FROM group_stats
            WHERE group_id = ?
            """, (group_id,))
            
            result = self.cursor.fetchone()
            return result[0] if result else 60
            
        except sqlite3.Error as e:
            logger.error(f"Grup aralığı sorgulama hatası: {str(e)}")
            return 60

    # mark_message_sent metodunu ekleyin:

    def mark_message_sent(self, group_id, sent_time=None):
        """
        Bir gruba mesaj gönderildiğini işaretler.
        
        Args:
            group_id: Grup ID'si
            sent_time: Gönderim zamanı (varsayılan: şu an)
        
        Returns:
            bool: İşlem başarılı ise True
        """
        try:
            if sent_time is None:
                sent_time = datetime.now()
            
            self.cursor.execute("""
            UPDATE group_stats
            SET last_message_sent = ?
            WHERE group_id = ?
            """, (sent_time.strftime('%Y-%m-%d %H:%M:%S'), group_id))
            
            # Grup yoksa ekle
            if self.cursor.rowcount == 0:
                self.cursor.execute("""
                INSERT INTO group_stats (group_id, last_message_sent)
                VALUES (?, ?)
                """, (group_id, sent_time.strftime('%Y-%m-%d %H:%M:%S')))
            
            self.conn.commit()
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Mesaj gönderim kaydı hatası: {str(e)}")
            return False

    # UserDatabase sınıfına yeni yardımcı metodlar ekleyin:

    def get_user_count(self):
        """Toplam kullanıcı sayısını döndürür."""
        try:
            self.cursor.execute("SELECT COUNT(*) FROM users")
            return self.cursor.fetchone()[0]
        except sqlite3.Error as e:
            logger.error(f"Kullanıcı sayımı hatası: {str(e)}")
            return 0

    def get_invited_user_count(self):
        """Davet gönderilen kullanıcı sayısını döndürür."""
        try:
            self.cursor.execute("SELECT COUNT(*) FROM users WHERE last_invited IS NOT NULL")
            return self.cursor.fetchone()[0]
        except sqlite3.Error as e:
            logger.error(f"Davet sayımı hatası: {str(e)}")
            return 0
        
    def get_recent_users(self, limit=10):
        """En son eklenen kullanıcıları döndürür."""
        try:
            self.cursor.execute("""
            SELECT user_id, username, first_name, last_name, join_date 
            FROM users 
            ORDER BY join_date DESC 
            LIMIT ?
            """, (limit,))
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            logger.error(f"Yeni kullanıcı listesi hatası: {str(e)}")
            return []