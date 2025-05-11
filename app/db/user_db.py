"""
# ============================================================================ #
# Dosya: user_db.py
# Yol: /Users/siyahkare/code/telegram-bot/database/user_db.py
# İşlev: Telegram botu için kullanıcı veritabanı yönetimi sınıfı.
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

import os
import json
import logging
import time
import asyncio
import psycopg2
import psycopg2.extras
from psycopg2 import pool
import sqlite3
import aiosqlite
from datetime import datetime, timedelta
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class UserDatabase:
    """
    Kullanıcı verilerini yönetmek için veritabanı sınıfı
    """
    def __init__(self, db_url=None):
        """
        Veritabanı bağlantı parametrelerini ayarlar
        
        Args:
            db_url (str, optional): Veritabanı bağlantı URL'si - varsayılan: None
        """
        self.conn = None
        self.cursor = None
        self.connected = False
        
        if db_url:
            self.db_url = db_url
        else:
            self.db_url = os.getenv("DB_CONNECTION", "postgresql://postgres:postgres@localhost:5432/telegram_bot")
        
        # SQLite veya PostgreSQL mi kontrol et
        if self.db_url.startswith("sqlite:///"):
            self.db_type = "sqlite"
            self.db_path = self.db_url.replace("sqlite:///", "")
            logger.info(f"SQLite veritabanı kullanılacak: {self.db_path}")
        else:
            self.db_type = "postgresql"
            # PostgreSQL bağlantı parametrelerini ayrıştır
            try:
                url = urlparse(self.db_url)
                self.db_name = url.path[1:]  # / işaretini kaldır
                self.db_user = url.username or "postgres"
                self.db_password = url.password or "postgres"
                self.db_host = url.hostname or "localhost"
                self.db_port = url.port or 5432
                self.db_path = f"{self.db_host}:{self.db_port}/{self.db_name}"
                logger.debug(f"PostgreSQL bağlantı detayları: {self.db_path}")
            except Exception as e:
                logger.error(f"PostgreSQL bağlantı URL'si ayrıştırma hatası: {str(e)}")
                # Varsayılan değerleri kullan
                self.db_host = "localhost"
                self.db_port = 5432
                self.db_name = "telegram_bot"
                self.db_user = "postgres"
                self.db_password = "postgres"
                self.db_path = f"{self.db_host}:{self.db_port}/{self.db_name}"
        
        logger.debug(f"Veritabanı bağlantısı yapılandırıldı: {self.db_type}://{self.db_path}")

    async def connect(self):
        """
        Veritabanına bağlantı kurar
        
        Returns:
            bool: Bağlantı başarılı ise True, değilse False
        """
        max_attempts = 3
        connection_attempt = 0
        
        while connection_attempt < max_attempts:
            try:
                connection_attempt += 1
                
                # Zaten bağlı ise, mevcut bağlantıyı kontrol et
                if self.connected and self.conn and self.cursor:
                    try:
                        # Bağlantıyı test et
                        test_query = "SELECT 1"
                        
                        if self.db_type == "sqlite":
                            await self.cursor.execute(test_query)
                            test_result = await self.cursor.fetchone()
                        else:
                            self.cursor.execute(test_query)
                            test_result = self.cursor.fetchone()
                            
                        if test_result and test_result[0] == 1:
                            return True
                    except (psycopg2.OperationalError, psycopg2.InterfaceError, sqlite3.OperationalError, 
                            aiosqlite.OperationalError):
                        # Bağlantı kopmuş, yeniden bağlanmaya çalış
                        logger.warning("Mevcut veritabanı bağlantısı geçersiz, yeniden bağlanılıyor...")
                        self.connected = False
                        self.cursor = None
                        if self.conn:
                            try:
                                if self.db_type == "sqlite":
                                    await self.conn.close()
                                else:
                                    self.conn.close()
                            except:
                                pass
                        self.conn = None
                
                # Veritabanı tipine göre bağlan
                if self.db_type == "sqlite":
                    logger.info(f"SQLite veritabanına bağlanılıyor: {self.db_path} (Deneme {connection_attempt}/{max_attempts})")
                    
                    # SQLite dizinini oluştur
                    os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
                    
                    # Asenkron SQLite bağlantısı
                    self.conn = await aiosqlite.connect(self.db_path)
                    self.cursor = await self.conn.cursor()
                    
                    # SQLite'da PRAGMA ayarları
                    await self.cursor.execute("PRAGMA journal_mode=WAL")
                    await self.cursor.execute("PRAGMA synchronous=NORMAL")
                    await self.cursor.execute("PRAGMA foreign_keys=ON")
                    
                    self.connected = True
                    logger.info("SQLite veritabanına başarıyla bağlandı")
                    return True
                else:
                    logger.info(f"PostgreSQL veritabanına bağlanılıyor: {self.db_path} (Deneme {connection_attempt}/{max_attempts})")
                    
                    # PostgreSQL için bağlantı kurma
                    self.conn = psycopg2.connect(
                        dbname=self.db_name,
                        user=self.db_user,
                        password=self.db_password,
                        host=self.db_host,
                        port=self.db_port,
                        connect_timeout=10  # Bağlantı zaman aşımı
                    )
                    
                    self.conn.autocommit = True
                    self.cursor = self.conn.cursor()
                    self.connected = True
                    logger.info("PostgreSQL veritabanına başarıyla bağlandı")
                    return True
                
            except (psycopg2.OperationalError, sqlite3.OperationalError, aiosqlite.OperationalError) as e:
                logger.error(f"Veritabanı bağlantı hatası (Deneme {connection_attempt}/{max_attempts}): {str(e)}")
                if connection_attempt < max_attempts:
                    wait_time = 2 ** connection_attempt  # Üstel bekleme süresi
                    logger.info(f"{wait_time} saniye sonra tekrar denenecek...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.critical(f"Veritabanına bağlantı kurulamadı! Maksimum deneme sayısı aşıldı.")
                    self.connected = False
                    break
            
            except Exception as e:
                self.connected = False
                logger.error(f"Beklenmeyen veritabanı bağlantı hatası: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
                break
        
        return self.connected
    
    async def execute(self, query, params=None):
        """
        SQL komutunu çalıştırır.
        
        Args:
            query: SQL sorgusu
            params: Parametreler (opsiyonel)
            
        Returns:
            İlk satırın ilk sütunu (varsa)
        """
        try:
            if not self.connected:
                await self.connect()
                
            # Parametrelerin formatı hakkında bilgi ver
            param_info = ""
            if params:
                if isinstance(params, (list, tuple)):
                    param_info = f", {len(params)} parametre ile"
                elif isinstance(params, dict):
                    param_info = f", {len(params)} anahtarlı parametre ile"
                else:
                    param_info = f", tek parametre ile"
            
            # Sorguyu logla (kısaltılmış)
            if len(query) > 100:
                logger.debug(f"SQL sorgusu çalıştırılıyor{param_info}: {query[:100]}...")
            else:
                logger.debug(f"SQL sorgusu çalıştırılıyor{param_info}: {query}")
                
            # SQLite/PostgreSQL uyumluluk düzeltmeleri
            if self.db_type == "sqlite":
                # SQLite'ın RETURNING ifadesini desteklemediğini kontrol et
                if "RETURNING" in query.upper():
                    # RETURNING ifadesini kaldır ve INSERT ID'yi döndür
                    query = query.split("RETURNING")[0].strip()
                
                # PostgreSQL'den SQLite'a parametre dönüşümü (%s -> ?)
                query = query.replace("%s", "?")
                
                # ON CONFLICT ifadelerini SQLite'ın INSERT OR REPLACE ifadesiyle değiştir
                if "ON CONFLICT" in query.upper():
                    query = query.replace("ON CONFLICT", "OR REPLACE")
                
                # Açıkça belirt: Parametreler tuple/list tipinde değilse, tek bir değerse
                if params and not isinstance(params, (list, tuple, dict)) and not hasattr(params, '__iter__'):
                    params = (params,)
                
                # Cursor kontrolü
                if not self.cursor:
                    self.cursor = await self.conn.cursor()
                
                # Sorgu çalıştır (SQLite için)
                await self.cursor.execute(query, params if params else ())
                
                # SQL tipi kontrol et ve uygun şekilde döndür
                if query.strip().upper().startswith(('SELECT', 'WITH')):
                    # Eğer veri döndüren bir sorgu ise (SELECT, WITH)
                    result = await self.cursor.fetchone()
                    if result:
                        return result[0]  # İlk satırın ilk sütunu
                    return None
                elif query.strip().upper().startswith('INSERT'):
                    # SQLite için last_insert_rowid() döndür
                    await self.conn.commit()
                    await self.cursor.execute("SELECT last_insert_rowid()")
                    result = await self.cursor.fetchone()
                    if result:
                        return result[0]
                    return None
                else:
                    # DML sorguları için
                    await self.conn.commit()
                    return self.cursor.rowcount
            else:
                # PostgreSQL için orijinal kod
                # Açıkça belirt: Parametreler tuple/list tipinde değilse, tek bir değerse
                if params and not isinstance(params, (list, tuple, dict)) and not hasattr(params, '__iter__'):
                    params = (params,)
                    
                # Cursor kontrolü
                if not self.cursor:
                    self.cursor = self.conn.cursor()
                    
                # Sorgu çalıştır
                self.cursor.execute(query, params)
                
                # SQL tipi kontrol et ve uygun şekilde döndür
                if query.strip().upper().startswith(('SELECT', 'WITH')):
                    # Eğer veri döndüren bir sorgu ise (SELECT, WITH)
                    result = self.cursor.fetchone()
                    if result:
                        return result[0]  # İlk satırın ilk sütunu
                    return None
                elif query.strip().upper().startswith('INSERT') and 'RETURNING' in query.strip().upper():
                    # INSERT ... RETURNING ile ID döndüren sorgular için
                    result = self.cursor.fetchone()
                    if result:
                        return result[0]
                    return None
                else:
                    # DML sorguları için
                    self.conn.commit()
                    return self.cursor.rowcount
                    
        except Exception as e:
            logger.error(f"SQL sorgusu çalıştırma hatası: {str(e)}")
            logger.error(f"Hatalı sorgu: {query}")
            if params:
                logger.error(f"Parametreler: {params}")
            
            # Bağlantı hatası mı kontrol et ve yeniden bağlanmayı dene
            if isinstance(e, (psycopg2.OperationalError, psycopg2.InterfaceError, 
                             sqlite3.OperationalError, aiosqlite.OperationalError)):
                logger.warning("Veritabanı bağlantı hatası, yeniden bağlanılıyor...")
                self.connected = False
                self.cursor = None
                if self.conn:
                    try:
                        if self.db_type == "sqlite":
                            await self.conn.close()
                        else:
                            self.conn.close()
                    except:
                        pass
                self.conn = None
                
                # Bir kez daha bağlantıyı dene
                if await self.connect():
                    logger.info("Veritabanına yeniden bağlandı, sorgu tekrarlanıyor...")
                    # Yeniden dene ama sonsuz döngüye girme
                    return await self.execute(query, params)
            
            import traceback
            logger.error(traceback.format_exc())
            return None

    async def fetchone(self, query, params=None):
        """
        Tek bir sonuç satırı döndüren SQL sorgusu çalıştırır.
        
        Args:
            query: SQL sorgusu
            params: Parametreler (opsiyonel)
            
        Returns:
            Bir satırlık sonuç
        """
        try:
            if not self.connected:
                await self.connect()
                
            # Parametrelerin formatı hakkında bilgi ver
            param_info = ""
            if params:
                if isinstance(params, (list, tuple)):
                    param_info = f", {len(params)} parametre ile"
                elif isinstance(params, dict):
                    param_info = f", {len(params)} anahtarlı parametre ile"
                else:
                    param_info = f", tek parametre ile"
            
            # Sorguyu logla (kısaltılmış)
            if len(query) > 100:
                logger.debug(f"Fetchone sorgusu çalıştırılıyor{param_info}: {query[:100]}...")
            else:
                logger.debug(f"Fetchone sorgusu çalıştırılıyor{param_info}: {query}")
                
            # SQLite/PostgreSQL uyumluluk düzeltmeleri
            if self.db_type == "sqlite":
                # PostgreSQL'den SQLite'a parametre dönüşümü (%s -> ?)
                query = query.replace("%s", "?")
                
                # Açıkça belirt: Parametreler tuple/list tipinde değilse, tek bir değerse
                if params and not isinstance(params, (list, tuple, dict)) and not hasattr(params, '__iter__'):
                    params = (params,)
                
                # Cursor kontrolü
                if not self.cursor:
                    self.cursor = await self.conn.cursor()
                
                # Sorgu çalıştır (SQLite için)
                await self.cursor.execute(query, params if params else ())
                
                # Sonuçları al
                result = await self.cursor.fetchone()
                return result
            else:
                # PostgreSQL için orijinal kod
                # Açıkça belirt: Parametreler tuple/list tipinde değilse, tek bir değerse
                if params and not isinstance(params, (list, tuple, dict)) and not hasattr(params, '__iter__'):
                    params = (params,)
                    
                # Cursor kontrolü
                if not self.cursor:
                    self.cursor = self.conn.cursor()
                    
                # Sorgu çalıştır
                self.cursor.execute(query, params)
                
                # Sonuçları al
                result = self.cursor.fetchone()
                return result
                    
        except Exception as e:
            logger.error(f"Fetchone sorgusu çalıştırma hatası: {str(e)}")
            logger.error(f"Hatalı sorgu: {query}")
            if params:
                logger.error(f"Parametreler: {params}")
            
            # Bağlantı hatası mı kontrol et ve yeniden bağlanmayı dene
            if isinstance(e, (psycopg2.OperationalError, psycopg2.InterfaceError, 
                             sqlite3.OperationalError, aiosqlite.OperationalError)):
                logger.warning("Veritabanı bağlantı hatası, yeniden bağlanılıyor...")
                self.connected = False
                self.cursor = None
                if self.conn:
                    try:
                        if self.db_type == "sqlite":
                            await self.conn.close()
                        else:
                            self.conn.close()
                    except:
                        pass
                self.conn = None
                
                # Bir kez daha bağlantıyı dene
                if await self.connect():
                    logger.info("Veritabanına yeniden bağlandı, sorgu tekrarlanıyor...")
                    # Yeniden dene ama sonsuz döngüye girme
                    return await self.fetchone(query, params)
            
            import traceback
            logger.error(traceback.format_exc())
            return None

    async def fetchall(self, query, params=None):
        """
        Tüm sonuç satırlarını döndüren SQL sorgusu çalıştırır
        
        Args:
            query: SQL sorgusu
            params: Parametreler (opsiyonel)
            
        Returns:
            Tüm sonuç satırları
        """
        try:
            if not self.connected:
                await self.connect()
                
            # Parametrelerin formatı hakkında bilgi ver
            param_info = ""
            if params:
                if isinstance(params, (list, tuple)):
                    param_info = f", {len(params)} parametre ile"
                elif isinstance(params, dict):
                    param_info = f", {len(params)} anahtarlı parametre ile"
                else:
                    param_info = f", tek parametre ile"
            
            # Sorguyu logla (kısaltılmış)
            if len(query) > 100:
                logger.debug(f"Fetchall sorgusu çalıştırılıyor{param_info}: {query[:100]}...")
            else:
                logger.debug(f"Fetchall sorgusu çalıştırılıyor{param_info}: {query}")
                
            # SQLite/PostgreSQL uyumluluk düzeltmeleri
            if self.db_type == "sqlite":
                # PostgreSQL'den SQLite'a parametre dönüşümü (%s -> ?)
                query = query.replace("%s", "?")
                
                # Açıkça belirt: Parametreler tuple/list tipinde değilse, tek bir değerse
                if params and not isinstance(params, (list, tuple, dict)) and not hasattr(params, '__iter__'):
                    params = (params,)
                
                # Cursor kontrolü
                if not self.cursor:
                    self.cursor = await self.conn.cursor()
                
                # Sorgu çalıştır (SQLite için)
                await self.cursor.execute(query, params if params else ())
                
                # Sonuçları al
                result = await self.cursor.fetchall()
                return result
            else:
                # PostgreSQL için orijinal kod
                # Açıkça belirt: Parametreler tuple/list tipinde değilse, tek bir değerse
                if params and not isinstance(params, (list, tuple, dict)) and not hasattr(params, '__iter__'):
                    params = (params,)
                    
                # Cursor kontrolü
                if not self.cursor:
                    self.cursor = self.conn.cursor()
                    
                # Sorgu çalıştır
                self.cursor.execute(query, params)
                
                # Sonuçları al
                result = self.cursor.fetchall()
                return result
                    
        except Exception as e:
            logger.error(f"Fetchall sorgusu çalıştırma hatası: {str(e)}")
            logger.error(f"Hatalı sorgu: {query}")
            if params:
                logger.error(f"Parametreler: {params}")
            
            # Bağlantı hatası mı kontrol et ve yeniden bağlanmayı dene
            if isinstance(e, (psycopg2.OperationalError, psycopg2.InterfaceError, 
                             sqlite3.OperationalError, aiosqlite.OperationalError)):
                logger.warning("Veritabanı bağlantı hatası, yeniden bağlanılıyor...")
                self.connected = False
                self.cursor = None
                if self.conn:
                    try:
                        if self.db_type == "sqlite":
                            await self.conn.close()
                        else:
                            self.conn.close()
                    except:
                        pass
                self.conn = None
                
                # Bir kez daha bağlantıyı dene
                if await self.connect():
                    logger.info("Veritabanına yeniden bağlandı, sorgu tekrarlanıyor...")
                    # Yeniden dene ama sonsuz döngüye girme
                    return await self.fetchall(query, params)
            
            import traceback
            logger.error(traceback.format_exc())
            return None

    # CRUD operations for users and groups
    async def get_user_by_id(self, user_id):
        """Fetch a user by Telegram ID."""
        query = "SELECT * FROM users WHERE user_id = %s"
        return await self.fetchone(query, (user_id,))

    async def add_user(self, user_id, username, first_name, last_name, is_bot, is_active, phone=None):
        """Insert a new user."""
        query = """
            INSERT INTO users (user_id, username, first_name, last_name, is_bot, is_active, phone, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id) DO NOTHING
        """
        params = (user_id, username, first_name, last_name, is_bot, is_active, phone)
        return await self.execute(query, params)

    async def update_user(self, user_id, username, first_name, last_name, is_bot, is_active, is_premium=False, phone=None):
        """Update an existing user."""
        query = """
            UPDATE users
            SET username = %s,
                first_name = %s,
                last_name = %s,
                is_bot = %s,
                is_active = %s,
                is_premium = %s,
                phone = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s
        """
        params = (username, first_name, last_name, is_bot, is_active, is_premium, phone, user_id)
        return await self.execute(query, params)

    async def get_group_by_id(self, group_id):
        """Fetch a group by Telegram ID."""
        query = "SELECT * FROM groups WHERE group_id = %s"
        return await self.fetchone(query, (group_id,))

    async def add_group(self, group_id, name, username=None):
        """Insert or update a group."""
        if username:
            query = """
                INSERT INTO groups (group_id, name, username, is_active, created_at, updated_at)
                VALUES (%s, %s, %s, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT (group_id) DO UPDATE
                SET name = EXCLUDED.name,
                    username = EXCLUDED.username,
                    updated_at = CURRENT_TIMESTAMP
            """
            params = (group_id, name, username)
        else:
            query = """
                INSERT INTO groups (group_id, name, is_active, created_at, updated_at)
                VALUES (%s, %s, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT (group_id) DO UPDATE
                SET name = EXCLUDED.name,
                    updated_at = CURRENT_TIMESTAMP
            """
            params = (group_id, name)
        return await self.execute(query, params)

    async def update_group(self, group_id, fields: dict):
        """Update specific fields of a group."""
        set_clauses = []
        params = []
        for key, value in fields.items():
            set_clauses.append(f"{key} = %s")
            params.append(value)
        set_clause = ", ".join(set_clauses) + ", updated_at = CURRENT_TIMESTAMP"
        query = f"UPDATE groups SET {set_clause} WHERE group_id = %s"
        params.append(group_id)
        return await self.execute(query, tuple(params))

    async def create_tables(self):
        """PostgreSQL veritabanında gerekli tabloları oluşturur."""
        try:
            # user_group_relation tablosu
            user_group_relation_table = """
            CREATE TABLE IF NOT EXISTS user_group_relation (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                group_id BIGINT REFERENCES groups(group_id),
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                left_at TIMESTAMP,
                is_admin BOOLEAN DEFAULT FALSE,
                is_banned BOOLEAN DEFAULT FALSE,
                is_muted BOOLEAN DEFAULT FALSE,
                last_message_at TIMESTAMP,
                message_count INTEGER DEFAULT 0,
                UNIQUE(user_id, group_id)
            );
            """
            
            # Tabloyu oluştur
            await self.execute(user_group_relation_table)
            
            # İndeksleri oluştur
            indices = [
                "CREATE INDEX IF NOT EXISTS idx_user_group_relation_user_id ON user_group_relation(user_id);",
                "CREATE INDEX IF NOT EXISTS idx_user_group_relation_group_id ON user_group_relation(group_id);"
            ]
            
            for index in indices:
                await self.execute(index)
            
            logger.info("user_group_relation tablosu başarıyla oluşturuldu.")
            return True
        except Exception as e:
            logger.error(f"user_group_relation tablosu oluşturma hatası: {str(e)}")
            return False
            
    async def create_user_profile_tables(self):
        """Kullanıcı profili ve etkileşimleri için gerekli tabloları oluşturur."""
        try:
            # user_profiles tablosu
            user_profiles_table = """
            CREATE TABLE IF NOT EXISTS user_profiles (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                display_name TEXT,
                avatar_url TEXT,
                bio TEXT,
                interests TEXT[],
                location TEXT,
                website TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
            
            # user_connections tablosu
            user_connections_table = """
            CREATE TABLE IF NOT EXISTS user_connections (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                connected_user_id BIGINT REFERENCES users(user_id),
                connection_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, connected_user_id, connection_type)
            );
            """
            
            # user_preferences tablosu
            user_preferences_table = """
            CREATE TABLE IF NOT EXISTS user_preferences (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                preference_key TEXT NOT NULL,
                preference_value TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, preference_key)
            );
            """
            
            # İndeksler
            indices = [
                "CREATE INDEX IF NOT EXISTS idx_user_profiles_user_id ON user_profiles(user_id);",
                "CREATE INDEX IF NOT EXISTS idx_user_connections_user_id ON user_connections(user_id);",
                "CREATE INDEX IF NOT EXISTS idx_user_connections_connected_user_id ON user_connections(connected_user_id);",
                "CREATE INDEX IF NOT EXISTS idx_user_preferences_user_id ON user_preferences(user_id);",
                "CREATE INDEX IF NOT EXISTS idx_user_preferences_key ON user_preferences(preference_key);"
            ]
            
            # Tabloları oluştur
            await self.execute(user_profiles_table)
            await self.execute(user_connections_table)
            await self.execute(user_preferences_table)
            
            # İndeksleri oluştur
            for index in indices:
                await self.execute(index)
            
            logger.info("Kullanıcı profili tabloları başarıyla oluşturuldu.")
            return True
        except Exception as e:
            logger.error(f"Kullanıcı profili tabloları oluşturma hatası: {e}")
            return False

    async def disconnect(self):
        """Veritabanı bağlantısını kapatır"""
        try:
            if self.connected:
                logger.info("Veritabanı bağlantısı kapatılıyor...")
                
                # SQLite veya PostgreSQL'e göre bağlantı kapatma
                if self.db_type == "sqlite":
                    if self.cursor:
                        await self.cursor.close()
                    if self.conn:
                        await self.conn.close()
                else:
                    if self.cursor:
                        self.cursor.close()
                    if self.conn:
                        self.conn.close()
                        
                self.connected = False
                logger.info("Veritabanı bağlantısı başarıyla kapatıldı")
                return True
            else:
                logger.debug("Veritabanı bağlantısı zaten kapalı")
                return True
        except Exception as e:
            logger.error(f"Veritabanı bağlantısı kapatılırken hata: {str(e)}")
            
            # Hata alsak bile kapatıldı olarak işaretle
            self.connected = False
            self.cursor = None
            self.conn = None
            
            return False
    
    async def close(self):
        """Veritabanı bağlantısını kapatır (disconnect'in alias'ı)"""
        await self.disconnect()

    async def get_users_for_invite(self, limit=10):
        """
        Davet gönderilecek kullanıcıları getirir.
        
        Uygun kullanıcılar şu kriterlere göre seçilir:
        - Aktif kullanıcılar
        - Davet bekleme süresi dolmuş kullanıcılar
        - Daha önce davet edilmemiş veya son 7 günde davet edilmemiş kullanıcılar
        
        Args:
            limit (int): Alınacak maksimum kullanıcı sayısı
            
        Returns:
            list: Kullanıcı bilgileri listesi
        """
        try:
            # Bağlantı kontrolü
            if not self.connected or self.conn is None:
                await self.connect()
                
            # Sorgu, önce tabloları kontrol et
            check_tables_query = """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'user_invites'
            );
            """
            has_table = await self.fetchone(check_tables_query)
            has_user_invites = has_table and has_table[0]
            
            # user_invites tablosu varsa, davet edilmemiş veya uzun süredir davet edilmemiş kullanıcıları getir
            if has_user_invites:
                query = """
                SELECT u.user_id, u.username, u.first_name, u.last_name, NULL as phone
                FROM users u
                LEFT JOIN user_invites ui ON u.user_id = ui.user_id
                WHERE u.is_active = TRUE
                AND (ui.id IS NULL OR ui.invited_at < NOW() - INTERVAL '7 days')
                ORDER BY RANDOM()
                LIMIT %s
                """
            else:
                # user_invites tablosu yoksa, tüm aktif kullanıcıları getir
                query = """
                SELECT user_id, username, first_name, last_name, NULL as phone
                FROM users 
                WHERE is_active = TRUE
                ORDER BY RANDOM()
                LIMIT %s
                """
            
            result = await self.fetchall(query, (limit,))
            logger.info(f"{len(result)} adet kullanıcı davet için seçildi")
            return result
            
        except Exception as e:
            logger.error(f"Davet için kullanıcı çekme hatası: {str(e)}")
            
            # Hata durumunda, basit bir sorgu ile kullanıcı getir
            try:
                fallback_query = """
                SELECT user_id, username, first_name, last_name, NULL as phone
                FROM users 
                WHERE is_active = TRUE
                ORDER BY RANDOM()
                LIMIT %s
                """
                result = await self.fetchall(fallback_query, (limit,))
                return result
            except:
                return []
            
    async def run_migrations(self):
        """
        Veritabanı migrasyon işlemlerini çalıştırır.
        
        Returns:
            bool: İşlem başarılı ise True, değilse False
        """
        try:
            # Bağlantı kontrolü
            if not self.connected or self.conn is None:
                await self.connect()
            
            logger.info("Veritabanı migrasyonları başlatılıyor...")
            
            # Migrasyon tablosunu oluştur
            migration_table = """
            CREATE TABLE IF NOT EXISTS migrations (
                id SERIAL PRIMARY KEY,
                version VARCHAR(20),
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
            await self.execute(migration_table)
            
            # Eksik tablo kontrolü
            tables_check = [
                ("messages", """
                CREATE TABLE IF NOT EXISTS messages (
                    id SERIAL PRIMARY KEY,
                    group_id BIGINT,
                    content TEXT,
                    sent_at TIMESTAMP,
                    status TEXT,
                    error TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_messages_group_id ON messages(group_id);
                """),
                ("mining_data", """
                CREATE TABLE IF NOT EXISTS mining_data (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    group_id BIGINT,
                    group_name TEXT,
                    message_count INTEGER DEFAULT 0,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_mining_data_user_id ON mining_data(user_id);
                CREATE INDEX IF NOT EXISTS idx_mining_data_group_id ON mining_data(group_id);
                """),
                ("mining_logs", """
                CREATE TABLE IF NOT EXISTS mining_logs (
                    id SERIAL PRIMARY KEY,
                    mining_id BIGINT,
                    action_type TEXT,
                    details TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    success BOOLEAN,
                    error TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_mining_logs_mining_id ON mining_logs(mining_id);
                """),
                ("user_invites", """
                CREATE TABLE IF NOT EXISTS user_invites (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    username TEXT,
                    invite_link TEXT NOT NULL,
                    group_id BIGINT,
                    status TEXT DEFAULT 'pending',
                    invited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    joined_at TIMESTAMP,
                    last_invite_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_user_invites_user_id ON user_invites(user_id);
                CREATE INDEX IF NOT EXISTS idx_user_invites_group_id ON user_invites(group_id);
                """)
            ]
            
            # Tabloları kontrol et ve gerekirse oluştur
            for table_name, create_sql in tables_check:
                check_query = f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = '{table_name}'
                );
                """
                
                result = await self.fetchone(check_query)
                if not result or not result[0]:
                    logger.info(f"{table_name} tablosu bulunamadı, oluşturuluyor...")
                    await self.execute(create_sql)
                    logger.info(f"{table_name} tablosu başarıyla oluşturuldu")
            
            # Tüm tablolara yetki ver
            await self.grant_privileges()
            
            # Son migrasyon versiyonunu kaydet
            insert_version = "INSERT INTO migrations (version) VALUES (%s)"
            await self.execute(insert_version, ("2.1",))
            
            logger.info(f"Veritabanı migrasyonları tamamlandı")
            return True
            
        except Exception as e:
            logger.error(f"Migrasyon hatası: {str(e)}")
            return False
    
    async def grant_privileges(self):
        """
        Veritabanı tablolarına gereken yetkileri verir.
        """
        try:
            logger.info("Tablo yetkilerini ayarlama işlemi başlatılıyor...")
            
            # Tüm tabloları çek
            query = """
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public'
            """
            rows = await self.fetchall(query)
            tables = [row[0] for row in rows]
            
            # Yetki vermek için DB kullanıcısını çek
            db_user = self.db_user
            
            # Her tablo için yetki ver
            for table in tables:
                grant_query = f"GRANT ALL PRIVILEGES ON TABLE {table} TO {db_user}"
                await self.execute(grant_query)
                logger.debug(f"{table} tablosuna {db_user} için yetki verildi")
            
            # Tüm sequence'lara yetki ver
            seq_query = """
            SELECT sequence_name FROM information_schema.sequences
            WHERE sequence_schema = 'public'
            """
            seq_rows = await self.fetchall(seq_query)
            sequences = [row[0] for row in seq_rows]
            
            for seq in sequences:
                seq_grant = f"GRANT USAGE, SELECT ON SEQUENCE {seq} TO {db_user}"
                await self.execute(seq_grant)
                logger.debug(f"{seq} sequence'ına {db_user} için yetki verildi")
                
            logger.info(f"Tüm tablolara ve sekanslara yetki verme işlemi tamamlandı")
            return True
        except Exception as e:
            logger.error(f"Yetki verme işlemi sırasında hata: {str(e)}")
            return False