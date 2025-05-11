"""
Kullanıcı yönetimi ve takip servisi.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, List, Union

from sqlalchemy.ext.asyncio import AsyncSession
from app.services.base_service import BaseService
from app.db.session import get_db
from app.models.user import User

logger = logging.getLogger(__name__)

class UserService(BaseService):
    """
    Kullanıcı yönetimi ve takip servisi.
    - Kullanıcı kayıt ve güncellemesi
    - DM etkileşimlerinin takibi
    - Kullanıcı istatistiklerinin yönetimi
    """
    
    service_name = "user_service"
    
    def __init__(self, db: AsyncSession = None):
        """
        UserService sınıfını başlatır.
        
        Args:
            db: Veritabanı bağlantısı
        """
        super().__init__(name="user_service")
        self.db = db
    
    async def initialize(self):
        """Servisi başlat."""
        self.db = self.db or await get_db().__anext__()
        logger.info("UserService initialized")
        return True
    
    async def register_or_update_user(self, user_data) -> int:
        """
        Kullanıcıyı veritabanına kaydet veya güncelle.
        
        Args:
            user_data: Telegram kullanıcı nesnesi
            
        Returns:
            int: Kullanıcı ID
        """
        try:
            # Kullanıcı bilgilerini hazırla
            user_id = user_data.id
            username = user_data.username if hasattr(user_data, "username") else None
            first_name = user_data.first_name if hasattr(user_data, "first_name") else None
            last_name = user_data.last_name if hasattr(user_data, "last_name") else None
            
            # Kullanıcı var mı kontrol et
            query = "SELECT id FROM users WHERE id = :user_id"
            result = await self.db.execute(query, {"user_id": user_id})
            user = result.fetchone()
            
            if not user:
                # Yeni kullanıcı ekle
                query = """
                    INSERT INTO users (
                        id, username, first_name, last_name, 
                        is_active, created_at, updated_at, last_activity_at
                    )
                    VALUES (
                        :user_id, :username, :first_name, :last_name, 
                        true, NOW(), NOW(), NOW()
                    )
                    RETURNING id
                """
                params = {
                    "user_id": user_id,
                    "username": username,
                    "first_name": first_name,
                    "last_name": last_name
                }
                result = await self.db.execute(query, params)
                await self.db.commit()
                logger.info(f"User {user_id} registered")
            else:
                # Var olan kullanıcıyı güncelle
                query = """
                    UPDATE users
                    SET username = :username, 
                        first_name = :first_name, 
                        last_name = :last_name,
                        updated_at = NOW(),
                        last_activity_at = NOW()
                    WHERE id = :user_id
                """
                params = {
                    "user_id": user_id,
                    "username": username,
                    "first_name": first_name,
                    "last_name": last_name
                }
                await self.db.execute(query, params)
                await self.db.commit()
                logger.debug(f"User {user_id} updated")
            
            return user_id
            
        except Exception as e:
            logger.error(f"Error registering/updating user: {str(e)}", exc_info=True)
            return None
    
    async def get_user(self, user_id: int) -> Dict[str, Any]:
        """
        Kullanıcı bilgilerini getir.
        
        Args:
            user_id: Kullanıcı ID
            
        Returns:
            Dict: Kullanıcı bilgileri
        """
        try:
            query = """
                SELECT * FROM users
                WHERE id = :user_id
            """
            result = await self.db.execute(query, {"user_id": user_id})
            user = result.fetchone()
            
            if not user:
                return None
            
            return dict(user)
            
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {str(e)}", exc_info=True)
            return None
    
    async def update_user(self, user_id: int, data: Dict[str, Any]) -> bool:
        """
        Kullanıcı bilgilerini güncelle.
        
        Args:
            user_id: Kullanıcı ID
            data: Güncellenecek alanlar ve değerleri
            
        Returns:
            bool: Başarılı ise True
        """
        try:
            # Güncellenecek alanları ve değerlerini hazırla
            set_statements = []
            params = {"user_id": user_id}
            
            for key, value in data.items():
                set_statements.append(f"{key} = :{key}")
                params[key] = value
            
            if not set_statements:
                return False
            
            # Güncelleme zamanını ekle
            set_statements.append("updated_at = NOW()")
            
            # SQL sorgusu oluştur
            query = f"""
                UPDATE users
                SET {', '.join(set_statements)}
                WHERE id = :user_id
            """
            
            await self.db.execute(query, params)
            await self.db.commit()
            
            logger.debug(f"User {user_id} updated with data: {data}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating user {user_id}: {str(e)}", exc_info=True)
            return False
    
    async def update_user_stats(self, user_id: int, **stats) -> bool:
        """
        Kullanıcı istatistiklerini güncelle.
        
        Args:
            user_id: Kullanıcı ID
            **stats: İstatistik alanları (messages_received, messages_sent, promos_sent vb.)
            
        Returns:
            bool: Başarılı ise True
        """
        try:
            # Güncellenecek alanları ve değerlerini hazırla
            set_statements = []
            params = {"user_id": user_id}
            
            for key, value in stats.items():
                set_statements.append(f"{key} = {key} + :{key}")
                params[key] = value
            
            if not set_statements:
                return False
            
            # Güncelleme zamanını ekle
            set_statements.append("updated_at = NOW()")
            
            # SQL sorgusu oluştur
            query = f"""
                UPDATE users
                SET {', '.join(set_statements)}
                WHERE id = :user_id
            """
            
            await self.db.execute(query, params)
            await self.db.commit()
            
            logger.debug(f"User {user_id} stats updated: {stats}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating user stats for {user_id}: {str(e)}", exc_info=True)
            return False
    
    async def log_dm_activity(
        self, 
        user_id: int, 
        content: str, 
        message_type: str,
        response_to: str = None
    ) -> bool:
        """
        DM aktivitesini kaydet.
        
        Args:
            user_id: Kullanıcı ID
            content: Mesaj içeriği
            message_type: Mesaj tipi (welcome, service_list, promo vb.)
            response_to: Yanıt verilen mesaj içeriği
            
        Returns:
            bool: Başarılı ise True
        """
        try:
            query = """
                INSERT INTO user_dm_activities (
                    user_id, content, message_type, response_to, created_at
                )
                VALUES (
                    :user_id, :content, :message_type, :response_to, NOW()
                )
                RETURNING id
            """
            params = {
                "user_id": user_id,
                "content": content,
                "message_type": message_type,
                "response_to": response_to
            }
            
            result = await self.db.execute(query, params)
            activity_id = result.fetchone()[0]
            
            # Kullanıcının son DM zamanını güncelle
            query = """
                UPDATE users
                SET last_dm_at = NOW()
                WHERE id = :user_id
            """
            await self.db.execute(query, {"user_id": user_id})
            
            await self.db.commit()
            
            logger.debug(f"Logged DM activity {activity_id} for user {user_id}: {message_type}")
            return True
            
        except Exception as e:
            logger.error(f"Error logging DM activity for user {user_id}: {str(e)}", exc_info=True)
            return False
    
    async def cleanup(self):
        """Servis kapatılırken temizlik."""
        logger.info("UserService cleanup completed")
        
    async def _start(self) -> bool:
        """BaseService için başlatma metodu"""
        return await self.initialize()
        
    async def _stop(self) -> bool:
        """BaseService için durdurma metodu"""
        try:
            await self.cleanup()
            return True
        except Exception as e:
            logger.error(f"UserService durdurma hatası: {e}")
            return False
            
    async def _update(self) -> bool:
        """Periyodik güncelleme metodu"""
        # Bu servis için güncelleme işlemi yok
        return True 