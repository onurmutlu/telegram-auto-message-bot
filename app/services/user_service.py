"""
# ============================================================================ #
# Dosya: user_service.py
# Yol: /Users/siyahkare/code/telegram-bot/app/services/user_service.py
# İşlev: Telegram bot için kullanıcı yönetimi servisi.
#
# Versiyon: v2.0.0
# ============================================================================ #
"""

import logging
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime
from sqlalchemy import text

from app.services.base_service import BaseService
from app.db.session import get_session

logger = logging.getLogger(__name__)

class UserStatus(str, Enum):
    """Kullanıcı durumları"""
    # Büyük harfli versiyonlar (standard)
    ACTIVE = "ACTIVE"
    BLOCKED = "BLOCKED"
    NOT_FOUND = "NOT_FOUND"
    INACTIVE = "INACTIVE"
    # Küçük harfli versiyonlar (DB'de mevcut eski değerler)
    active = "active"
    blocked = "blocked"
    not_found = "not_found"
    inactive = "inactive"
    
    @classmethod
    def normalize(cls, value):
        """Herhangi bir formattaki durum değerini standart formata dönüştürür"""
        if value is None:
            return cls.ACTIVE
        
        # String ise
        if isinstance(value, str):
            # Uppercase yapıp enum değerini bul
            try:
                upper_value = value.upper()
                if upper_value == "ACTIVE":
                    return cls.ACTIVE
                elif upper_value == "BLOCKED":
                    return cls.BLOCKED
                elif upper_value == "NOT_FOUND":
                    return cls.NOT_FOUND
                elif upper_value == "INACTIVE":
                    return cls.INACTIVE
                # Eşleşme bulunamazsa varsayılan
                return cls.ACTIVE
            except (KeyError, AttributeError):
                # Eşleşme bulunamazsa varsayılan
                return cls.ACTIVE
        
        # Zaten enum ise
        if isinstance(value, cls):
            return value
            
        # Varsayılan değer
        return cls.ACTIVE

class UserService(BaseService):
    """
    Kullanıcı yönetimi ve işlemleri için servis.
    """
    
    service_name = "user_service"
    default_interval = 300  # 5 dakikada bir güncelleme
    
    def __init__(self, name='user_service', client=None, db=None, config=None, stop_event=None, *args, **kwargs):
        """
        UserService sınıfının başlatıcısı.
        """
        super().__init__(name=name)
        self.logger = logging.getLogger(__name__)  # Logger tanımla
        self.client = client
        self.db = db
        self.config = config
        self.stop_event = stop_event
        self.initialized = False
        self.user_cache = {}
        self.stats = {
            'total_users': 0,
            'active_users': 0,
            'blocked_users': 0,
            'last_update': None
        }
        self.logger.info("UserService oluşturuldu")
    
    async def _start(self) -> bool:
        """
        Servisi başlatır.
        
        Returns:
            bool: Başlatma başarılıysa True
        """
        try:
            self.logger.info("UserService başlatılıyor...")
            
            # DB bağlantısını kontrol et
            if not self.db:
                self.logger.warning("Veritabanı bağlantısı sağlanmadı, doğrudan session kullanılacak")
            
            # Kullanıcı istatistiklerini yükle
            await self.load_user_stats()
            
            self.initialized = True
            self.logger.info(f"UserService başlatıldı. Toplam {self.stats['total_users']} kullanıcı, " 
                             f"{self.stats['active_users']} aktif, {self.stats['blocked_users']} engellenmiş.")
            return True
        except Exception as e:
            self.logger.exception(f"UserService başlatma hatası: {str(e)}")
            return False
    
    async def _stop(self) -> bool:
        """
        Servisi durdurur.
        
        Returns:
            bool: Durdurma başarılıysa True
        """
        try:
            self.logger.info("UserService durduruluyor...")
            # Kullanıcı önbelleğini temizle
            self.user_cache.clear()
            self.initialized = False
            self.logger.info("UserService durduruldu")
            return True
        except Exception as e:
            self.logger.exception(f"UserService durdurma hatası: {str(e)}")
            return False
    
    async def _update(self) -> None:
        """
        Düzenli olarak çağrılan güncelleme metodu.
        Kullanıcı durumlarını ve istatistiklerini günceller.
        """
        try:
            if not self.initialized:
                self.logger.warning("UserService henüz başlatılmadı, güncelleme atlanıyor")
                return
                
            self.logger.debug("UserService güncelleniyor...")
            
            # Kullanıcı istatistiklerini yükle
            await self.load_user_stats()
            
            self.logger.debug(f"UserService güncelleme tamamlandı. Toplam {self.stats['total_users']} kullanıcı, " 
                             f"{self.stats['active_users']} aktif, {self.stats['blocked_users']} engellenmiş.")
        except Exception as e:
            self.logger.exception(f"UserService güncelleme hatası: {str(e)}")

    async def load_user_stats(self) -> None:
        """Kullanıcı istatistiklerini veritabanından yükler"""
        try:
            session = next(get_session())
            
            # Toplam kullanıcı sayısı
            total_query = text("SELECT COUNT(*) FROM users")
            total_result = session.execute(total_query).scalar()
            
            # Aktif kullanıcı sayısı - UPPER ile büyük/küçük harf duyarsızlığı
            active_query = text("""
                SELECT COUNT(*) FROM users 
                WHERE UPPER(is_active::text) = 'TRUE' AND 
                      (UPPER(status) = 'ACTIVE' OR status = 'active')
            """)
            active_result = session.execute(active_query).scalar()
            
            # Engellenmiş kullanıcı sayısı - UPPER ile büyük/küçük harf duyarsızlığı
            blocked_query = text("""
                SELECT COUNT(*) FROM users 
                WHERE UPPER(status) = 'BLOCKED' OR status = 'blocked'
            """)
            blocked_result = session.execute(blocked_query).scalar()
            
            # İstatistikleri güncelle
            self.stats['total_users'] = total_result or 0
            self.stats['active_users'] = active_result or 0
            self.stats['blocked_users'] = blocked_result or 0
            self.stats['last_update'] = datetime.now()
            
        except Exception as e:
            self.logger.error(f"Kullanıcı istatistikleri yüklenirken hata: {str(e)}", exc_info=True)

    async def process_user(self, user_id: int, username: str, phone: str) -> None:
        """Kullanıcıyı işle ve gerekli kontrolleri yap"""
        try:
            # Kullanıcıyı veritabanına ekle
            await self.add_user(user_id, username, phone)
            
            # Kullanıcı durumunu kontrol et
            user_status = await self.check_user_status(user_id)
            
            if user_status == UserStatus.ACTIVE:
                # Kullanıcı aktif, işlem yapma
                self.logger.info(f"Kullanıcı {user_id} zaten aktif")
                return
                
            elif user_status == UserStatus.BLOCKED:
                # Kullanıcı engellenmiş, işlem yapma
                self.logger.warning(f"Kullanıcı {user_id} engellenmiş durumda")
                return
                
            elif user_status == UserStatus.NOT_FOUND:
                # Kullanıcı bulunamadı, yeni kullanıcı olarak ekle
                self.logger.info(f"Yeni kullanıcı eklendi: {user_id}")
                await self.add_user(user_id, username, phone)
                
            else:
                # Kullanıcı pasif, aktifleştir
                self.logger.info(f"Kullanıcı {user_id} aktifleştirildi")
                await self.activate_user(user_id)
                
        except Exception as e:
            self.logger.error(f"Kullanıcı işleme hatası: {str(e)}", exc_info=True)
            raise

    async def add_user(self, user_id: int, username: str, phone: str, is_active: bool = True) -> None:
        """Yeni kullanıcı ekle"""
        try:
            # Kullanıcı zaten var mı kontrol et
            if await self.user_exists(user_id):
                self.logger.info(f"Kullanıcı {user_id} zaten mevcut")
                return
            
            session = next(get_session())
            
            # Kullanıcıyı veritabanına ekle - SQL Injection koruması için parametreli sorgu
            query = text("""
                INSERT INTO users (user_id, username, phone, status, is_active, created_at, updated_at)
                VALUES (:user_id, :username, :phone, :status, :is_active, NOW(), NOW())
            """)
            
            session.execute(query, {
                "user_id": user_id, 
                "username": username, 
                "phone": phone, 
                "status": UserStatus.ACTIVE.value,
                "is_active": is_active
            })
            
            session.commit()
            self.logger.info(f"Yeni kullanıcı eklendi: {user_id}")
            
            # Önbelleği güncelle
            self.user_cache[user_id] = {
                "username": username,
                "phone": phone,
                "status": UserStatus.ACTIVE.value,
                "is_active": is_active
            }
            
        except Exception as e:
            self.logger.error(f"Kullanıcı ekleme hatası: {str(e)}", exc_info=True)
            raise

    async def user_exists(self, user_id: int) -> bool:
        """Kullanıcının veritabanında olup olmadığını kontrol et"""
        try:
            # Önce önbellekte kontrol et
            if user_id in self.user_cache:
                return True
                
            session = next(get_session())
            
            query = text("SELECT COUNT(*) FROM users WHERE user_id = :user_id")
            result = session.execute(query, {"user_id": user_id}).scalar()
            
            exists = result > 0 if result is not None else False
            
            # Kullanıcı varsa önbelleğe ekle
            if exists:
                user_query = text("""
                    SELECT username, phone, status, is_active 
                    FROM users WHERE user_id = :user_id
                """)
                user_result = session.execute(user_query, {"user_id": user_id}).first()
                
                if user_result:
                    self.user_cache[user_id] = {
                        "username": user_result[0],
                        "phone": user_result[1],
                        "status": user_result[2],
                        "is_active": user_result[3]
                    }
            
            return exists
            
        except Exception as e:
            self.logger.error(f"Kullanıcı kontrolü hatası: {str(e)}", exc_info=True)
            return False

    async def check_user_status(self, user_id: int) -> UserStatus:
        """Kullanıcının durumunu kontrol et"""
        try:
            # Önce önbellekte kontrol et
            if user_id in self.user_cache:
                cache_status = self.user_cache[user_id].get("status")
                cache_is_active = self.user_cache[user_id].get("is_active")
                
                if not cache_is_active:
                    return UserStatus.INACTIVE
                    
                return UserStatus.normalize(cache_status)
                
            session = next(get_session())
            
            query = text("""
                SELECT status, is_active 
                FROM users 
                WHERE user_id = :user_id
            """)
            
            result = session.execute(query, {"user_id": user_id}).first()
            
            if not result:
                return UserStatus.NOT_FOUND
                
            status, is_active = result
            
            if not is_active:
                return UserStatus.INACTIVE
                
            return UserStatus.normalize(status)
            
        except Exception as e:
            self.logger.error(f"Kullanıcı durumu kontrolü hatası: {str(e)}", exc_info=True)
            return UserStatus.NOT_FOUND

    async def activate_user(self, user_id: int) -> None:
        """Kullanıcıyı aktifleştir"""
        try:
            session = next(get_session())
            
            query = text("""
                UPDATE users 
                SET status = :status, is_active = TRUE, updated_at = NOW()
                WHERE user_id = :user_id
            """)
            
            session.execute(query, {
                "status": UserStatus.ACTIVE.value, 
                "user_id": user_id
            })
            
            session.commit()
            self.logger.info(f"Kullanıcı aktifleştirildi: {user_id}")
            
            # Önbelleği güncelle
            if user_id in self.user_cache:
                self.user_cache[user_id]["status"] = UserStatus.ACTIVE.value
                self.user_cache[user_id]["is_active"] = True
                
        except Exception as e:
            self.logger.error(f"Kullanıcı aktifleştirme hatası: {str(e)}", exc_info=True)
            raise
            
    async def block_user(self, user_id: int, reason: str = None) -> None:
        """Kullanıcıyı engelle"""
        try:
            session = next(get_session())
            
            query = text("""
                UPDATE users 
                SET status = :status, is_active = FALSE, updated_at = NOW(), notes = :reason
                WHERE user_id = :user_id
            """)
            
            session.execute(query, {
                "status": UserStatus.BLOCKED.value, 
                "user_id": user_id,
                "reason": reason or "Manuel engelleme"
            })
            
            session.commit()
            self.logger.info(f"Kullanıcı engellendi: {user_id}")
            
            # Önbelleği güncelle
            if user_id in self.user_cache:
                self.user_cache[user_id]["status"] = UserStatus.BLOCKED.value
                self.user_cache[user_id]["is_active"] = False
                
        except Exception as e:
            self.logger.error(f"Kullanıcı engelleme hatası: {str(e)}", exc_info=True)
            raise
            
    async def get_user_info(self, user_id: int) -> Dict[str, Any]:
        """Kullanıcı bilgilerini getir"""
        try:
            # Önce önbellekte kontrol et
            if user_id in self.user_cache:
                return self.user_cache[user_id]
                
            session = next(get_session())
            
            query = text("""
                SELECT username, phone, status, is_active, created_at, updated_at
                FROM users
                WHERE user_id = :user_id
            """)
            
            result = session.execute(query, {"user_id": user_id}).first()
            
            if not result:
                return {"error": "Kullanıcı bulunamadı"}
                
            user_info = {
                "username": result[0],
                "phone": result[1],
                "status": result[2],
                "is_active": result[3],
                "created_at": result[4],
                "updated_at": result[5]
            }
            
            # Önbelleğe ekle
            self.user_cache[user_id] = user_info
            
            return user_info
            
        except Exception as e:
            self.logger.error(f"Kullanıcı bilgisi getirme hatası: {str(e)}", exc_info=True)
            return {"error": str(e)}

    async def get_statistics(self) -> Dict[str, Any]:
        """Servis istatistiklerini getir"""
        return {
            "total_users": self.stats['total_users'],
            "active_users": self.stats['active_users'],
            "blocked_users": self.stats['blocked_users'],
            "last_update": self.stats['last_update'],
            "cache_size": len(self.user_cache)
        } 