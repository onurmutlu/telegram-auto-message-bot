"""
# ============================================================================ #
# Dosya: user_service.py
# Yol: /Users/siyahkare/code/telegram-bot/bot/services/user_service.py
# İşlev: Kullanıcı yönetimi ve işlemleri için servis.
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from bot.services.base_service import BaseService

logger = logging.getLogger(__name__)

class UserService(BaseService):
    """
    Kullanıcı yönetimi ve işlemleri için servis.
    
    Bu servis, kullanıcı bilgilerini yönetmek, kullanıcı istatistiklerini
    toplamak ve kullanıcılarla ilgili işlemleri gerçekleştirmek için
    kullanılır.
    
    Attributes:
        user_cache: Önbelleğe alınmış kullanıcı bilgileri
        user_stats: Kullanıcı istatistikleri
    """
    
    def __init__(self, client: Any, config: Any, db: Any, stop_event: asyncio.Event):
        """
        UserService sınıfının başlatıcısı.
        
        Args:
            client: Telethon istemcisi
            config: Uygulama yapılandırması
            db: Veritabanı bağlantısı
            stop_event: Durdurma sinyali için asyncio.Event nesnesi
        """
        super().__init__("user", client, config, db, stop_event)
        
        # Kullanıcı önbelleği ve istatistikler
        self.user_cache: Dict[int, Dict] = {}
        self.user_stats: Dict[int, Dict] = {}
        self.cache_size = 100
        self.cache_ttl = 3600  # 1 saat
        
        # Telethon event handler'ları
        self.registered_handlers = []
        
        # Diğer servislere referans
        self.services = {}
        
    def set_services(self, services: Dict[str, Any]) -> None:
        """
        Diğer servislere referansları ayarlar.
        
        Args:
            services: Servis adı -> Servis nesnesi eşleşmesi
            
        Returns:
            None
        """
        self.services = services
        
    async def initialize(self) -> bool:
        """
        Servisi başlatmadan önce hazırlar.
        
        Returns:
            bool: Başarılı ise True
        """
        await super().initialize()
        
        # Kullanıcı istatistiklerini yükle
        if hasattr(self.db, 'get_user_stats'):
            stats = await self._run_async_db_method(self.db.get_user_stats)
            if stats:
                self.user_stats = stats
                
        # Event handler'larını kaydet
        self._register_event_handlers()
                
        return True
        
    def _register_event_handlers(self) -> None:
        """
        Telethon olay işleyicilerini kaydeder.
        
        Returns:
            None
        """
        from telethon import events
        
        # Yeni kullanıcı girişi
        handler = self.client.add_event_handler(
            self._handle_new_user,
            events.ChatAction(func=lambda e: e.user_joined or e.user_added)
        )
        self.registered_handlers.append(handler)
        
        # Kullanıcı çıkışı
        handler = self.client.add_event_handler(
            self._handle_user_left,
            events.ChatAction(func=lambda e: e.user_left or e.user_kicked)
        )
        self.registered_handlers.append(handler)
        
    async def run(self) -> None:
        """
        Servisin ana çalışma döngüsü.
        
        Returns:
            None
        """
        logger.info("User servisi çalışıyor")
        
        while self.running:
            if self.stop_event.is_set():
                break
                
            try:
                # Periyodik temizlik ve bakım
                self._cleanup_cache()
                
                # İstatistikleri kaydet
                if hasattr(self.db, 'save_user_stats'):
                    await self._run_async_db_method(self.db.save_user_stats, self.user_stats)
                    
            except Exception as e:
                logger.error(f"User servisi döngü hatası: {str(e)}")
                
            # 5 dakikada bir çalış
            await asyncio.sleep(300)
            
    async def _handle_new_user(self, event: Any) -> None:
        """
        Yeni kullanıcı girişi olayını işler.
        
        Args:
            event: Telethon olay nesnesi
            
        Returns:
            None
        """
        try:
            user_id = event.user_id
            chat_id = event.chat_id
            
            # Kullanıcı bilgisini al
            user = await event.client.get_entity(user_id)
            
            # Veritabanına kaydet
            if hasattr(self.db, 'add_user'):
                user_data = {
                    'id': user_id,
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'chat_id': chat_id,
                    'join_date': datetime.now()
                }
                
                await self._run_async_db_method(self.db.add_user, **user_data)
                
            # Önbelleğe ekle
            self.user_cache[user_id] = {
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'cache_time': datetime.now()
            }
            
            # İstatistik güncelle
            if user_id not in self.user_stats:
                self.user_stats[user_id] = {'joins': 0, 'leaves': 0, 'messages': 0}
            self.user_stats[user_id]['joins'] += 1
            
            # Gruplar arası iletişim
            await self._notify_services_new_user(user_id, user.username, chat_id)
            
            logger.info(f"Yeni kullanıcı: {user_id} (@{user.username}) -> {chat_id}")
            
        except Exception as e:
            logger.error(f"Yeni kullanıcı işleme hatası: {str(e)}")
            
    async def _handle_user_left(self, event: Any) -> None:
        """
        Kullanıcı çıkışı olayını işler.
        
        Args:
            event: Telethon olay nesnesi
            
        Returns:
            None
        """
        try:
            user_id = event.user_id
            chat_id = event.chat_id
            
            # Veritabanı güncelle
            if hasattr(self.db, 'update_user_left'):
                await self._run_async_db_method(
                    self.db.update_user_left,
                    user_id,
                    chat_id,
                    datetime.now()
                )
                
            # İstatistik güncelle
            if user_id not in self.user_stats:
                self.user_stats[user_id] = {'joins': 0, 'leaves': 0, 'messages': 0}
            self.user_stats[user_id]['leaves'] += 1
            
            logger.info(f"Kullanıcı ayrıldı: {user_id} -> {chat_id}")
            
        except Exception as e:
            logger.error(f"Kullanıcı çıkışı işleme hatası: {str(e)}")
            
    async def get_user_info(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Kullanıcı bilgilerini getirir.
        
        Args:
            user_id: Kullanıcı ID
            
        Returns:
            Optional[Dict]: Kullanıcı bilgileri
        """
        try:
            # Önbellekten kontrol et
            if user_id in self.user_cache:
                cache_entry = self.user_cache[user_id]
                if (datetime.now() - cache_entry['cache_time']).total_seconds() < self.cache_ttl:
                    return cache_entry
            
            # Veritabanından al
            if hasattr(self.db, 'get_user_info'):
                user_info = await self._run_async_db_method(self.db.get_user_info, user_id)
                if user_info:
                    # Önbelleğe ekle
                    self.user_cache[user_id] = {
                        **user_info,
                        'cache_time': datetime.now()
                    }
                    return user_info
            
            return None
        except Exception as e:
            logger.error(f"Kullanıcı bilgisi alınamadı: {str(e)}")
            return None
            
    def _cleanup_cache(self) -> None:
        """
        Önbelleği temizler.
        
        Returns:
            None
        """
        try:
            current_time = datetime.now()
            keys_to_remove = [
                user_id for user_id, cache_entry in self.user_cache.items()
                if (current_time - cache_entry['cache_time']).total_seconds() > self.cache_ttl
            ]
            for user_id in keys_to_remove:
                del self.user_cache[user_id]
        except Exception as e:
            logger.error(f"Önbellek temizleme hatası: {str(e)}")
            
    async def _notify_services_new_user(self, user_id: int, username: str, chat_id: int) -> None:
        """
        Diğer servisleri yeni bir kullanıcı hakkında bilgilendirir.
        
        Args:
            user_id: Kullanıcı ID
            username: Kullanıcı adı
            chat_id: Sohbet ID
            
        Returns:
            None
        """
        # DM servisini bilgilendir
        if 'dm' in self.services and hasattr(self.services['dm'], 'on_new_user'):
            try:
                await self.services['dm'].on_new_user(user_id=user_id, username=username, chat_id=chat_id)
            except Exception as e:
                logger.error(f"DM servisini bilgilendirme hatası: {str(e)}")
        
        # Group servisini bilgilendir
        if 'group' in self.services and hasattr(self.services['group'], 'on_new_user'):
            try:
                await self.services['group'].on_new_user(user_id=user_id, username=username, chat_id=chat_id)
            except Exception as e:
                logger.error(f"Group servisini bilgilendirme hatası: {str(e)}")
                
    async def stop(self) -> None:
        """
        Servisi güvenli bir şekilde durdurur.
        
        Returns:
            None
        """
        self.running = False
        logger.info("User servisi durduruluyor...")
        
        # Event handler'ları kaldır
        for handler in self.registered_handlers:
            self.client.remove_event_handler(handler)
        self.registered_handlers.clear()
        
        # İstatistikleri kaydet
        if hasattr(self.db, 'save_user_stats'):
            await self._run_async_db_method(self.db.save_user_stats, self.user_stats)
            
        await super().stop()
        
    async def get_status(self) -> Dict[str, Any]:
        """
        Servisin mevcut durumunu döndürür.
        
        Returns:
            Dict: Servis durum bilgileri
        """
        status = await super().get_status()
        status.update({
            'cache_size': len(self.user_cache),
            'stats_count': len(self.user_stats),
            'handlers_count': len(self.registered_handlers)
        })
        return status
        
    async def get_statistics(self) -> Dict[str, Any]:
        """
        Servisin istatistiklerini döndürür.
        
        Returns:
            Dict: Servis istatistikleri
        """
        # Bazı özet istatistikler hesapla
        total_joins = sum(stats['joins'] for stats in self.user_stats.values())
        total_leaves = sum(stats['leaves'] for stats in self.user_stats.values())
        total_messages = sum(stats.get('messages', 0) for stats in self.user_stats.values())
        
        return {
            'total_users': len(self.user_stats),
            'total_joins': total_joins,
            'total_leaves': total_leaves,
            'total_messages': total_messages,
            'cache_hit_ratio': self.cache_hit_ratio if hasattr(self, 'cache_hit_ratio') else 0
        }