import psycopg2
from psycopg2.extras import RealDictCursor
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class PgDatabase:
    def __init__(self, connection_string):
        self.connection_string = connection_string
        self.conn = None
        self.cursor = None
    
    def connect(self):
        """Veritabanına bağlanır"""
        try:
            self.conn = psycopg2.connect(self.connection_string)
            self.conn.autocommit = False  # Otomatik commit kapalı
            self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)
            
            # Test sorgusu çalıştır
            self.cursor.execute("SELECT 1")
            logger.info("PostgreSQL veritabanına bağlantı başarılı")
            return True
        except Exception as e:
            logger.error(f"PostgreSQL bağlantı hatası: {str(e)}")
            return False
    
    def setup_database(self):
        """Veritabanını hazırlar"""
        try:
            # groups tablosunu oluştur
            self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS groups (
                group_id BIGINT PRIMARY KEY,
                name TEXT,
                join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_message TIMESTAMP,
                message_count INTEGER DEFAULT 0,
                member_count INTEGER DEFAULT 0,
                error_count INTEGER DEFAULT 0, 
                last_error TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                permanent_error BOOLEAN DEFAULT FALSE,
                is_target BOOLEAN DEFAULT TRUE,
                retry_after TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            # users tablosunu oluştur
            self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                source_group TEXT,
                join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_invited TIMESTAMP,
                invite_count INTEGER DEFAULT 0,
                is_bot BOOLEAN DEFAULT FALSE,
                is_replied BOOLEAN DEFAULT FALSE,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            # user_groups tablosunu oluştur
            self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_groups (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                group_id BIGINT REFERENCES groups(group_id) ON DELETE CASCADE,
                join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, group_id)
            )
            """)
            
            self.conn.commit()
            logger.info("PostgreSQL tabloları başarıyla oluşturuldu")
            return True
        except Exception as e:
            self.conn.rollback()
            logger.error(f"PostgreSQL tablo oluşturma hatası: {str(e)}")
            return False
    
    # Database sınıfının diğer metotlarını aynı imza ile implemente edin:
    
    async def get_target_groups(self):
        """Tüm hedef grupları getirir"""
        try:
            self.cursor.execute("SELECT * FROM groups WHERE is_target = TRUE")
            groups = self.cursor.fetchall()
            return groups
        except Exception as e:
            logger.error(f"Hedef grupları getirme hatası: {str(e)}")
            return []
    
    async def add_group(self, group_id, title, username=None, member_count=0, is_active=True):
        """
        Grubu veritabanına ekler veya günceller
        
        Args:
            group_id (int): Grup ID
            title (str): Grup adı
            username (str, optional): Grup kullanıcı adı
            member_count (int, optional): Grup üye sayısı
            is_active (bool, optional): Grup aktif mi
        
        Returns:
            bool: İşlem başarılıysa True
        """
        try:
            # Önce grubun var olup olmadığını kontrol et
            self.cursor.execute('SELECT 1 FROM groups WHERE group_id = %s', (group_id,))
            exists = self.cursor.fetchone()
            
            now = datetime.now()
            
            if exists:
                # Mevcut grup kaydını güncelle
                self.cursor.execute('''
                    UPDATE groups
                    SET name = %s, 
                        member_count = %s, 
                        is_active = %s, 
                        updated_at = %s
                    WHERE group_id = %s
                ''', (title, member_count, is_active, now, group_id))
            else:
                # Yeni grup ekle
                self.cursor.execute('''
                    INSERT INTO groups 
                    (group_id, name, join_date, member_count, is_active, is_target, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ''', (
                    group_id, title, now, member_count, is_active, True, now, now
                ))
            
            self.conn.commit()
            return True
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Grup eklenirken PostgreSQL hatası: {str(e)}")
            return False
    
    async def add_target_group(self, group_id, name, member_count=0):
        """Hedef grubu veritabanına ekler"""
        return await self.add_group(group_id, name, None, member_count, True)

    async def update_group_stats(self, group_id, last_message=None, message_count=1):
        """Grup istatistiklerini günceller"""
        try:
            self.cursor.execute('''
                UPDATE groups 
                SET last_message = %s, 
                    message_count = message_count + %s,
                    updated_at = %s
                WHERE group_id = %s
            ''', (last_message or datetime.now(), message_count, datetime.now(), group_id))
            self.conn.commit()
            return True
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Grup istatistikleri güncellenirken hata: {str(e)}")
            return False

    async def mark_group_inactive(self, group_id, error_message=None, retry_time=None, permanent=False):
        """Grubu devre dışı bırakır"""
        try:
            # Varsayılan retry_time şimdiden 24 saat sonrası
            if retry_time is None and not permanent:
                retry_time = datetime.now() + timedelta(hours=24)
            
            # Kalıcı olarak devre dışı bırakılacaksa retry_time NULL olmalı
            permanent_flag = permanent
            
            self.cursor.execute('''
                UPDATE groups 
                SET is_active = FALSE,
                    error_count = error_count + 1,
                    last_error = %s,
                    retry_after = %s,
                    permanent_error = %s,
                    updated_at = %s
                WHERE group_id = %s
            ''', (error_message or "Bilinmeyen hata", retry_time, permanent_flag, datetime.now(), group_id))
            
            self.conn.commit()
            
            if permanent:
                logger.warning(f"Grup {group_id} kalıcı olarak devre dışı bırakıldı: {error_message}")
            else:
                logger.info(f"Grup {group_id} şu tarihe kadar devre dışı bırakıldı: {retry_time}")
            
            return True
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Grup devre dışı bırakılırken hata: {str(e)}")
            return False

    async def fetchone(self, query, params=None):
        """Tek bir satır sonuç döndürür"""
        try:
            self.cursor.execute(query, params or ())
            return self.cursor.fetchone()
        except Exception as e:
            logger.error(f"Sorgu hatası (fetchone): {str(e)}")
            return None

    async def fetchall(self, query, params=None):
        """Tüm sonuçları döndürür"""
        try:
            self.cursor.execute(query, params or ())
            return self.cursor.fetchall()
        except Exception as e:
            logger.error(f"Sorgu hatası (fetchall): {str(e)}")
            return []

    async def execute(self, query, params=None):
        """Sorgu çalıştırır ve commit yapar"""
        try:
            self.cursor.execute(query, params or ())
            self.conn.commit()
            return True
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Sorgu çalıştırma hatası: {str(e)}")
            return False

    async def execute_query(self, query, params=None):
        """
        SQL sorgusu çalıştırır ve sonuçları döndürür.
        main.py dosyasındaki get_or_create_session_string fonksiyonu için eklendi.
        
        Args:
            query: SQL sorgusu
            params: Parametreler
            
        Returns:
            list: Sorgu sonuçları
        """
        try:
            self.cursor.execute(query, params or ())
            
            # SQL komutunun türünü kontrol et
            if query.strip().upper().startswith(('SELECT', 'SHOW', 'DESCRIBE')):
                result = self.cursor.fetchall()
                self.conn.commit()
                return result
            else:
                self.conn.commit()
                return True
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Sorgu çalıştırma hatası (execute_query): {str(e)}")
            raise  # Hatanın üst katmanlara iletilmesi gerekiyor

    async def get_active_groups(self):
        """Aktif grupları getirir"""
        try:
            current_time = datetime.now()
            self.cursor.execute('''
                SELECT * FROM groups 
                WHERE is_active = TRUE 
                   OR (retry_after IS NOT NULL AND retry_after <= %s AND permanent_error = FALSE)
            ''', (current_time,))
            
            groups = self.cursor.fetchall()
            return groups
        except Exception as e:
            logger.error(f"Aktif grupları getirme hatası: {str(e)}")
            return []

    async def reactivate_group(self, group_id):
        """Grubu tekrar aktif eder"""
        try:
            self.cursor.execute('''
                UPDATE groups 
                SET is_active = TRUE,
                    retry_after = NULL,
                    updated_at = %s
                WHERE group_id = %s
            ''', (datetime.now(), group_id))
            self.conn.commit()
            logger.info(f"Grup {group_id} tekrar aktifleştirildi")
            return True
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Grup aktifleştirme hatası: {str(e)}")
            return False

    async def get_users_for_invite(self, limit=50, cooldown_hours=24):
        """
        Davet gönderilecek kullanıcıları getirir.
        
        Args:
            limit: Maksimum kullanıcı sayısı
            cooldown_hours: Son davet sonrası bekleme süresi (saat)
        
        Returns:
            list: Kullanıcı listesi
        """
        try:
            cooldown_time = datetime.now() - timedelta(hours=cooldown_hours)
            
            self.cursor.execute('''
                SELECT * FROM users 
                WHERE (last_invited IS NULL OR last_invited < %s)
                AND is_bot = FALSE
                AND status = 'active'
                ORDER BY RANDOM()
                LIMIT %s
            ''', (cooldown_time, limit))
            
            return self.cursor.fetchall()
        except Exception as e:
            logger.error(f"Davet edilecek kullanıcıları getirme hatası: {str(e)}")
            return []

    async def mark_user_invited(self, user_id):
        """
        Kullanıcıyı davet edildi olarak işaretler
        
        Args:
            user_id: Kullanıcı ID
        
        Returns:
            bool: İşlem başarılıysa True
        """
        try:
            now = datetime.now()
            
            self.cursor.execute('''
                UPDATE users
                SET last_invited = %s,
                    invite_count = invite_count + 1,
                    updated_at = %s
                WHERE user_id = %s
            ''', (now, now, user_id))
            
            self.conn.commit()
            return True
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Kullanıcı davet işaretleme hatası: {str(e)}")
            return False

    async def add_user_if_not_exists(self, user_id, username=None, first_name=None, last_name=None, source_group=None, is_bot=False):
        """Kullanıcıyı veritabanına ekler (yoksa)"""
        try:
            # Kullanıcının var olup olmadığını kontrol et
            self.cursor.execute('SELECT 1 FROM users WHERE user_id = %s', (user_id,))
            exists = self.cursor.fetchone()
            
            now = datetime.now()
            
            if exists:
                # Sadece mevcut kullanıcıyı güncelle
                self.cursor.execute('''
                    UPDATE users
                    SET username = COALESCE(%s, username),
                        first_name = COALESCE(%s, first_name),
                        last_name = COALESCE(%s, last_name),
                        source_group = COALESCE(%s, source_group),
                        is_bot = %s,
                        updated_at = %s
                    WHERE user_id = %s
                ''', (username, first_name, last_name, source_group, is_bot, now, user_id))
            else:
                # Yeni kullanıcı ekle
                self.cursor.execute('''
                    INSERT INTO users
                    (user_id, username, first_name, last_name, source_group, join_date, is_bot, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ''', (user_id, username, first_name, last_name, source_group, now, is_bot, now, now))
            
            self.conn.commit()
            return True
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Kullanıcı ekleme hatası: {str(e)}")
            return False

    async def get_user(self, user_id):
        """
        Kullanıcı bilgilerini getirir
        
        Args:
            user_id: Kullanıcı ID
            
        Returns:
            dict: Kullanıcı bilgileri
        """
        try:
            self.cursor.execute('SELECT * FROM users WHERE user_id = %s', (user_id,))
            return self.cursor.fetchone()
        except Exception as e:
            logger.error(f"Kullanıcı getirme hatası: {str(e)}")
            return None

    async def reset_invite_cooldowns(self):
        """
        Davet bekleme sürelerini sıfırlar (acil davet durumunda kullanılır)
        """
        try:
            # 14 günden eski davet edilmiş kullanıcıları sıfırla
            old_date = datetime.now() - timedelta(days=14)
            
            self.cursor.execute('''
                UPDATE users
                SET last_invited = NULL
                WHERE last_invited < %s
            ''', (old_date,))
            
            count = self.cursor.rowcount
            self.conn.commit()
            
            return count
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Davet sürelerini sıfırlama hatası: {str(e)}")
            return 0

    async def get_all_groups(self):
        """
        Tüm grupları getirir
        """
        try:
            self.cursor.execute("SELECT * FROM groups")
            return self.cursor.fetchall()
        except Exception as e:
            logger.error(f"Tüm grupları getirme hatası: {str(e)}")
            return []

    async def get_group_by_id(self, group_id):
        """
        ID'ye göre grup getirir
        """
        try:
            self.cursor.execute("SELECT * FROM groups WHERE group_id = %s", (group_id,))
            return self.cursor.fetchone()
        except Exception as e:
            logger.error(f"Grup getirme hatası: {str(e)}")
            return None

    async def close(self):
        """Veritabanı bağlantısını kapatır"""
        try:
            if self.conn:
                if self.cursor:
                    self.cursor.close()
                self.conn.close()
                logger.info("PostgreSQL bağlantısı kapatıldı")
        except Exception as e:
            logger.error(f"Veritabanı kapatma hatası: {str(e)}")

    # Kalan metotları da ekleyin...
