"""
Yapılandırma ayarları ve ortam değişkenleri yönetimi
"""
import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class Config:
    """Uygulama yapılandırmasını yöneten sınıf"""
    
    DEFAULT_CONFIG = {
        "environment": "production",  # production veya development
        "logs_path": "logs/bot.log",
        "detailed_logs_path": "logs/detailed_bot.json",
        "user_db_path": "data/users.db",
        "message_delay_min": 60,       # saniye cinsinden minimum gecikme
        "message_delay_max": 180,      # saniye cinsinden maksimum gecikme
        "messages_per_day": 20,        # Günlük maksimum mesaj sayısı
        "message_templates_path": "data/messages.json",
        "invite_templates_path": "data/invites.json",
        "session_file": "session/member_session",
        "admin_ids": []                # Yönetici kullanıcı ID listesi
    }
    
    def __init__(self):
        # Varsayılan yapılandırma
        self.environment = self.DEFAULT_CONFIG["environment"]
        self.logs_path = Path(self.DEFAULT_CONFIG["logs_path"])
        self.detailed_logs_path = Path(self.DEFAULT_CONFIG["detailed_logs_path"])
        self.user_db_path = Path(self.DEFAULT_CONFIG["user_db_path"])
        self.message_delay_min = self.DEFAULT_CONFIG["message_delay_min"]
        self.message_delay_max = self.DEFAULT_CONFIG["message_delay_max"]
        self.messages_per_day = self.DEFAULT_CONFIG["messages_per_day"]
        self.message_templates_path = Path(self.DEFAULT_CONFIG["message_templates_path"])
        self.invite_templates_path = Path(self.DEFAULT_CONFIG["invite_templates_path"])
        self.session_file = Path(self.DEFAULT_CONFIG["session_file"])
        self.admin_ids = self.DEFAULT_CONFIG["admin_ids"]
    
    @staticmethod
    def load_config():
        """Yapılandırma dosyasını yükler"""
        try:
            # Önce default config dosyasını oluştur
            config_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(config_dir, "config.json")
            
            # Eğer dosya yoksa varsayılanları oluştur
            if not os.path.exists(config_path):
                default_config = {
                    "session_file": "session/telegram_bot",
                    "log_file": "logs/bot.log",
                    "log_level": "INFO",
                    "debug_mode": False,
                    "environment": "production"
                }
                
                # Config dizinini oluştur
                os.makedirs(config_dir, exist_ok=True)
                
                # Varsayılan config dosyasını oluştur
                with open(config_path, "w") as f:
                    json.dump(default_config, f, indent=4)
                
                logger.info(f"Varsayılan yapılandırma dosyası oluşturuldu: {config_path}")
                return Config()  # DEFAULT_CONFIG değerleriyle başlat
            
            # Dosya varsa yükle
            with open(config_path, "r") as f:
                config_data = json.load(f)
            
            # Yeni bir Config nesnesi oluştur
            config = Config()
            
            # Config nesnesinin alanlarını güncelle
            for key, value in config_data.items():
                if hasattr(config, key):
                    # Path nesnelerini dönüştür
                    if key.endswith('_path') or key == 'logs_path' or key == 'session_file':
                        value = Path(value)
                    
                    setattr(config, key, value)
            
            return config
            
        except Exception as e:
            logger.warning(f"Yapılandırma dosyası yüklenemedi: {str(e)}, varsayılanlar kullanılıyor")
            # Varsayılan değerlerle devam et
            return Config()  # DEFAULT_CONFIG değerleriyle başlat
    
    @classmethod
    def load_api_credentials(cls):
        """
        API kimlik bilgilerini .env dosyasından yükler
        Returns:
            Tuple: (api_id, api_hash, phone)
        """
        # .env dosyasını yükle (eğer main.py'de yüklenmediyse)
        load_dotenv()
        
        # API bilgilerini çevre değişkenlerinden al
        api_id = os.getenv('API_ID')
        if api_id is not None:
            api_id = int(api_id)
        
        api_hash = os.getenv('API_HASH')
        phone = os.getenv('PHONE_NUMBER')
        
        if not all([api_id, api_hash, phone]):
            error_msg = "API kimlik bilgileri eksik! .env dosyasını kontrol edin."
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        logger.debug(f"API bilgileri yüklendi: ID:{api_id}, TELEFON:{phone}")
        return api_id, api_hash, phone

    @classmethod
    def load_messages(cls, file_path: Optional[str] = None):
        """
        Mesaj şablonlarını JSON dosyasından yükler
        Args:
            file_path: Mesaj şablonları dosya yolu (None ise varsayılan kullanılır)
        Returns:
            list: Mesaj şablonları listesi
        """
        try:
            # Yapılandırma dosyası yoksa varsayılan yolu kullan
            if file_path is None:
                file_path = cls.DEFAULT_CONFIG["message_templates_path"]
            
            # Dosyanın var olduğunu kontrol et
            path = Path(file_path)
            if not path.exists():
                logger.warning(f"Mesaj şablonları dosyası bulunamadı: {file_path}")
                # Örnek şablonlar oluştur (doğrudan liste formatında)
                sample_messages = [
                    "Merhaba, gruba hoş geldiniz! 👋",
                    "Bu grup, [KONU] hakkında bilgi paylaşımı için oluşturulmuştur.",
                    "Sorularınız için @admin ile iletişime geçebilirsiniz."
                ]
                
                # Dizini oluştur
                path.parent.mkdir(parents=True, exist_ok=True)
                
                # Örnek dosyayı kaydet
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(sample_messages, f, ensure_ascii=False, indent=4)
                
                logger.info(f"Örnek mesaj şablonları oluşturuldu: {file_path}")
                return sample_messages
            
            # Dosyayı oku
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Hem eski hem de yeni format desteği
            if isinstance(data, list):
                # Doğrudan liste formatı (tercih edilen)
                messages = data
            elif isinstance(data, dict) and "group_messages" in data:
                # Eski format - nesne içindeki liste
                messages = data["group_messages"]
            else:
                logger.warning(f"Desteklenmeyen mesaj formatı: {file_path}")
                return []
                
            if not isinstance(messages, list):
                logger.warning(f"Mesajlar bir liste değil: {file_path}")
                return []
            
            logger.info(f"{len(messages)} mesaj şablonu yüklendi")
            return messages
        
        except Exception as e:
            logger.error(f"Mesaj şablonları yükleme hatası: {str(e)}")
            return []

    @classmethod
    def load_invites(cls, file_path: Optional[str] = None):
        """
        Davet mesajlarını JSON dosyasından yükler
        Args:
            file_path: Davet mesajları dosya yolu (None ise varsayılan kullanılır)
        Returns:
            dict: Davet mesajları içeren sözlük
        """
        try:
            # Yapılandırma dosyası yoksa varsayılan yolu kullan
            if file_path is None:
                file_path = cls.DEFAULT_CONFIG["invite_templates_path"]
            
            # Dosyanın var olduğunu kontrol et
            path = Path(file_path)
            if not path.exists():
                logger.warning(f"Davet mesajları dosyası bulunamadı: {file_path}")
                return {"invites": [], "invites_outro": [], "redirect_messages": []}
            
            # Dosyayı oku
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Veri doğruluğunu kontrol et
            if not isinstance(data, dict):
                logger.warning(f"Davet mesajları geçerli bir JSON nesnesi değil: {file_path}")
                return {"invites": [], "invites_outro": [], "redirect_messages": []}
                
            # Eksik anahtarları kontrol et ve varsayılanları ekle
            result = {
                "invites": data.get("invites", []),
                "invites_outro": data.get("invites_outro", []),
                "redirect_messages": data.get("redirect_messages", [])
            }
            
            logger.info(f"Davet mesajları yüklendi: {len(result['invites'])} davet, {len(result['redirect_messages'])} yönlendirme")
            return result
        
        except Exception as e:
            logger.error(f"Davet mesajları yükleme hatası: {str(e)}")
            return {"invites": [], "invites_outro": [], "redirect_messages": []}

    @classmethod
    def load_responses(cls, file_path: Optional[str] = None):
        """
        Yanıt mesajlarını JSON dosyasından yükler
        Args:
            file_path: Yanıt mesajları dosya yolu (None ise varsayılan 'data/responses.json')
        Returns:
            dict: Yanıt mesajları içeren sözlük
        """
        try:
            # Yapılandırma dosyası yoksa varsayılan yolu kullan
            if file_path is None:
                file_path = "data/responses.json"
            
            # Dosyanın var olduğunu kontrol et
            path = Path(file_path)
            if not path.exists():
                logger.warning(f"Yanıt mesajları dosyası bulunamadı: {file_path}")
                return {"flirty_responses": []}
            
            # Dosyayı oku
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Veri doğruluğunu kontrol et
            if not isinstance(data, dict):
                logger.warning(f"Yanıt mesajları geçerli bir JSON nesnesi değil: {file_path}")
                return {"flirty_responses": []}
                
            # Eksik anahtarları kontrol et ve varsayılanları ekle
            result = {
                "flirty_responses": data.get("flirty_responses", [])
            }
            
            logger.info(f"Yanıt mesajları yüklendi: {len(result['flirty_responses'])} flirty yanıt")
            return result
        
        except Exception as e:
            logger.error(f"Yanıt mesajları yükleme hatası: {str(e)}")
            return {"flirty_responses": []}

    def save_config(self, config_path: str = "config/config.json") -> bool:
        """
        Yapılandırma ayarlarını JSON dosyasına kaydeder
        Args:
            config_path: Kayıt yapılacak dosya yolu
        Returns:
            bool: Başarılı ise True
        """
        try:
            # Dizini oluştur (yoksa)
            Path(config_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Config nesnesini sözlüğe dönüştür
            config_dict = {}
            for key, default_value in self.DEFAULT_CONFIG.items():
                value = getattr(self, key)
                # Path nesnelerini string'e dönüştür
                if isinstance(value, Path):
                    value = str(value)
                config_dict[key] = value
            
            # JSON olarak kaydet
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=4)
                
            logger.info(f"Yapılandırma kaydedildi: {config_path}")
            return True
        
        except Exception as e:
            logger.error(f"Yapılandırma kaydetme hatası: {str(e)}")
            return False
    
    def __str__(self) -> str:
        """Config nesnesinin string gösterimi"""
        return f"Config(env={self.environment}, db={self.user_db_path}, logs={self.logs_path})"