"""
# ============================================================================ #
# Dosya: settings.py
# Yol: /Users/siyahkare/code/telegram-bot/config/settings.py
# İşlev: Bot yapılandırma ayarlarını .env dosyasından yükler.
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

import os
import logging
from datetime import datetime
from typing import Dict, Any
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class Config:
    """
    Bot yapılandırma sınıfı.
    
    Bu sınıf, botun çalışması için gerekli yapılandırma ayarlarını .env dosyasından
    veya ortam değişkenlerinden yükler.
    """
    
    def __init__(self, env_path: str = ".env"):
        """
        Config sınıfının başlatıcısı.
        
        Args:
            env_path: .env dosyasının yolu
        """
        # .env dosyasını yükle
        self.load_success = load_dotenv(env_path)
        if not self.load_success:
            logger.warning(f".env dosyası bulunamadı: {env_path}, ortam değişkenleri kullanılacak")
        
        # Telegram yapılandırması
        self.telegram = self._load_telegram_config()
        
        # Veritabanı yapılandırması
        self.database = self.db = self._load_database_config()
        
        # Mesajlaşma ayarları
        self.messaging = self._load_messaging_config()
        
        # Genel ayarlar
        self.settings = self._load_general_settings()
        
        logger.info("Yapılandırma yüklendi")
    
    def get(self, key, default=None):
        """
        Yapılandırma ayarını güvenli bir şekilde alır (dict benzeri erişim için).
        
        Args:
            key (str): Ayar anahtarı
            default: Ayar bulunamazsa döndürülecek değer
            
        Returns:
            Ayar değeri veya varsayılan değer
        """
        # Nokta içeren anahtarlar için (örn: 'telegram.api_id')
        if '.' in key:
            parts = key.split('.')
            current = self
            for part in parts[:-1]:
                if hasattr(current, part):
                    current = getattr(current, part)
                else:
                    return default
            
            # Son parça
            last_part = parts[-1]
            if hasattr(current, last_part):
                return getattr(current, last_part)
            else:
                return default
                
        # Basit anahtarlar için doğrudan öznitelik ara
        if hasattr(self, key):
            return getattr(self, key)
        elif hasattr(self.settings, key):
            return getattr(self.settings, key)
        elif hasattr(self.telegram, key):
            return getattr(self.telegram, key)
        elif hasattr(self.database, key):
            return getattr(self.database, key)
        elif hasattr(self.messaging, key):
            return getattr(self.messaging, key)
        else:
            return default
            
    def __getitem__(self, key):
        """
        Dict benzeri erişim için __getitem__ metodu.
        
        Args:
            key (str): Ayar anahtarı
            
        Returns:
            Ayar değeri
            
        Raises:
            KeyError: Anahtar bulunamazsa
        """
        value = self.get(key)
        if value is None:
            raise KeyError(key)
        return value
    
    def __contains__(self, key):
        """
        Dict benzeri 'in' operatörü desteği için __contains__ metodu.
        
        Args:
            key (str): Ayar anahtarı
            
        Returns:
            bool: Anahtar varsa True, yoksa False
        """
        return self.get(key) is not None
        
    def __iter__(self):
        """
        Dict benzeri iterasyon desteği için __iter__ metodu.
        
        Returns:
            Anahtar iterator'ı
        """
        # Tüm config anahtarlarını birleştir
        keys = set(dir(self))
        keys = {k for k in keys if not k.startswith('_') and k not in 
                ['load_success', 'telegram', 'database', 'db', 'messaging', 'settings',
                 'get', 'items', 'keys', 'values']}
        
        # Alt config nesnelerindeki anahtarları ekle
        if hasattr(self, 'settings'):
            settings_keys = {f"settings.{k}" for k in dir(self.settings) if not k.startswith('_')}
            keys.update(settings_keys)
            
        if hasattr(self, 'telegram'):
            telegram_keys = {f"telegram.{k}" for k in dir(self.telegram) if not k.startswith('_')}
            keys.update(telegram_keys)
            
        if hasattr(self, 'database'):
            database_keys = {f"database.{k}" for k in dir(self.database) if not k.startswith('_')}
            keys.update(database_keys)
            
        if hasattr(self, 'messaging'):
            messaging_keys = {f"messaging.{k}" for k in dir(self.messaging) if not k.startswith('_')}
            keys.update(messaging_keys)
            
        return iter(keys)
        
    def items(self):
        """
        Dict benzeri items() metodu.
        
        Returns:
            (anahtar, değer) çiftlerinin iterator'ı
        """
        for key in self:
            yield (key, self.get(key))
            
    def keys(self):
        """
        Dict benzeri keys() metodu.
        
        Returns:
            Anahtarların iterator'ı
        """
        return iter(self)
        
    def values(self):
        """
        Dict benzeri values() metodu.
        
        Returns:
            Değerlerin iterator'ı
        """
        for key in self:
            yield self.get(key)
    
    def _load_telegram_config(self) -> Any:
        """
        Telegram yapılandırmasını yükler.
        
        Returns:
            Any: Telegram yapılandırması
        """
        class TelegramConfig:
            def __init__(self):
                self.api_id = os.environ.get('API_ID')
                self.api_hash = os.environ.get('API_HASH')
                self.bot_token = os.environ.get('BOT_TOKEN')
                self.session_name = os.environ.get('SESSION_NAME', 'bot_session')
                
                # Opsiyonel proxy ayarları
                proxy_host = os.environ.get('PROXY_HOST')
                proxy_port = os.environ.get('PROXY_PORT')
                proxy_username = os.environ.get('PROXY_USERNAME')
                proxy_password = os.environ.get('PROXY_PASSWORD')
                
                if proxy_host and proxy_port:
                    self.proxy = {
                        'proxy_type': os.environ.get('PROXY_TYPE', 'socks5'),
                        'addr': proxy_host,
                        'port': int(proxy_port),
                        'username': proxy_username,
                        'password': proxy_password
                    }
                else:
                    self.proxy = None
        
        return TelegramConfig()
    
    def _load_database_config(self) -> Any:
        """
        Veritabanı yapılandırmasını yükler.
        
        Returns:
            Any: Veritabanı yapılandırması
        """
        class DatabaseConfig:
            def __init__(self):
                self.type = os.environ.get('DB_TYPE', 'sqlite')
                
                # SQLite için
                if self.type.lower() == 'sqlite':
                    self.path = os.environ.get('DB_PATH', 'data/bot.db')
                    
                # PostgreSQL için
                elif self.type.lower() == 'postgres':
                    self.host = os.environ.get('DB_HOST', 'localhost')
                    self.port = int(os.environ.get('DB_PORT', '5432'))
                    self.user = os.environ.get('DB_USER')
                    self.password = os.environ.get('DB_PASSWORD')
                    self.database = os.environ.get('DB_NAME')
        
        return DatabaseConfig()
    
    def _load_messaging_config(self) -> Any:
        """
        Mesajlaşma yapılandırmasını yükler.
        
        Returns:
            Any: Mesajlaşma yapılandırması
        """
        class MessagingConfig:
            def __init__(self):
                self.templates_path = os.environ.get('TEMPLATES_PATH', 'data/messages.json')
                self.invites_path = os.environ.get('INVITES_PATH', 'data/invites.json')
                self.responses_path = os.environ.get('RESPONSES_PATH', 'data/responses.json')
        
        return MessagingConfig()
    
    def _load_general_settings(self) -> Any:
        """
        Genel ayarları yükler.
        
        Returns:
            Any: Genel ayarlar
        """
        class GeneralSettings:
            def __init__(self):
                self.environment = os.environ.get('ENVIRONMENT', 'production')
                self.debug_mode = os.environ.get('DEBUG_MODE', 'false').lower() == 'true'
                self.admin_groups = self._parse_list(os.environ.get('ADMIN_GROUPS', ''))
                self.super_users = self._parse_list(os.environ.get('SUPER_USERS', ''))
            
            def _parse_list(self, value: str) -> list:
                return [item.strip() for item in value.split(',')] if value else []
        
        return GeneralSettings()
    
    @property
    def env(self):
        """
        Ortam bilgisini döndürür.
        Varsayılan olarak "production" değerini döndürür.
        """
        return self.settings.environment

    @property
    def debug(self):
        """
        Debug modunu döndürür.
        Varsayılan olarak False değerini döndürür.
        """
        return self.settings.debug_mode

    @property
    def admin_groups(self):
        """
        Yönetici gruplarını döndürür (Yönetici/Kurucu olduğunuz gruplar).
        """
        return self.settings.admin_groups

    @property
    def super_users(self):
        """
        Süper kullanıcıların listesini döndürür.
        """
        return self.settings.super_users