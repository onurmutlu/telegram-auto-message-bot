"""
# ============================================================================ #
# Dosya: user_service.py 
# Yol: /Users/siyahkare/code/telegram-bot/bot/services/user_service.py
# İşlev: Telegram bot için kullanıcı yönetimi servisi.
#
# Build: 2025-04-02-08:30:00
# Versiyon: v3.4.1
# ============================================================================ #
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any

logger = logging.getLogger(__name__)

class UserService:
    """
    Kullanıcı yönetim servisi - kullanıcı verilerinin işlenmesi ve yönetilmesinden sorumlu.
    
    Bu servis, kullanıcıların veritabanına eklenmesi, güncellenmesi, davet edilmesi 
    ve kullanıcı verilerinin sorgulanması gibi işlemleri yönetir.
    """
    
    def __init__(self, client, db, config):
        """
        UserService sınıfını başlatır.
        
        Args:
            client: Telethon müşteri nesnesi
            db: Veritabanı bağlantısı 
            config: Yapılandırma nesnesi
        """
        self.client = client
        self.db = db
        self.config = config
        self.last_activity = datetime.now()
        self.processed_users = 0
        self.invited_users = 0
        self.running = True
        
    async def add_user(self, user_id: int, username: str = None, 
                      first_name: str = None, last_name: str = None) -> bool:
        """
        Yeni bir kullanıcıyı veritabanına ekler.
        
        Args:
            user_id: Kullanıcı ID
            username: Kullanıcı adı (isteğe bağlı)
            first_name: İlk adı (isteğe bağlı)
            last_name: Soyadı (isteğe bağlı)
            
        Returns:
            bool: İşlem başarılı ise True
        """
        try:
            self.db.add_user(user_id, username, first_name, last_name)
            self.processed_users += 1
            self.last_activity = datetime.now()
            logger.info(f"Kullanıcı eklendi: {user_id} - @{username}")
            return True
        except Exception as e:
            logger.error(f"Kullanıcı ekleme hatası: {str(e)}")
            return False
            
    async def update_user_activity(self, user_id: int) -> bool:
        """
        Kullanıcının son aktivite zamanını günceller.
        
        Args:
            user_id: Kullanıcı ID
            
        Returns:
            bool: İşlem başarılı ise True
        """
        try:
            self.db.update_last_seen(user_id)
            return True
        except Exception as e:
            logger.error(f"Kullanıcı aktivite güncelleme hatası: {str(e)}")
            return False

    async def get_users_to_invite(self, limit: int = 10) -> List[Tuple[int, Optional[str]]]:
        """
        Davet edilecek kullanıcıları getirir.
        
        Args:
            limit: Maksimum kullanıcı sayısı
            
        Returns:
            Liste[Tuple[int, Optional[str]]]: (user_id, username) şeklinde tuple listesi 
        """
        try:
            return self.db.get_users_to_invite(limit)
        except Exception as e:
            logger.error(f"Davet edilecek kullanıcı getirme hatası: {str(e)}")
            return []

    async def mark_user_invited(self, user_id: int) -> bool:
        """
        Kullanıcıyı davet edildi olarak işaretler.
        
        Args:
            user_id: Kullanıcı ID
            
        Returns:
            bool: İşlem başarılı ise True
        """
        try:
            self.db.mark_as_invited(user_id)
            self.invited_users += 1
            logger.info(f"Kullanıcı davet edildi olarak işaretlendi: {user_id}")
            return True
        except Exception as e:
            logger.error(f"Kullanıcı davet işaretleme hatası: {str(e)}")
            return False
            
    async def is_invited(self, user_id: int) -> bool:
        """
        Kullanıcının daha önce davet edilip edilmediğini kontrol eder.
        
        Args:
            user_id: Kullanıcı ID
            
        Returns:
            bool: Kullanıcı davet edildiyse True
        """
        return self.db.is_invited(user_id)
        
    async def was_recently_invited(self, user_id: int, hours: int = 4) -> bool:
        """
        Kullanıcının belirtilen saat içinde davet edilip edilmediğini kontrol eder.
        
        Args:
            user_id: Kullanıcı ID
            hours: Son kaç saatte kontrol edileceği
            
        Returns:
            bool: Son `hours` saat içinde davet edildiyse True
        """
        return self.db.was_recently_invited(user_id, hours)
        
    def get_status(self) -> Dict[str, Any]:
        """
        Servisin mevcut durumunu ve istatistiklerini döndürür.
        
        Returns:
            Dict: Servis durumu ve istatistikleri
        """
        return {
            "running": self.running,
            "processed_users": self.processed_users,
            "invited_users": self.invited_users,
            "last_activity": self.last_activity.strftime("%H:%M:%S")
        }