import logging
from typing import Optional
from enum import Enum

logger = logging.getLogger(__name__)

class UserStatus(Enum):
    ACTIVE = "active"
    BLOCKED = "blocked"
    NOT_FOUND = "not_found"
    INACTIVE = "inactive"

class UserService:
    def __init__(self, db):
        self.db = db

    async def process_user(self, user_id: int, username: str, phone: str) -> None:
        """Kullanıcıyı işle ve gerekli kontrolleri yap"""
        try:
            # Kullanıcıyı veritabanına ekle
            await self.add_user(user_id, username, phone)
            
            # Kullanıcı durumunu kontrol et
            user_status = await self.check_user_status(user_id)
            
            if user_status == UserStatus.ACTIVE:
                # Kullanıcı aktif, işlem yapma
                logger.info(f"Kullanıcı {user_id} zaten aktif")
                return
                
            elif user_status == UserStatus.BLOCKED:
                # Kullanıcı engellenmiş, işlem yapma
                logger.warning(f"Kullanıcı {user_id} engellenmiş durumda")
                return
                
            elif user_status == UserStatus.NOT_FOUND:
                # Kullanıcı bulunamadı, yeni kullanıcı olarak ekle
                logger.info(f"Yeni kullanıcı eklendi: {user_id}")
                await self.add_user(user_id, username, phone)
                
            else:
                # Kullanıcı pasif, aktifleştir
                logger.info(f"Kullanıcı {user_id} aktifleştirildi")
                await self.activate_user(user_id)
                
        except Exception as e:
            logger.error(f"Kullanıcı işleme hatası: {str(e)}")
            raise

    async def add_user(self, user_id: int, username: str, phone: str, is_active: bool = True) -> None:
        """Yeni kullanıcı ekle"""
        try:
            # Kullanıcı zaten var mı kontrol et
            if await self.user_exists(user_id):
                logger.info(f"Kullanıcı {user_id} zaten mevcut")
                return
                
            # Kullanıcıyı veritabanına ekle
            query = """
                INSERT INTO users (user_id, username, phone, status, is_active, created_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
            """
            await self.db.execute(query, (user_id, username, phone, UserStatus.ACTIVE.value, is_active))
            logger.info(f"Yeni kullanıcı eklendi: {user_id}")
            
        except Exception as e:
            logger.error(f"Kullanıcı ekleme hatası: {str(e)}")
            raise

    async def user_exists(self, user_id: int) -> bool:
        """Kullanıcının veritabanında olup olmadığını kontrol et"""
        try:
            query = "SELECT COUNT(*) FROM users WHERE user_id = %s"
            result = await self.db.fetchone(query, (user_id,))
            return result[0] > 0 if result else False
        except Exception as e:
            logger.error(f"Kullanıcı kontrolü hatası: {str(e)}")
            return False

    async def check_user_status(self, user_id: int) -> UserStatus:
        """Kullanıcının durumunu kontrol et"""
        try:
            query = "SELECT status, is_active FROM users WHERE user_id = %s"
            result = await self.db.fetchone(query, (user_id,))
            
            if not result:
                return UserStatus.NOT_FOUND
                
            status, is_active = result
            if not is_active:
                return UserStatus.INACTIVE
                
            return UserStatus(status)
        except Exception as e:
            logger.error(f"Kullanıcı durumu kontrolü hatası: {str(e)}")
            return UserStatus.NOT_FOUND

    async def activate_user(self, user_id: int) -> None:
        """Kullanıcıyı aktifleştir"""
        try:
            query = """
                UPDATE users 
                SET status = %s, is_active = TRUE 
                WHERE user_id = %s
            """
            await self.db.execute(query, (UserStatus.ACTIVE.value, user_id))
            logger.info(f"Kullanıcı aktifleştirildi: {user_id}")
        except Exception as e:
            logger.error(f"Kullanıcı aktifleştirme hatası: {str(e)}")
            raise 