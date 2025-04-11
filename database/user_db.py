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
from typing import Optional, Dict, List, Any, Union, Tuple

logger = logging.getLogger(__name__)

class UserDatabase:
    """
    Veritabanı işlemlerini yöneten sınıf.
    
    Bu sınıf, SQLite veritabanı kullanarak kullanıcı bilgilerini yönetir.
    Kullanıcı ekleme, güncelleme, sorgulama ve silme gibi temel veritabanı 
    işlemlerini sağlar. Ayrıca veritabanı bağlantısını yönetir, 
    yedekleme yapar ve performans optimizasyonları uygular.
    """
    
    def __init__(self, config_or_path="data/bot.db"):
        """
        UserDatabase sınıfının yapıcısı
        
        Args:
            config_or_path: Veritabanı yapılandırması veya dosya yolu 
                            (varsayılan: "data/bot.db")
        """
        # String veya Path nesnesi ise doğrudan yol olarak kullan
        if isinstance(config_or_path, (str, Path)):
            self.db_path = Path(config_or_path)
            self.db_type = "sqlite"
        # Yapılandırma nesnesi ise
        else:
            self.db_type = getattr(config_or_path, 'type', 'sqlite').lower()
            
            if self.db_type == 'sqlite':
                self.db_path = Path(getattr(config_or_path, 'path', 'data/bot.db'))
            elif self.db_type == 'postgres' or self.db_type == 'postgresql':
                # PostgreSQL için bağlantı bilgileri
                self.db_host = getattr(config_or_path, 'host', 'localhost')
                self.db_port = getattr(config_or_path, 'port', 5432)
                self.db_user = getattr(config_or_path, 'user', 'postgres')
                self.db_password = getattr(config_or_path, 'password', '')
                self.db_name = getattr(config_or_path, 'db_name', 'telegram_bot')
                self.db_path = Path(f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}")
            else:
                raise ValueError(f"Desteklenmeyen veritabanı türü: {self.db_type}")

        # Veritabanı dizinin var olduğundan emin ol
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path_str = str(self.db_path)  # String olarak sakla
        
        # Bağlantı ve cursor niteliklerini başlangıçta None olarak ayarla
        self.conn = None
        self.connection = None
        self.cursor = None

    async def connect(self):
        """
        Veritabanına bağlanır ve tabloları oluşturur.
        
        Returns:
            bool: Bağlantı başarılı ise True
        """
        try:
            if self.conn:
                # Zaten bağlıysa tekrar bağlanmaya gerek yok
                return True

            # Bağlantıyı oluştur
            self.conn = sqlite3.connect(self.db_path_str)
            self.connection = self.conn  # İki değişkeni aynı nesneye referans yap
            
            # Row factory ayarla
            self.conn.row_factory = sqlite3.Row
            
            # Cursor oluştur
            self.cursor = self.conn.cursor()
            
            # Tabloları oluştur
            self._create_tables()
            
            logger.info(f"Veritabanı bağlandı: {self.db_path_str}")
            return True
        except Exception as e:
            logger.error(f"Veritabanı bağlantı hatası: {str(e)}")
            self._backup_and_recreate_if_needed()
            return False

    async def disconnect(self):
        """
        Veritabanı bağlantısını kapatır.
        
        Returns:
            bool: Bağlantı başarıyla kapatıldıysa True
        """
        if self.conn:
            try:
                self.conn.close()
                self.conn = None
                self.connection = None
                self.cursor = None
                logger.info("Veritabanı bağlantısı kapatıldı")
                return True
            except Exception as e:
                logger.error(f"Veritabanı kapatma hatası: {str(e)}")
                return False
        return True  # Zaten kapalıysa başarılı kabul et
    
    def _create_tables(self):
        """Gerekli tabloları oluşturur."""
        try:
            # Kullanıcılar tablosu
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
                is_active BOOLEAN DEFAULT 1,
                blocked INTEGER DEFAULT 0,
                invited INTEGER DEFAULT 0,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_admin INTEGER DEFAULT 0
            )
            ''')
            
            # Grup istatistikleri tablosu
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
            
            # Hata veren gruplar tablosu
            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS error_groups (
                group_id INTEGER PRIMARY KEY,
                group_title TEXT,
                error_reason TEXT,
                last_error_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                retry_after TIMESTAMP
            )
            ''')
            
            self.conn.commit()
            
        except sqlite3.Error as e:
            logger.error(f"Tablo oluşturma hatası: {str(e)}")

    def get_target_groups(self):
        """
        Veritabanından hedef grupları alır.
        
        Returns:
            list: Hedef grupların listesi
        """
        try:
            self.cursor.execute("""
            SELECT group_id, group_name, message_count 
            FROM group_stats 
            WHERE is_active = 1
            ORDER BY last_activity DESC
            """)
            rows = self.cursor.fetchall()
            
            groups = []
            for row in rows:
                groups.append({
                    'group_id': row[0],
                    'title': row[1],
                    'message_count': row[2]
                })
            return groups
        except Exception as e:
            logger.error(f"Hedef gruplar alınırken hata: {str(e)}")
            return []

    # Diğer metodlar (değişiklik yok)...