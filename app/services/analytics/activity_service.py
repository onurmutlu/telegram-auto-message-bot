"""
# ============================================================================ #
# Dosya: activity_service.py
# Yol: /Users/siyahkare/code/telegram-bot/app/services/analytics/activity_service.py
# İşlev: Kullanıcı aktivite ve etkileşimlerini izleme servisi.
#
# Versiyon: v1.0.0
# ============================================================================ #
"""

import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from app.services.base_service import BaseService
from app.db.session import get_db

logger = logging.getLogger(__name__)

class ActivityService(BaseService):
    """
    Kullanıcı aktivite ve etkileşim izleme servisi.
    - Grup ve kullanıcı etkileşimlerini kaydeder
    - Etkileşim istatistiklerini tutar
    - Aktivite analizi sağlar
    """
    
    service_name = "activity_service"
    
    def __init__(self, db: AsyncSession = None):
        """
        ActivityService sınıfını başlatır.
        
        Args:
            db: Veritabanı bağlantısı
        """
        super().__init__(name="activity_service")
        self.db = db
    
    async def initialize(self):
        """Servisi başlat."""
        self.db = self.db or await get_db().__anext__()
        logger.info("ActivityService initialized")
        return True
    
    async def log_interaction(
        self, 
        user_id: int, 
        group_id: int, 
        message_id: int, 
        interaction_type: str
    ) -> bool:
        """
        Kullanıcı etkileşimini kaydet.
        
        Args:
            user_id: Kullanıcı ID
            group_id: Grup ID
            message_id: Mesaj ID
            interaction_type: Etkileşim tipi (reply, mention, like, etc.)
            
        Returns:
            bool: Başarılı ise True
        """
        try:
            query = """
                INSERT INTO user_interactions (
                    user_id, group_id, message_id, interaction_type, created_at
                )
                VALUES (:user_id, :group_id, :message_id, :interaction_type, NOW())
                RETURNING id
            """
            params = {
                "user_id": user_id, 
                "group_id": group_id,
                "message_id": message_id,
                "interaction_type": interaction_type
            }
            
            result = await self.db.execute(query, params)
            interaction_id = result.fetchone()[0]
            await self.db.commit()
            
            # Grup ve kullanıcı son aktivite zamanını güncelle
            await self._update_last_activity(user_id, group_id)
            
            logger.debug(f"Logged interaction {interaction_id}: {interaction_type} by user {user_id} in group {group_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error logging interaction: {str(e)}", exc_info=True)
            return False
    
    async def _update_last_activity(self, user_id: int, group_id: int) -> None:
        """
        Kullanıcı ve grup son aktivite zamanını güncelle.
        
        Args:
            user_id: Kullanıcı ID
            group_id: Grup ID
        """
        try:
            # Kullanıcı aktivitesini güncelle
            query = """
                UPDATE users
                SET last_activity_at = NOW()
                WHERE id = :user_id
            """
            await self.db.execute(query, {"user_id": user_id})
            
            # Grup aktivitesini güncelle
            query = """
                UPDATE groups
                SET last_activity_at = NOW()
                WHERE id = :group_id
            """
            await self.db.execute(query, {"group_id": group_id})
            
            await self.db.commit()
            
        except Exception as e:
            logger.error(f"Error updating last activity: {str(e)}", exc_info=True)
    
    async def get_user_activity(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        """
        Kullanıcının aktivite istatistiklerini getir.
        
        Args:
            user_id: Kullanıcı ID
            days: Kaç günlük veri alınacak
            
        Returns:
            Dict: Aktivite istatistikleri
        """
        try:
            query = """
                SELECT 
                    COUNT(*) as total_interactions,
                    COUNT(DISTINCT group_id) as active_groups,
                    COUNT(DISTINCT date_trunc('day', created_at)) as active_days,
                    MAX(created_at) as last_interaction
                FROM user_interactions
                WHERE user_id = :user_id AND created_at > NOW() - INTERVAL ':days days'
            """
            
            result = await self.db.execute(query, {"user_id": user_id, "days": days})
            stats = result.fetchone()
            
            if not stats:
                return {
                    "total_interactions": 0,
                    "active_groups": 0,
                    "active_days": 0,
                    "last_interaction": None
                }
            
            return dict(stats)
            
        except Exception as e:
            logger.error(f"Error getting user activity: {str(e)}", exc_info=True)
            return {
                "total_interactions": 0,
                "active_groups": 0,
                "active_days": 0,
                "last_interaction": None,
                "error": str(e)
            }
    
    async def cleanup(self):
        """Servis kapatılırken temizlik."""
        logger.info("ActivityService cleanup completed")
        
    async def _start(self) -> bool:
        """BaseService için başlatma metodu"""
        return await self.initialize()
        
    async def _stop(self) -> bool:
        """BaseService için durdurma metodu"""
        try:
            await self.cleanup()
            return True
        except Exception as e:
            logger.error(f"ActivityService durdurma hatası: {e}")
            return False
            
    async def _update(self) -> bool:
        """Periyodik güncelleme metodu"""
        # Bu servis için güncelleme işlemi yok
        return True 