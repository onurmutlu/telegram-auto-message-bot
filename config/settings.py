"""
# ============================================================================ #
# Dosya: settings.py
# Yol: /Users/siyahkare/code/telegram-bot/config/settings.py
# İşlev: Telegram bot yapılandırma ayarlarını yönetir.
#
# Build: 2025-04-01
# Versiyon: v3.4.0
# ============================================================================ #
#
# Bu modül, Telegram bot uygulamasının yapılandırma ayarlarını yönetmek için kullanılır.
# Başlıca işlevleri şunlardır:
#   - Ortam değişkenlerinden yapılandırma ayarlarını yükleme
#   - Dosyalardan (örneğin, config.json, invites.json) yapılandırma ayarlarını yükleme
#   - Varsayılan yapılandırma ayarlarını tanımlama
#   - Yapılandırma ayarlarını diğer modüller tarafından erişilebilir hale getirme
#
# ============================================================================ #
"""
import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class Config:
    """
    Bot yapılandırma ayarlarını yönetir.
    """

    BASE_DIR = Path(__file__).resolve().parent.parent
    DATA_DIR = BASE_DIR / 'data'
    RUNTIME_DIR = BASE_DIR / 'runtime'
    SESSION_DIR = RUNTIME_DIR / 'sessions'
    DATABASE_DIR = RUNTIME_DIR / 'database'
    LOGS_DIR = RUNTIME_DIR / 'logs'

    DATABASE_PATH = DATABASE_DIR / 'users.db'
    SESSION_PATH = SESSION_DIR / 'member_session'
    LOG_FILE_PATH = LOGS_DIR / 'bot.log'
    MESSAGE_TEMPLATES_PATH = DATA_DIR / 'messages.json'
    INVITE_TEMPLATES_PATH = DATA_DIR / 'invites.json'
    RESPONSE_TEMPLATES_PATH = DATA_DIR / 'responses.json'
    CONFIG_PATH = DATA_DIR / 'config.json'

    def __init__(self, config_path="data/config.json", 
                 messages_path="data/messages.json",
                 invites_path="data/invites.json",
                 responses_path="data/responses.json"):
        """
        Config sınıfının başlatıcı metodu.
        """
        self.config_path = config_path
        self.messages_path = messages_path
        self.invites_path = invites_path
        self.responses_path = responses_path
        
        self.data = self._load_config_data()  # Metod adını düzelt
        self.messages = self._load_messages()
        self.invites = self._load_invites()
        self.responses = self._load_responses_data()  # Metod adını düzelt
        
        self.message_templates = {}
        self.invite_templates = {}
        self.response_templates = {}
        self.flirty_messages = []
        
        # Yükleme fonksiyonlarını çağır
        self.load_message_templates()
        self.load_invite_templates()
        self.load_response_templates()
        self.load_flirty_messages()
        
        # Log
        logger.info("Yapılandırma yüklendi")

    @classmethod
    def load_config(cls):
        """
        Yapılandırma yükler ve döndürür.
        
        Returns:
            Config: Doldurulmuş yapılandırma nesnesi
        """
        return cls()  # Sınıfın yeni bir örneğini döndür

    def load_message_templates(self):
        """
        Mesaj şablonlarını yükler.
        """
        try:
            # Mesajları doğrudan messages dosyasından al
            self.message_templates = self.messages
            logger.info(f"{len(self.message_templates)} mesaj şablonu yüklendi")
        except Exception as e:
            logger.error(f"Mesaj şablonları yüklenirken hata: {e}")
            self.message_templates = {}

    def load_invite_templates(self):
        """
        Davet şablonlarını yükler.
        """
        try:
            # Davet şablonlarını doğrudan invites dosyasından al
            self.invite_templates = self.invites
            logger.info(f"{len(self.invite_templates)} davet şablonu yüklendi")
        except Exception as e:
            logger.error(f"Davet şablonları yüklenirken hata: {e}")
            self.invite_templates = {}

    def load_response_templates(self):
        """
        Yanıt şablonlarını yükler.
        """
        try:
            # Yanıtları doğrudan responses dosyasından al
            self.response_templates = self.responses.get("flirty", [])
            logger.info(f"{len(self.response_templates)} yanıt şablonu yüklendi")
        except Exception as e:
            logger.error(f"Yanıt şablonları yüklenirken hata: {e}")
            self.response_templates = []  # Boş liste ile başlat, None değil

    def load_flirty_messages(self):
        """
        Flirty mesajları yükler.
        """
        try:
            # Flirty mesajları doğrudan responses dosyasından al
            self.flirty_messages = self.responses.get("flirty", [])
            logger.info(f"{len(self.flirty_messages)} flirty mesaj yüklendi")
        except Exception as e:
            logger.error(f"Flirty mesajlar yüklenirken hata: {e}")
            self.flirty_messages = []
        return self.flirty_messages

    def create_directories(self):
        """
        Gerekli dizinleri oluşturur.
        Bu dizinler, oturum dosyaları, veritabanı dosyaları ve log dosyaları için kullanılır.
        """
        os.makedirs(self.SESSION_DIR, exist_ok=True)
        os.makedirs(self.DATABASE_DIR, exist_ok=True)
        os.makedirs(self.LOGS_DIR, exist_ok=True)
        os.makedirs(self.DATABASE_DIR / 'backups', exist_ok=True)

    @property
    def env(self):
        """
        Ortam bilgisini döndürür.
        Varsayılan olarak "production" değerini döndürür.
        """
        return os.getenv("ENVIRONMENT", "production")

    @property
    def debug(self):
        """
        Debug modunu döndürür.
        Varsayılan olarak False değerini döndürür.
        """
        return self.debug_mode

    @property
    def admin_groups(self):
        """
        Yönetici gruplarını döndürür (Yönetici/Kurucu olduğunuz gruplar).
        Ortam değişkeninden yükler ve virgülle ayrılmış değerleri liste olarak döndürür.
        """
        admin_groups_str = os.getenv("ADMIN_GROUPS", "")
        return [group.strip() for group in admin_groups_str.split(",")] if admin_groups_str else []

    @property
    def super_users(self):
        """
        Süper kullanıcıların listesini döndürür.
        Ortam değişkeninden yükler ve virgülle ayrılmış değerleri liste olarak döndürür.
        """
        super_users_str = os.getenv("SUPER_USERS", "")
        return [user.strip() for user in super_users_str.split(",")] if super_users_str else []

    def _load_messages(self):
        """
        Mesajlar dosyasını yükler.
        """
        try:
            with open(self.messages_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Mesajlar dosyası bulunamadı: {self.messages_path}")
            return []
        except json.JSONDecodeError:
            logger.error(f"Mesajlar dosyası JSON formatında değil: {self.messages_path}")
            return []

    def _load_invites(self):
        """
        Davetler dosyasını yükler.
        """
        try:
            with open(self.invites_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Davetler dosyası bulunamadı: {self.invites_path}")
            return {}
        except json.JSONDecodeError:
            logger.error(f"Davetler dosyası JSON formatında değil: {self.invites_path}")
            return {}

    def _load_config_data(self):  # Metod adını düzelt
        """
        Yapılandırma dosyasını yükler.
        """
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Yapılandırma dosyası bulunamadı: {self.config_path}")
            return {}
        except json.JSONDecodeError:
            logger.error(f"Yapılandırma dosyası JSON formatında değil: {self.config_path}")
            return {}

    def _load_responses_data(self):  # Metod adını düzelt
        """
        Yanıtlar dosyasını yükler.
        """
        try:
            with open(self.responses_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Yanıtlar dosyası bulunamadı: {self.responses_path}")
            return {}
        except json.JSONDecodeError:
            logger.error(f"Yanıtlar dosyası JSON formatında değil: {self.responses_path}")
            return {}