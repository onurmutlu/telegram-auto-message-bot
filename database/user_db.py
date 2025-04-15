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
import logging
from datetime import datetime, timedelta
from pathlib import Path
import time
import shutil
import json
from typing import Optional, Dict, List, Any, Union, Tuple
import asyncio
import functools
import aiosqlite
import sqlite3
import threading

from database.db_connection import DatabaseConnectionManager

logger = logging.getLogger(__name__)

class UserDatabase:
    def __init__(self, db_connection_manager: DatabaseConnectionManager = None, db_path: str = None):
        """
        UserDatabase sınıfının başlatıcısı.
        
        Args:
            db_connection_manager: Veritabanı bağlantı yöneticisi
            db_path: Veritabanı dosya yolu (eski tip bağlantı için)
        """
        if db_connection_manager:
            # Yeni tip bağlantı - bağlantı havuzu kullanılır
            self.db_connection_manager = db_connection_manager
            self.db_path = None  # Doğrudan yolu saklamıyoruz
            self.conn = None  # Bağlantıyı havuzdan alacağız
            self.cursor = None  # Havuz bağlantısı ile alınacak
            self._use_connection_pool = True
        elif db_path:
            # Eski tip doğrudan bağlantı
            self.db_connection_manager = None
            self.db_path = db_path
            self.conn = None
            self.cursor = None
            self._use_connection_pool = False
        else:
            raise ValueError("Bir bağlantı yöneticisi veya dosya yolu vermelisiniz")
            
        # Thread güvenliği ve kilit mekanizması
        self.lock = threading.RLock()
        self.max_lock_retries = 10
        self.initial_backoff = 0.1  # 100ms
        self.max_backoff = 5.0  # 5 saniye
        
        # Kilit problem izleme için
        self.lock_retry_count = 0
        self.last_lock_error_time = None
        
        # Bağlantı başlatma
        # NOT: __init__ metodunda async metod çağırılmaz
        # Bağlantı ana programdan sonra kurulacak

    async def connect(self):
        """Veritabanına bağlanır"""
        try:
            import sqlite3
            import os
            
            # Veritabanı dizininin var olduğundan emin ol
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            
            # Kilit ile güvenli erişim
            with self.lock:
                # Yeni bir bağlantı kurulmadan önce eski bağlantıyı kapat
                if self.conn:
                    try:
                        self.conn.close()
                        logger.debug("Önceki veritabanı bağlantısı kapatıldı")
                    except Exception as e:
                        logger.warning(f"Önceki bağlantı kapatma hatası: {str(e)}")
                
                # Bağlantı kur
                self.conn = sqlite3.connect(
                    self.db_path, 
                    timeout=60,  # 60 saniye bağlantı zaman aşımı (arttırıldı)
                    isolation_level=None,  # Otomatik commit modu (autocommit)
                    check_same_thread=False  # Çoklu thread erişimi için
                )
                self.conn.row_factory = sqlite3.Row
                
                # SQLite performans ayarları
                self.conn.execute("PRAGMA journal_mode=WAL")
                self.conn.execute("PRAGMA busy_timeout=30000")  # 30 saniye timeout (arttırıldı)
                self.conn.execute("PRAGMA synchronous=NORMAL")  # Daha az disk senkronizasyonu
                self.conn.execute("PRAGMA cache_size=10000")  # Daha büyük cache
                self.conn.execute("PRAGMA temp_store=MEMORY")  # Geçici tabloları bellekte tut
                
                self.cursor = self.conn.cursor()
                
                # Test sorgusu çalıştır
                self.cursor.execute("SELECT 1")
            
            logger.info(f"Veritabanı bağlantısı başarılı: {self.db_path}")
            return True
        except Exception as e:
            logger.error(f"Veritabanı bağlantı hatası: {str(e)}")
            self.conn = None  # Hata durumunda bağlantıyı sıfırla
            self.cursor = None
            return False

    async def close(self):
        """Veritabanı bağlantısını kapatır"""
        try:
            if self.conn:
                self.conn.close()
                logger.info("Veritabanı bağlantısı kapatıldı")
            return True
        except Exception as e:
            logger.error(f"Veritabanı bağlantısı kapatma hatası: {str(e)}")
            return False

    async def reconnect(self):
        """Veritabanı bağlantısını yeniden kurar"""
        await self.close()
        return await self.connect()

    async def execute(self, query, params=None):
        """Asenkron olarak bir SQL sorgusu çalıştırır."""
        try:
            cursor = self.cursor.execute(query, params or ())
            self.conn.commit()
            return cursor
        except Exception as e:
            logger.error(f"SQL sorgusu çalıştırılırken hata: {str(e)}")
            raise

    async def fetchall(self, query, params=None):
        """Asenkron olarak bir SQL sorgusundan tüm sonuçları döndürür."""
        try:
            cursor = self.cursor.execute(query, params or ())
            rows = cursor.fetchall()
            return rows
        except Exception as e:
            logger.error(f"SQL sorgusu çalıştırılırken hata: {str(e)}")
            raise

    async def fetchone(self, query, params=None):
        """Asenkron olarak bir SQL sorgusundan tek bir sonucu döndürür."""
        try:
            cursor = self.cursor.execute(query, params or ())
            row = cursor.fetchone()
            return row
        except Exception as e:
            logger.error(f"SQL sorgusu çalıştırılırken hata: {str(e)}")
            raise

    async def create_tables(self):
        """Veritabanı tablolarını oluşturur."""
        try:
            # Kullanıcılar tablosu
            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                user_id INTEGER UNIQUE,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                is_bot INTEGER DEFAULT 0,
                language_code TEXT,
                is_premium INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                is_admin INTEGER DEFAULT 0,
                quota INTEGER DEFAULT 0,
                join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP,
                last_message TEXT
            )
            ''')
            
            # Gruplar tablosu
            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY,
                group_id INTEGER UNIQUE,
                chat_id INTEGER UNIQUE,
                title TEXT,
                username TEXT,
                description TEXT,
                member_count INTEGER DEFAULT 0,
                participants_count INTEGER DEFAULT 0, 
                last_message TEXT,
                message_count INTEGER DEFAULT 0,
                error_count INTEGER DEFAULT 0,
                last_error TEXT,
                retry_after INTEGER DEFAULT 0,
                permanent_error INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                is_target INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            )
            ''')
            
            # Spam mesajları tablosu
            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS spam_messages (
                id INTEGER PRIMARY KEY,
                message_type TEXT,
                content TEXT,
                media_file TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            # Ayarlar tablosu
            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            )
            ''')
            
            # Kullanıcı aktivite tablosu
            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_activity (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                activity_type TEXT,
                data TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
            ''')
            
            # Groups tablosu sütunları
            groups_columns = {
                "error_count": "INTEGER DEFAULT 0",
                "last_error": "TEXT",
                "retry_after": "INTEGER DEFAULT 0",
                "permanent_error": "INTEGER DEFAULT 0",
                "is_target": "INTEGER DEFAULT 0",
                "updated_at": "TIMESTAMP"
            }
            
            self.cursor.execute("PRAGMA table_info(groups)")
            existing_columns = [col[1] for col in self.cursor.fetchall()]
            
            for column_name, column_type in groups_columns.items():
                if column_name not in existing_columns:
                    try:
                        logger.info(f"groups tablosuna {column_name} sütunu ekleniyor")
                        self.cursor.execute(f"ALTER TABLE groups ADD COLUMN {column_name} {column_type}")
                    except Exception as e:
                        logger.error(f"Sütun ekleme hatası: {str(e)}")
            
            # Settings tablosu sütunları
            settings_columns = {
                "updated_at": "TIMESTAMP"
            }
            
            self.cursor.execute("PRAGMA table_info(settings)")
            existing_columns = [col[1] for col in self.cursor.fetchall()]
            
            for column_name, column_type in settings_columns.items():
                if column_name not in existing_columns:
                    try:
                        logger.info(f"settings tablosuna {column_name} sütunu ekleniyor")
                        self.cursor.execute(f"ALTER TABLE settings ADD COLUMN {column_name} {column_type}")
                    except Exception as e:
                        logger.error(f"Sütun ekleme hatası: {str(e)}")
            
            self.conn.commit()
            logger.info("Veritabanı tabloları başarıyla oluşturuldu.")
        except Exception as e:
            logger.error(f"Tablo oluşturma hatası: {str(e)}")
            self.conn.rollback()
            
    async def create_user_profile_tables(self):
        """Kullanıcı profil tablolarını oluşturur"""
        try:
            # Kullanıcı profilleri tablosu
            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id INTEGER PRIMARY KEY,
                interests TEXT,
                bio TEXT,
                age INTEGER,
                gender TEXT,
                location TEXT,
                last_updated TIMESTAMP
            )
            ''')
            
            # Kullanıcı etkileşimleri tablosu
            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                interaction_type TEXT,
                target_id INTEGER,
                timestamp TIMESTAMP,
                details TEXT
            )
            ''')
            
            self.conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Profil tablolarını oluştururken hata: {str(e)}")
            raise

    async def get_all_groups(self):
        """
        Tüm grupları getirir.
        
        Returns:
            List[Dict]: Grup listesi
        """
        try:
            query = "SELECT * FROM groups"
            async with self.conn.execute(query) as cursor:
                rows = await cursor.fetchall()
                
                # Sonuçları sözlük listesine dönüştür
                result = []
                for row in rows:
                    result.append({
                        'chat_id': row[0],
                        'title': row[1],
                        'join_date': row[2],
                        'member_count': row[3],
                        'is_active': row[4],
                        'last_activity': row[5]
                    })
                
                return result
        except Exception as e:
            logger.error(f"Tüm grupları alma hatası: {str(e)}")
            return []

    async def get_groups(self, filter_active=False, limit=100):
        """
        Tüm grupların listesini getirir.
        
        Args:
            filter_active: True ise sadece aktif grupları getirir
            limit: Maksimum grup sayısı
            
        Returns:
            List[Dict]: Grupların listesi
        """
        try:
            # filter_active parametresine göre sorgu oluştur
            if filter_active:
                query = """
                SELECT * FROM groups
                WHERE is_active = 1
                ORDER BY last_activity DESC
                LIMIT ?
                """
            else:
                query = """
                SELECT * FROM groups
                ORDER BY last_activity DESC
                LIMIT ?
                """
            
            result = await self.fetchall(query, (limit,))
            return self._convert_rows_to_dict(result)
        except Exception as e:
            logger.error(f"Grupları getirme hatası: {str(e)}")
            return []

    async def add_group(self, group_id, title, join_date=None, member_count=0, is_active=1, last_activity=None, username=None):
        """Gruba ait bilgileri veritabanına kaydeder."""
        try:
            # Şimdiki zamanı varsayılan değer olarak kullan
            if join_date is None:
                join_date = datetime.now()
            if last_activity is None:
                last_activity = datetime.now()
                
            # Önce grup var mı kontrol et - chat_id yerine group_id kullan
            query = "SELECT group_id FROM groups WHERE group_id = ?"
            params = (group_id,)
            
            existing_group = await self.fetchone(query, params)
            
            # Tabloda username sütununun var olup olmadığını kontrol et
            columns_query = "PRAGMA table_info(groups)"
            columns = await self.fetchall(columns_query)
            has_username_column = any(col[1] == 'username' for col in columns)
            
            if existing_group:
                # Grup zaten varsa güncelle
                if has_username_column and username is not None:
                    query = """
                    UPDATE groups
                    SET title = ?, member_count = ?, is_active = ?, last_activity = ?, username = ?
                    WHERE group_id = ?
                    """
                    params = (title, member_count, is_active, last_activity, username, group_id)
                else:
                    query = """
                    UPDATE groups
                    SET title = ?, member_count = ?, is_active = ?, last_activity = ?
                    WHERE group_id = ?
                    """
                    params = (title, member_count, is_active, last_activity, group_id)
            else:
                # Grup yoksa ekle
                if has_username_column and username is not None:
                    query = """
                    INSERT INTO groups (group_id, title, join_date, member_count, is_active, last_activity, username)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """
                    params = (group_id, title, join_date, member_count, is_active, last_activity, username)
                else:
                    query = """
                    INSERT INTO groups (group_id, title, join_date, member_count, is_active, last_activity)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """
                    params = (group_id, title, join_date, member_count, is_active, last_activity)
                
            await self.execute(query, params)
            return True
        except Exception as e:
            logger.error(f"Grup eklenirken hata: {str(e)}")
            return False

    async def group_exists(self, group_id):
        """
        Bir grubun veritabanında olup olmadığını kontrol eder.
        """
        try:
            # chat_id yerine group_id kullan
            query = "SELECT 1 FROM groups WHERE group_id = ?"
            result = await self.fetchone(query, (group_id,))
            return result is not None
        except Exception as e:
            logger.error(f"Grup kontrolü hatası: {str(e)}")
            return False

    async def get_group(self, group_id):
        """
        Belirli bir grubun bilgilerini getirir.
        """
        try:
            # chat_id yerine group_id kullan
            query = "SELECT * FROM groups WHERE group_id = ?"
            result = await self.fetchone(query, (group_id,))
            return result
        except Exception as e:
            logger.error(f"Grup bilgileri alınırken hata: {str(e)}")
            return None

    async def update_group(self, group_id, **kwargs):
        """
        Grup bilgilerini günceller.
        """
        try:
            # chat_id yerine group_id kullan
            set_clauses = [f"{key} = ?" for key in kwargs.keys()]
            query = f"UPDATE groups SET {', '.join(set_clauses)} WHERE group_id = ?"
            params = list(kwargs.values()) + [group_id]
            
            await self.execute(query, params)
            return True
        except Exception as e:
            logger.error(f"Grup güncellenirken hata: {str(e)}")
            return False

    async def get_users_by_segment(self, segment_id=None):
        """
        Belirli bir segmente ait kullanıcıları getirir.
        
        Args:
            segment_id: Segment kimliği (None ise tüm segmentler)
            
        Returns:
            List: Kullanıcı bilgilerinin listesi
        """
        try:
            if segment_id is None:
                query = "SELECT id, username, first_name, last_name FROM users WHERE is_active = 1"
                params = ()
            else:
                query = """
                SELECT u.id, u.username, u.first_name, u.last_name 
                FROM users u 
                JOIN user_segments us ON u.id = us.user_id 
                WHERE us.segment_id = ? AND u.is_active = 1
                """
                params = (segment_id,)
                
            async with self.conn.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                
                result = []
                for row in rows:
                    result.append({
                        'id': row[0],
                        'username': row[1],
                        'first_name': row[2],
                        'last_name': row[3]
                    })
                
                return result
        except Exception as e:
            logger.error(f"Segment bazlı kullanıcı alma hatası: {str(e)}")
            return []

    async def log_group_error(self, chat_id, error_type, error_message, permanent=False):
        """
        Grup hatalarını kaydeder
        
        Args:
            chat_id: Grup ID
            error_type: Hata tipi (admin_required, write_forbidden, banned, etc.)
            error_message: Hata mesajı
            permanent: Kalıcı hata mı?
        """
        try:
            now = datetime.now()
            retry_days = 0
            
            # Hata tipine göre yeniden deneme süresi belirleme
            if error_type == 'admin_required':
                permanent = True  # Admin gerektiren kanallar kalıcı olarak işaretlenir
                retry_days = 30   # Uzun süre sonra tekrar kontrol edilebilir
            elif error_type == 'write_forbidden':
                retry_days = 3    # 3 gün sonra tekrar dene
            elif error_type == 'banned':
                retry_days = 7    # 7 gün sonra tekrar dene
            elif error_type == 'flood_wait':
                retry_days = 0.5  # 12 saat sonra tekrar dene
            else:
                retry_days = 1    # Varsayılan: 1 gün sonra
                
            retry_after = now + timedelta(days=retry_days)
            
            # Önce mevcut kaydı kontrol et
            query = "SELECT retry_count FROM group_errors WHERE chat_id = ?"
            async with self.conn.execute(query, (chat_id,)) as cursor:
                existing = await cursor.fetchone()
                
            if existing:
                # Mevcut kaydı güncelle
                query = '''
                UPDATE group_errors 
                SET error_type = ?, error_message = ?, last_occurred = ?, 
                    retry_after = ?, retry_count = retry_count + 1, 
                    is_permanent = ?
                WHERE chat_id = ?
                '''
                params = (error_type, error_message, now, retry_after, permanent, chat_id)
            else:
                # Yeni kayıt ekle
                query = '''
                INSERT INTO group_errors 
                (chat_id, error_type, error_message, first_occurred, last_occurred, 
                 retry_after, retry_count, is_permanent)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?)
                '''
                params = (chat_id, error_type, error_message, now, now, retry_after, permanent)
                
            await self.conn.execute(query, params)
            await self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Grup hatası kaydedilirken hata: {str(e)}")
            return False

    async def can_send_to_group(self, chat_id):
        """
        Bir gruba mesaj gönderip gönderemeyeceğimizi kontrol eder
        
        Args:
            chat_id: Kontrol edilecek grup ID
            
        Returns:
            bool: Mesaj gönderilebilirse True
        """
        try:
            now = datetime.now()
            query = '''
            SELECT is_permanent, retry_after FROM group_errors 
            WHERE chat_id = ?
            '''
            
            async with self.conn.execute(query, (chat_id,)) as cursor:
                row = await cursor.fetchone()
                
            if not row:
                return True  # Hata kaydı yok, gönderebilir
                
            is_permanent, retry_after = row
            
            if is_permanent:
                return False  # Kalıcı hata, gönderemez
                
            # Yeniden deneme zamanı gelmiş mi?
            if retry_after and datetime.fromisoformat(retry_after) > now:
                return False  # Daha bekleme süresi dolmamış
                
            return True  # Yeniden deneme zamanı gelmiş
            
        except Exception as e:
            logger.error(f"Grup kontrol hatası: {str(e)}")
            return True  # Hata durumunda varsayılan olarak göndermeyi dene

    async def get_token_usage(self, date):
        """Belirli bir günün token kullanımını getirir."""
        try:
            query = "SELECT tokens FROM token_usage WHERE date = ?"
            result = await self.fetchone(query, (date.isoformat(),))
            return {"tokens": result[0]} if result else None
        except Exception as e:
            logger.error(f"Token kullanımı alınamadı: {str(e)}")
            return None

    async def update_token_usage(self, date, tokens):
        """Token kullanımını günceller."""
        try:
            # Eğer bugün için bir kayıt varsa güncelle, yoksa oluştur
            query = """
            INSERT INTO token_usage (date, tokens)
            VALUES (?, ?)
            ON CONFLICT(date) DO UPDATE SET
            tokens = token_usage.tokens + ?
            """
            await self.execute(query, (date.isoformat(), tokens, tokens))
        except Exception as e:
            logger.error(f"Token kullanımı güncellenirken hata: {str(e)}")

    async def save_gpt_stats(self, stats):
        """GPT istatistiklerini kaydeder."""
        try:
            query = """
            INSERT INTO gpt_stats (date, total_requests, total_tokens)
            VALUES (?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
            total_requests = ?, total_tokens = ?
            """
            today = datetime.now().date().isoformat()
            params = (
                today, 
                stats["total_requests"],
                stats["total_tokens"],
                stats["total_requests"],
                stats["total_tokens"]
            )
            await self.execute(query, params)
        except Exception as e:
            logger.error(f"GPT istatistikleri kaydedilirken hata: {str(e)}")

    async def get_user_count(self):
        """
        Veritabanındaki toplam kullanıcı sayısını döndürür.
        
        Returns:
            int: Toplam kullanıcı sayısı
        """
        try:
            query = "SELECT COUNT(*) FROM users"
            row = await self.fetchone(query)
            return row[0] if row else 0
        except Exception as e:
            logger.error(f"Kullanıcı sayısı alınırken hata: {str(e)}")
            return 0

    async def get_users_for_invite(self, limit=50, cooldown_minutes=30):
        """Davet edilebilecek kullanıcıları getirir."""
        try:
            # Cooldown süresini hesapla
            cooldown_time = datetime.now() - timedelta(minutes=cooldown_minutes)
            cooldown_str = cooldown_time.isoformat()
            
            # Daha basit sorgu - NULLS FIRST olmadan
            query = """
            SELECT id, username, first_name, last_name, last_invited
            FROM users
            WHERE (last_invited IS NULL OR last_invited < ?)
            AND is_bot = 0
            ORDER BY 
                CASE WHEN last_invited IS NULL THEN 0 ELSE 1 END,
                last_invited ASC
            LIMIT ?
            """
            
            # Sorguyu çalıştır
            result = await self.fetchall(query, (cooldown_str, limit))
            
            # Debug için kullanıcı sayısını logla
            logger.info(f"Davet için uygun {len(result)} kullanıcı bulundu.")
            
            # Sonuçları işle
            users = []
            for row in result:
                users.append({
                    'id': row[0],
                    'username': row[1],
                    'first_name': row[2],
                    'last_name': row[3],
                    'last_invited': row[4]
                })
                
            return users
        except Exception as e:
            logger.error(f"Davet edilecek kullanıcıları alırken hata: {str(e)}")
            return []

    async def reset_invite_cooldowns(self, min_minutes_ago=30):
        """
        Belirli bir süreden önce davet edilen kullanıcıların cooldown sürelerini sıfırlar.
        
        Args:
            min_minutes_ago: Minimum kaç dakika önce davet edilmiş olmalı
        
        Returns:
            int: Etkilenen kullanıcı sayısı
        """
        try:
            # Belirtilen dakika önceye ait zamanı hesapla
            cutoff_time = datetime.now() - timedelta(minutes=min_minutes_ago)
            cutoff_str = cutoff_time.isoformat()
            
            # Belirli süreden önce davet edilen kullanıcıların cooldown'larını sıfırla
            query = """
            UPDATE users
            SET last_invited = NULL
            WHERE last_invited IS NOT NULL AND last_invited < ?
            """
            
            # Sorguyu çalıştır ve etkilenen satır sayısını döndür
            cursor = await self.execute(query, (cutoff_str,))
            rows_affected = cursor.rowcount if hasattr(cursor, 'rowcount') else 0
            
            return rows_affected
            
        except Exception as e:
            logger.error(f"Davet cooldown sıfırlama hatası: {str(e)}")
            return 0

    async def mark_user_invited(self, user_id):
        """
        Kullanıcının davet edildiğini işaretler.
        
        Args:
            user_id: Kullanıcı ID
        """
        try:
            now = datetime.now().isoformat()
            
            query = """
            UPDATE users
            SET last_invited = ?, invited_count = COALESCE(invited_count, 0) + 1
            WHERE id = ?
            """
            
            await self.execute(query, (now, user_id))
            return True
        except Exception as e:
            logger.error(f"Kullanıcı davet işaretleme hatası: {str(e)}")
            return False

    # Veritabanını kontrol etmek için bu sorguyu çalıştır (bir debug metodu olarak)
    async def debug_user_table(self):
        """Kullanıcı tablosunu hata ayıklama amaçlı kontrol eder"""
        try:
            # Toplam kullanıcı sayısı
            total_query = "SELECT COUNT(*) FROM users"
            total_row = await self.fetchone(total_query)
            total_users = total_row[0] if total_row else 0
            
            # Davet edilmemiş kullanıcılar
            uninvited_query = "SELECT COUNT(*) FROM users WHERE last_invited IS NULL"
            uninvited_row = await self.fetchone(uninvited_query)
            uninvited_users = uninvited_row[0] if uninvited_row else 0
            
            # Son 30 dakikada davet edilenler
            recent_query = "SELECT COUNT(*) FROM users WHERE last_invited > ?"
            cooldown_time = (datetime.now() - timedelta(minutes=30)).isoformat()
            recent_row = await self.fetchone(recent_query, (cooldown_time,))
            recent_users = recent_row[0] if recent_row else 0
            
            logger.info(f"DB DEBUG: Toplam: {total_users}, Davet Edilmemiş: {uninvited_users}, Son 30dk: {recent_users}")
            return {"total": total_users, "uninvited": uninvited_users, "recent": recent_users}
        except Exception as e:
            logger.error(f"Debug sorgu hatası: {str(e)}")
            return {}

    async def save_user_segments(self, segments):
        """Kullanıcı segmentlerini kaydeder."""
        try:
            # Önce settings tablosunu kontrol et
            self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='settings'")
            if not self.cursor.fetchone():
                logger.warning("settings tablosu bulunamadı. Tablo oluşturuluyor.")
                self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP
                )
                ''')
                self.conn.commit()
            
            # Sütunları kontrol et
            self.cursor.execute("PRAGMA table_info(settings)")
            columns = self.cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            # updated_at sütunu eksikse ekle
            if 'updated_at' not in column_names:
                logger.warning("settings tablosunda updated_at sütunu bulunamadı. Sütun ekleniyor.")
                self.cursor.execute("ALTER TABLE settings ADD COLUMN updated_at TIMESTAMP")
                self.conn.commit()
            
            # Segmentleri JSON olarak kaydet
            now = datetime.now().isoformat()
            
            # updated_at sütunu varlığına göre sorgu seç
            if 'updated_at' in column_names:
                query = """
                INSERT OR REPLACE INTO settings (key, value, updated_at) 
                VALUES (?, ?, ?)
                """
                params = ('user_segments', json.dumps(segments), now)
            else:
                # updated_at sütunu yoksa ekleme
                query = """
                INSERT OR REPLACE INTO settings (key, value) 
                VALUES (?, ?)
                """
                params = ('user_segments', json.dumps(segments))
            
            # Sorguyu çalıştır
            await self.execute(query, params)
            await self.conn.commit()
            
            logger.info(f"Kullanıcı segmentleri başarıyla kaydedildi: {len(segments)} segment")
            return True
            
        except Exception as e:
            logger.error(f"Segment kaydetme hatası: {str(e)}")
            return False

    def get_user_segments(self):
        """Kaydedilmiş kullanıcı segmentlerini getirir."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = 'user_segments'")
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
            return {}
        except Exception as e:
            logger.error(f"Segmentleri getirme hatası: {str(e)}")
            return {}

    def get_active_users(self, days=7):
        """Son n gün içinde aktif olan kullanıcıları getirir."""
        try:
            # Önce user_activity tablosunun varlığını kontrol et
            self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_activity'")
            if not self.cursor.fetchone():
                logger.warning("user_activity tablosu bulunamadı. Tablo oluşturuluyor.")
                self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_activity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    group_id INTEGER, 
                    last_message_time TIMESTAMP,
                    last_activity TIMESTAMP,
                    message_count INTEGER DEFAULT 0,
                    avg_message_length INTEGER DEFAULT 0,
                    active_hours TEXT,
                    topics TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
                ''')
                self.conn.commit()
                return []  # Tablo yeni oluşturuldu, henüz veri yok
                
            # Sütunları kontrol et
            self.cursor.execute("PRAGMA table_info(user_activity)")
            columns = self.cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            # last_activity sütununu kontrol et
            if 'last_activity' not in column_names:
                logger.warning("user_activity tablosunda last_activity sütunu bulunamadı. Sütun ekleniyor.")
                self.cursor.execute("ALTER TABLE user_activity ADD COLUMN last_activity TIMESTAMP")
                self.conn.commit()
            
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            # Alternatif sorgu - sadece users tablosundan getir
            query = """
            SELECT id, username, first_name, last_name 
            FROM users
            WHERE is_active = 1 AND last_seen > ?
            """
            
            try:
                self.cursor.execute(query, (cutoff_date,))
                
                result = []
                for row in self.cursor.fetchall():
                    result.append({
                        'id': row[0],
                        'username': row[1],
                        'first_name': row[2],
                        'last_name': row[3]
                    })
                
                logger.info(f"Son {days} gün içinde aktif {len(result)} kullanıcı bulundu")
                return result
                
            except Exception as inner_e:
                logger.warning(f"Son aktif kullanıcılar sorgusu hatası: {str(inner_e)}, basit sorgu deneniyor")
                
                # Çok basit sorgu - sadece son eklenen kullanıcılar
                simple_query = """
                SELECT id, username, first_name, last_name 
                FROM users
                WHERE is_active = 1
                ORDER BY update_time DESC
                LIMIT 50
                """
                
                self.cursor.execute(simple_query)
                
                result = []
                for row in self.cursor.fetchall():
                    result.append({
                        'id': row[0],
                        'username': row[1],
                        'first_name': row[2],
                        'last_name': row[3]
                    })
                
                logger.info(f"Basit sorgu ile {len(result)} kullanıcı bulundu")
                return result
                
        except Exception as e:
            logger.error(f"Aktif kullanıcıları getirme hatası: {str(e)}")
            return []

    def get_new_users(self, days=30):
        """Son n gün içinde eklenen kullanıcıları getirir."""
        try:
            # Sütunları kontrol et - users tablosunda id sütunu eksikse ekle
            self.cursor.execute("PRAGMA table_info(users)")
            columns = self.cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            if 'id' not in column_names:
                logger.error("users tablosunda id sütunu eksik! Bu ciddi bir veri bütünlüğü sorunudur.")
                # Eski users tablosunu adını değiştirerek koru
                try:
                    self.cursor.execute("ALTER TABLE users RENAME TO users_backup")
                    logger.warning("Mevcut users tablosu users_backup olarak yeniden adlandırıldı")
                    
                    # Yeni users tablosu doğru yapıda oluştur
                    self.cursor.execute('''
                    CREATE TABLE users (
                        id INTEGER PRIMARY KEY,
                        username TEXT,
                        first_name TEXT,
                        last_name TEXT,
                        is_bot INTEGER DEFAULT 0,
                        is_active INTEGER DEFAULT 1,
                        last_seen TIMESTAMP,
                        join_date TIMESTAMP,
                        update_time TIMESTAMP,
                        last_invited TIMESTAMP
                    )
                    ''')
                    
                    logger.info("Yeni users tablosu oluşturuldu, verileri taşıma işlemi gerekebilir")
                    return []
                except Exception as backup_error:
                    logger.error(f"users tablosunu yeniden oluşturmada hata: {str(backup_error)}")
                    return []
            
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            query = """
            SELECT id, username, first_name, last_name 
            FROM users
            WHERE join_date > ? OR update_time > ?
            """
            
            try:
                self.cursor.execute(query, (cutoff_date, cutoff_date))
                
                result = []
                for row in self.cursor.fetchall():
                    result.append({
                        'id': row[0],
                        'username': row[1],
                        'first_name': row[2],
                        'last_name': row[3]
                    })
                
                logger.info(f"Son {days} gün içinde eklenen {len(result)} yeni kullanıcı bulundu")
                return result
                
            except Exception as inner_e:
                logger.warning(f"Yeni kullanıcılar sorgusu hatası: {str(inner_e)}, basit sorgu deneniyor")
                
                # Basit sorgu
                simple_query = """
                SELECT id, username, first_name, last_name 
                FROM users
                ORDER BY join_date DESC
                LIMIT 50
                """
                
                self.cursor.execute(simple_query)
                
                result = []
                for row in self.cursor.fetchall():
                    result.append({
                        'id': row[0],
                        'username': row[1],
                        'first_name': row[2],
                        'last_name': row[3]
                    })
                
                logger.info(f"Basit sorgu ile {len(result)} yeni kullanıcı bulundu")
                return result
                
        except Exception as e:
            logger.error(f"Yeni kullanıcıları getirme hatası: {str(e)}")
            return []

    def get_dormant_users(self, days=30):
        """n günden fazla süredir aktif olmayan kullanıcıları getirir."""
        try:
            # Sütunları kontrol et - son aktivite alanı doğru mu?
            self.cursor.execute("PRAGMA table_info(users)")
            columns = self.cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            if 'last_seen' not in column_names:
                logger.warning("users tablosunda last_seen sütunu bulunamadı. Sütun ekleniyor.")
                self.cursor.execute("ALTER TABLE users ADD COLUMN last_seen TIMESTAMP")
                self.conn.commit()
            
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            # İlk olarak son görülme zamanını kullanarak dormant kullanıcıları bul
            query = """
            SELECT id, username, first_name, last_name, last_seen 
            FROM users
            WHERE last_seen < ? AND last_seen IS NOT NULL
            LIMIT 100
            """
            
            try:
                self.cursor.execute(query, (cutoff_date,))
                
                result = []
                for row in self.cursor.fetchall():
                    result.append({
                        'id': row[0],
                        'username': row[1],
                        'first_name': row[2],
                        'last_name': row[3],
                        'last_activity': row[4]
                    })
                
                logger.info(f"{days} günden fazla süredir aktif olmayan {len(result)} kullanıcı bulundu")
                return result
                
            except Exception as inner_e:
                logger.warning(f"Dormant kullanıcılar sorgusu hatası: {str(inner_e)}, basit sorgu deneniyor")
                
                # Basit sorgu - hiç aktif olmamış kullanıcılar
                simple_query = """
                SELECT id, username, first_name, last_name 
                FROM users
                WHERE last_seen IS NULL 
                LIMIT 100
                """
                
                self.cursor.execute(simple_query)
                
                result = []
                for row in self.cursor.fetchall():
                    result.append({
                        'id': row[0],
                        'username': row[1],
                        'first_name': row[2],
                        'last_name': row[3],
                        'last_activity': None
                    })
                
                logger.info(f"Basit sorgu ile {len(result)} dormant kullanıcı bulundu")
                return result
                
        except Exception as e:
            logger.error(f"Pasif kullanıcıları getirme hatası: {str(e)}")
            return []

    def update_user_demographics(self, data):
        """Kullanıcının demografik bilgilerini günceller."""
        try:
            cursor = self.conn.cursor()
            
            # Kullanıcı demografik tabloda var mı kontrol et
            cursor.execute("SELECT COUNT(*) FROM user_demographics WHERE user_id = ?", (data['user_id'],))
            exists = cursor.fetchone()[0] > 0
            
            if exists:
                # Güncelle
                query = """
                UPDATE user_demographics SET 
                    language = COALESCE(?, language),
                    bio_keywords = COALESCE(?, bio_keywords),
                    profile_picture_url = COALESCE(?, profile_picture_url),
                    last_updated = ?
                WHERE user_id = ?
                """
                
                cursor.execute(query, (
                    data.get('language'), 
                    data.get('bio_keywords'),
                    data.get('profile_picture_url'),
                    data['last_updated'].isoformat(),
                    data['user_id']
                ))
            else:
                # Yeni kayıt ekle
                query = """
                INSERT INTO user_demographics (
                    user_id, language, bio_keywords, profile_picture_url, last_updated
                ) VALUES (?, ?, ?, ?, ?)
                """
                
                cursor.execute(query, (
                    data['user_id'],
                    data.get('language'),
                    data.get('bio_keywords'),
                    data.get('profile_picture_url'),
                    data['last_updated'].isoformat()
                ))
                
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Demografik bilgi güncelleme hatası: {str(e)}")
            return False

    def update_user_group_activity(self, data):
        """Kullanıcının grup aktivitesini günceller."""
        try:
            cursor = self.conn.cursor()
            
            query = """
            INSERT OR REPLACE INTO user_activity (user_id, group_id, last_message_time)
            VALUES (?, ?, ?)
            """
            
            cursor.execute(query, (
                data['user_id'],
                data['group_id'],
                data['last_seen'].isoformat()
            ))
            
            # Ana kullanıcı tablosunda son aktif zamanı da güncelle
            cursor.execute(
                "UPDATE users SET last_active = ? WHERE id = ?",
                (data['last_seen'].isoformat(), data['user_id'])
            )
            
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Grup aktivitesi güncelleme hatası: {str(e)}")
            return False

    def get_language_distribution(self):
        """Dil dağılımını getirir."""
        try:
            cursor = self.conn.cursor()
            
            query = """
            SELECT language, COUNT(*) as count 
            FROM user_demographics 
            WHERE language IS NOT NULL 
            GROUP BY language 
            ORDER BY count DESC
            """
            
            cursor.execute(query)
            
            result = {}
            for row in cursor.fetchall():
                result[row[0]] = row[1]
                
            return result
        except Exception as e:
            logger.error(f"Dil dağılımını getirme hatası: {str(e)}")
            return {}

    def get_group_distribution(self):
        """Grup dağılımını getirir."""
        try:
            cursor = self.conn.cursor()
            
            query = """
            SELECT g.title, COUNT(DISTINCT a.user_id) as count
            FROM groups g
            JOIN user_activity a ON g.id = a.group_id
            GROUP BY g.id
            ORDER BY count DESC
            """
            
            cursor.execute(query)
            
            result = {}
            for row in cursor.fetchall():
                result[row[0]] = row[1]
                
            return result
        except Exception as e:
            logger.error(f"Grup dağılımını getirme hatası: {str(e)}")
            return {}

    def log_mining_activity(self, log_entry):
        """Veri madenciliği aktivitesini kaydeder."""
        try:
            cursor = self.conn.cursor()
            
            query = """
            INSERT INTO mining_logs (
                timestamp, groups_processed, users_processed, 
                new_users, updated_users, duration_seconds
            ) VALUES (?, ?, ?, ?, ?, ?)
            """
            
            cursor.execute(query, (
                log_entry['timestamp'].isoformat(),
                log_entry['groups_processed'],
                log_entry['users_processed'],
                log_entry['new_users'],
                log_entry['updated_users'],
                log_entry['duration_seconds']
            ))
            
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Madencilik aktivitesi kaydetme hatası: {str(e)}")
            return False

    def get_mining_stats_summary(self):
        """Veri madenciliği istatistik özetini getirir."""
        try:
            cursor = self.conn.cursor()
            
            query = """
            SELECT 
                COUNT(*) as total_runs,
                SUM(groups_processed) as total_groups,
                SUM(users_processed) as total_users,
                SUM(new_users) as total_new,
                SUM(updated_users) as total_updated,
                AVG(duration_seconds) as avg_duration,
                MAX(timestamp) as last_run
            FROM mining_logs
            """
            
            cursor.execute(query)
            row = cursor.fetchone()
            
            if not row:
                return {}
                
            return {
                'total_runs': row[0],
                'total_groups': row[1],
                'total_users': row[2],
                'total_new': row[3],
                'total_updated': row[4],
                'avg_duration': row[5],
                'last_run': row[6]
            }
        except Exception as e:
            logger.error(f"Madencilik istatistik özeti getirme hatası: {str(e)}")
            return {}

    async def get_active_groups(self, limit=50):
        """Aktif grupları getirir."""
        try:
            query = """
            SELECT * FROM groups
            WHERE is_active = 1
            ORDER BY last_activity DESC
            LIMIT ?
            """
            
            result = await self.fetchall(query, (limit,))
            return self._convert_rows_to_dict(result)
        except Exception as e:
            logger.error(f"Grupları getirme hatası: {str(e)}")
            return []

    async def mark_group_inactive(self, group_id: int, error_message: str = None, retry_time=None, permanent: bool = False):
        """Grubu devre dışı bırakır"""
        try:
            now = datetime.now()
            retry_after = retry_time or (now + timedelta(days=7 if permanent else 1))
            
            # 3 deneme yapın
            for attempt in range(3):
                try:
                    self.conn.execute('''
                        UPDATE groups
                        SET is_active = 0, 
                            retry_after = ?,
                            last_error = ?,
                            permanent_error = ?,
                            updated_at = ?
                        WHERE group_id = ?
                    ''', (retry_after.strftime('%Y-%m-%d %H:%M:%S'), 
                          error_message, 
                          1 if permanent else 0, 
                          now.strftime('%Y-%m-%d %H:%M:%S'), 
                          group_id))
                    
                    self.conn.commit()
                    logger.info(f"Grup {group_id} devre dışı bırakıldı")
                    return True
                except sqlite3.OperationalError as e:
                    if "database is locked" in str(e) and attempt < 2:
                        await asyncio.sleep(1)  # 1 saniye bekle ve tekrar dene
                    else:
                        raise
            return False
        except Exception as e:
            logger.error(f"Grup devre dışı bırakılırken hata: {str(e)}")
            return False

    def _convert_rows_to_dict(self, rows):
        """
        SQLite sorgu sonuçlarını sözlük listesine dönüştürür.
        
        Args:
            rows: SQLite sorgu sonuçları
            
        Returns:
            List[Dict]: Sözlük listesi
        """
        if not rows:
            return []
            
        result = []
        for row in rows:
            # Satır zaten sözlük mü?
            if isinstance(row, dict):
                result.append(row)
            else:
                # Gruplar tablosu için varsayılan sütunlar
                item = {
                    'group_id': row[0] if len(row) > 0 else None,
                    'title': row[1] if len(row) > 1 else None,
                    'join_date': row[2] if len(row) > 2 else None,
                    'member_count': row[3] if len(row) > 3 else None,
                    'last_activity': row[4] if len(row) > 4 else None
                }
                
                # 5. indeks varsa is_active sütununu ekle
                if len(row) > 5:
                    item['is_active'] = row[5]
                    
                # 6. indeks varsa retry_after sütununu ekle
                if len(row) > 6:
                    item['retry_after'] = row[6]
                    
                # 7. indeks varsa permanent_inactive sütununu ekle
                if len(row) > 7:
                    item['permanent_inactive'] = row[7]
                    
                # 8. indeks varsa last_error sütununu ekle
                if len(row) > 8:
                    item['last_error'] = row[8]
                    
                result.append(item)
                
        return result

    def execute_with_retry(self, query: str, params: tuple = None, max_retries: int = None) -> Optional[sqlite3.Cursor]:
        """
        Sorguyu çalıştırır. Database is locked hatası alınırsa yeniden dener.
        
        Args:
            query: SQL sorgusu
            params: Sorgu parametreleri
            max_retries: Maksimum yeniden deneme sayısı
            
        Returns:
            sqlite3.Cursor: Sorgu sonucu
        """
        if max_retries is None:
            max_retries = self.max_lock_retries
            
        retries = 0
        backoff = self.initial_backoff
        
        while retries <= max_retries:
            # Thread-safe bölge
            with self.lock:
                # Bağlantı al
                conn = None
                try:
                    if self._use_connection_pool:
                        # Bağlantı havuzundan al
                        conn = self.db_connection_manager.get_connection()
                    else:
                        # Doğrudan var olan bağlantıyı kullan
                        conn = self.conn
                        
                    cursor = conn.cursor()
                    if params:
                        cursor.execute(query, params)
                    else:
                        cursor.execute(query)
                    
                    # Autocommit modunda değilse commit yap
                    if conn.isolation_level is not None:
                        conn.commit()
                        
                    return cursor
                    
                except sqlite3.OperationalError as e:
                    if "database is locked" in str(e) and retries < max_retries:
                        # Logaritmik kademeli geri çekilme stratejisi
                        if retries == 0:
                            logger.debug(f"Veritabanı kilitli, yeniden deneniyor. Sorgu: {query}")
                        else:
                            logger.debug(f"Veritabanı kilitli, {retries}. yeniden deneme. Sorgu: {query}")
                        
                        retries += 1
                        # Havuz bağlantısını serbest bırak ve yeniden dene
                        if self._use_connection_pool and conn:
                            self.db_connection_manager.release_connection(conn)
                            conn = None
                        
                        # Kilit dışında önce kilidi serbest bırak
                        time.sleep(backoff)
                        
                        # Üstel geri çekilme (1.5 katsayı)
                        backoff = min(backoff * 1.5, self.max_backoff)
                    else:
                        # Bağlantıyı serbest bırak
                        if self._use_connection_pool and conn:
                            self.db_connection_manager.release_connection(conn)
                            conn = None
                        logger.error(f"SQL hatası: {str(e)}, Sorgu: {query}, Params: {params}")
                        raise
                
                except Exception as e:
                    # Bağlantıyı serbest bırak
                    if self._use_connection_pool and conn:
                        self.db_connection_manager.release_connection(conn)
                        conn = None
                    logger.error(f"Veritabanı hatası: {str(e)}, Sorgu: {query}, Params: {params}")
                    raise
                
                finally:
                    # Bağlantı hala açıksa ve havuzdan alındıysa serbest bırak
                    if self._use_connection_pool and conn:
                        self.db_connection_manager.release_connection(conn)
        
        # Maksimum deneme sayısı aşıldı
        logger.error(f"Veritabanı kilitleme hatası maksimum deneme sayısı aşıldı. Sorgu: {query}")
        raise sqlite3.OperationalError(f"Veritabanı kilitli, {max_retries} deneme sonrası başarısız oldu.")