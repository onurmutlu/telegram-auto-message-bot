"""
Telegram Bot yapılandırma yönetimi
"""
import os
import json
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

@dataclass
class TelegramConfig:
    api_id: int
    api_hash: str
    phone: str
    session_path: Path
    logs_path: Path
    user_db_path: Path
    data_path: Path
    environment: str = "production"  # "production" veya "development"
    
    @property
    def is_production(self) -> bool:
        """Üretim ortamında mı çalışıyor?"""
        return self.environment.lower() == "production"

class Config:
    _instance: TelegramConfig = None
    
    @staticmethod
    def get_project_root() -> Path:
        """Proje kök dizinini döndürür"""
        return Path(__file__).parent.parent
    
    @staticmethod
    def load_config() -> TelegramConfig:
        if Config._instance is None:
            # Ana proje dizini
            root_dir = Config.get_project_root()
            
            # Session dizini - açıkça belirtilmiş
            session_path = root_dir / 'session'
            logs_path = root_dir / 'logs'
            user_db_path = root_dir / 'data' / 'users.db'
            
            # Ortam değişkeninden geliştirme modunu al
            environment = os.getenv("ENVIRONMENT", "production")
            
            Config._instance = TelegramConfig(
                api_id=int(os.getenv('API_ID', '0')),
                api_hash=os.getenv('API_HASH', ''),
                phone=os.getenv('PHONE_NUMBER', ''),
                session_path=session_path,
                logs_path=logs_path,
                user_db_path=user_db_path,
                data_path=root_dir / 'data',
                environment=environment
            )
            
            # Dizinleri oluştur
            session_path.mkdir(parents=True, exist_ok=True)
            logs_path.mkdir(parents=True, exist_ok=True)
            (root_dir / 'data').mkdir(parents=True, exist_ok=True)
            (root_dir / 'data' / 'backups').mkdir(parents=True, exist_ok=True)
        
        return Config._instance
    
    @staticmethod
    def load_messages() -> Dict[str, List[str]]:
        """Mesaj şablonlarını yükler"""
        config = Config.load_config()
        messages_path = config.data_path / 'messages.json'
        
        if not messages_path.exists():
            raise FileNotFoundError(f"Mesaj şablonları bulunamadı: {messages_path}")
            
        with open(messages_path, 'r', encoding='utf-8') as f:
            return json.load(f)
            
    @staticmethod
    def load_invites() -> Dict[str, Any]:
        """Davet şablonlarını yükler"""
        config = Config.load_config()
        invites_path = config.data_path / 'invites.json'
        
        if not invites_path.exists():
            raise FileNotFoundError(f"Davet şablonları bulunamadı: {invites_path}")
            
        with open(invites_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    @staticmethod
    def load_responses() -> Dict[str, List[str]]:
        """Yanıt şablonlarını yükler"""
        config = Config.load_config()
        responses_path = config.data_path / 'responses.json'
        
        if not responses_path.exists():
            raise FileNotFoundError(f"Yanıt şablonları bulunamadı: {responses_path}")
            
        with open(responses_path, 'r', encoding='utf-8') as f:
            return json.load(f)

def _load_api_credentials():
    api_id = os.getenv('API_ID')
    api_hash = os.getenv('API_HASH')
    phone = os.getenv('PHONE_NUMBER')
    
    if not api_id or not api_hash or not phone:
        raise ValueError("API kimlik bilgileri eksik. .env dosyasını kontrol edin.")
    
    try:
        api_id = int(api_id)
    except ValueError:
        raise ValueError("API_ID sayısal bir değer olmalıdır.")
        
    return api_id, api_hash, phone