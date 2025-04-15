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
import functools
from datetime import datetime
from typing import Dict, Any, List, Optional
import sqlite3
import inspect
import random

from telethon import errors
from bot.services.base_service import BaseService

logger = logging.getLogger(__name__)

class UserService(BaseService):
    """
    Kullanıcı veritabanı işlemlerini yöneten servis.
    """
    
    def __init__(self, client, config, db, stop_event=None):
        """
        UserService sınıfının başlatıcısı.
        
        Args:
            client: Telegram istemcisi
            config: Yapılandırma nesnesi
            db: Veritabanı nesnesi
            stop_event: Durdurma sinyali için event nesnesi
        """
        # BaseService.__init__ çağrısı eklendi - burada "user" adını belirtmek kritik
        super().__init__("user", client, config, db, stop_event)
        
        # Diğer özellikler...
        self.users = {}
        self.stats = {
            'total_users': 0,
            'new_users': 0,
            'active_users': 0
        }
        self.last_user_update = None
        self.user_cache = {}
        self.user_stats = {}
        self.cache_ttl = 3600  # 1 saat önbellek süresi
        self.registered_handlers = []  # Event handler'ları saklamak için liste
        self.cache_hit_ratio = 0.0
        self.error_count = 0
    
    def set_services(self, services):
        """
        Diğer servislere referansları ayarlar.
        
        Args:
            services: Servis adı -> Servis nesnesi eşleşmesi
        """
        self.services = services
        logger.debug(f"{self.name} servisi diğer servislere bağlandı")
        
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
        """
        from telethon import events
        
        # Önceki handlerlari temizle
        if hasattr(self, "registered_handlers") and self.registered_handlers:
            for handler in self.registered_handlers:
                try:
                    self.client.remove_event_handler(handler)
                except Exception:
                    pass
            self.registered_handlers = []
        else:
            self.registered_handlers = []
        
        # Yeni kullanıcı girişi
        handler = self.client.add_event_handler(
            self._handle_new_user,
            events.ChatAction(func=lambda e: e.user_joined or e.user_added)
        )
        self.registered_handlers.append(handler)
        
        # Diğer handlerleri ekleyin...
        
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
            
            # Kullanıcı entity'sini güvenli şekilde al
            user = None
            try:
                # Belirli bir süre içinde entity almayı dene - zaman aşımı ekle
                # PeerUser hatasına karşı ekstra önlem
                try:
                    user = await asyncio.wait_for(
                        event.client.get_entity(user_id),
                        timeout=5.0  # 5 saniyelik zaman aşımı
                    )
                except (ValueError, TypeError) as e:
                    if "Could not find the input entity for" in str(e) or "Cannot find any entity corresponding to" in str(e):
                        logger.warning(f"PeerUser entity bulunamadı, InputUserFromMessage ile deneniyor: {user_id}")
                        # Alternatif yöntem: InputUserFromMessage kullanarak dene
                        message = await event.get_message()
                        if message:
                            from telethon.tl.types import InputUserFromMessage
                            input_user = InputUserFromMessage(
                                peer=event.chat_id,
                                msg_id=message.id,
                                user_id=user_id
                            )
                            user = await event.client.get_entity(input_user)
                    else:
                        raise
            except asyncio.TimeoutError:
                logger.warning(f"Kullanıcı entity alma zaman aşımı: {user_id}")
            except (ValueError, errors.RPCError) as e:
                logger.warning(f"Kullanıcı entity alınamadı ({user_id}): {str(e)}")
                
                # Alternatif: Event'ten kullanıcı bilgisini al
                if hasattr(event, 'user') and event.user:
                    user = event.user
                    logger.info(f"Alternatif yöntem ile kullanıcı bilgisi alındı: {user_id}")
                else:
                    # Entity alınamadı ama yine de veritabanına temel bilgileri kaydedeceğiz
                    # En azından bir ID'ye sahibiz
                    if hasattr(self.db, 'add_user'):
                        user_data = {
                            'id': user_id,
                            'username': None,
                            'first_name': None,
                            'last_name': None,
                            'chat_id': chat_id,
                            'join_date': datetime.now(),
                            'entity_error': True  # Entity alma hatası olduğunu işaretle
                        }
                        
                        try:
                            # Geliştirilmiş bağlantı yönetimi ile veritabanı işlemini yap
                            await self._run_async_db_method(self.db.add_user, **user_data)
                            logger.info(f"Minimum kullanıcı bilgisi kaydedildi: {user_id}")
                        except sqlite3.OperationalError as db_err:
                            logger.error(f"Kullanıcı kaydedilemedi, veritabanı hatası: {str(db_err)}")
                        except Exception as e2:
                            logger.error(f"Kullanıcı ekleme hatası: {str(e2)}")
                        
                    # İstatistik güncelle
                    if user_id not in self.user_stats:
                        self.user_stats[user_id] = {'joins': 0, 'leaves': 0, 'messages': 0}
                    self.user_stats[user_id]['joins'] += 1
                    
                    return  # Entity alamadığımız için diğer işlemleri atlayalım
            
            # Bu noktada, user nesnesini başarıyla aldık veya alamadık
            if user:
                # Veritabanına kaydet
                if hasattr(self.db, 'add_user'):
                    user_data = {
                        'id': user_id,
                        'username': getattr(user, 'username', None),
                        'first_name': getattr(user, 'first_name', None),
                        'last_name': getattr(user, 'last_name', None),
                        'chat_id': chat_id,
                        'join_date': datetime.now()
                    }
                    
                    try:
                        # Geliştirilmiş bağlantı yönetimi ile veritabanı işlemini yap
                        await self._run_async_db_method(self.db.add_user, **user_data)
                    except sqlite3.OperationalError as db_err:
                        logger.error(f"Kullanıcı kaydedilemedi, veritabanı hatası: {str(db_err)}")
                    except Exception as e2:
                        logger.error(f"Kullanıcı ekleme hatası: {str(e2)}")
                
                # Önbelleğe ekle
                self.user_cache[user_id] = {
                    'username': getattr(user, 'username', None),
                    'first_name': getattr(user, 'first_name', None),
                    'last_name': getattr(user, 'last_name', None),
                    'cache_time': datetime.now()
                }
                
                # İstatistik güncelle
                if user_id not in self.user_stats:
                    self.user_stats[user_id] = {'joins': 0, 'leaves': 0, 'messages': 0}
                self.user_stats[user_id]['joins'] += 1
                
                # Gruplar arası iletişim
                await self._notify_services_new_user(user_id, getattr(user, 'username', None), chat_id)
                
                logger.info(f"Yeni kullanıcı: {user_id} (@{getattr(user, 'username', 'Bilinmiyor')}) -> {chat_id}")
            
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
        """
        self.running = False
        logger.info("User servisi durduruluyor...")
        
        # Event handler'ları kaldır
        if hasattr(self, 'registered_handlers'): 
            for handler in self.registered_handlers:
                self.client.remove_event_handler(handler)
            self.registered_handlers.clear()
        
        # İstatistikleri kaydet
        if hasattr(self.db, 'save_user_stats') and hasattr(self, 'user_stats'):
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

    async def _run_async_db_method(self, method, *args, **kwargs):
        """
        Veritabanı methodlarını asenkron bir şekilde çalıştırır ve kilitlenme sorunlarını yönetir.
        Geliştirilmiş bağlantı havuzu ile çalışır.
        
        Args:
            method: Çağrılacak veritabanı methodu
            *args, **kwargs: Methoda geçirilecek parametreler
            
        Returns:
            Methodun sonucunu döndürür
        """
        max_attempts = 5
        base_delay = 0.5  # saniye
        
        for attempt in range(max_attempts):
            try:
                if inspect.iscoroutinefunction(method):
                    result = await method(*args, **kwargs)
                else:
                    # Veritabanı yöneticisi doğrudan erişim sağlar, thread-safe
                    result = await self.loop.run_in_executor(
                        None, functools.partial(method, *args, **kwargs))
                return result
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_attempts - 1:
                    # Üstel geri çekilme stratejisi (exponential backoff)
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
                    logger.warning(f"DB kilitli (run_async), {attempt+1}/{max_attempts} deneme. {delay:.2f}s bekleniyor...")
                    await asyncio.sleep(delay)
                else:
                    if attempt == max_attempts - 1:
                        logger.error(f"Veritabanı kilitli hatası çözülemedi ({max_attempts} deneme sonrası)")
                    else:
                        logger.error(f"Veritabanı hatası: {str(e)}")
                    raise
            except Exception as e:
                logger.error(f"DB method çağrısı hatası: {str(e)}")
                raise
                
    async def process_user(self, user_id, action=None):
        """Bir kullanıcı ile ilgili işlem yapar"""
        try:
            # Önce cache'i kontrol et
            if user_id in self.user_cache:
                user_info = self.user_cache[user_id]
                # Entity almaya gerek yok, direkt işle
                if action and hasattr(self, f"_action_{action}"):
                    action_method = getattr(self, f"_action_{action}")
                    await action_method(user_id, user_info)
                return True
                
            # Güvenli entity alma işlemi
            try:
                # İlk olarak klasik yöntemi dene
                # Zaman aşımı ekle
                user_entity = await asyncio.wait_for(
                    self.client.get_entity(user_id), 
                    timeout=5.0
                )
            except asyncio.TimeoutError:
                logger.warning(f"Kullanıcı entity alma zaman aşımı: {user_id}")
                return False
            except ValueError:
                try:
                    # ID'den bulunamadıysa, veritabanından username kontrolü yap
                    if hasattr(self.db, 'get_user_by_id'):
                        # Veritabanı kilitlenme sorunlarına karşı retry mekanizması
                        for attempt in range(3):
                            try:
                                user_data = await self._run_async_db_method(self.db.get_user_by_id, user_id)
                                break
                            except sqlite3.OperationalError as db_err:
                                if "database is locked" in str(db_err) and attempt < 2:
                                    logger.warning(f"Veritabanı kilitli, {attempt+1}/3 deneme...")
                                    await asyncio.sleep(1 * (attempt + 1))
                                else:
                                    logger.error(f"Veritabanı hatası: {str(db_err)}")
                                    return False
                            except Exception as e2:
                                logger.error(f"Kullanıcı veri alma hatası: {str(e2)}")
                                return False
                        
                        if user_data and user_data.get('username'):
                            # Username ile dene
                            username = user_data.get('username')
                            try:
                                user_entity = await asyncio.wait_for(
                                    self.client.get_entity(f"@{username}"),
                                    timeout=5.0
                                )
                            except asyncio.TimeoutError:
                                logger.warning(f"Username ile entity alma zaman aşımı: @{username}")
                                return False
                            except Exception:
                                logger.warning(f"Username ile entity alınamadı: @{username}")
                                return False
                        else:
                            logger.warning(f"Kullanıcı bulunamadı: {user_id}")
                            # İsteğe bağlı: Bulunamayan kullanıcıyı veritabanında işaretleyebiliriz
                            if hasattr(self.db, 'mark_user_not_found'):
                                # Yeniden deneme mekanizması
                                for attempt in range(3):
                                    try:
                                        await self._run_async_db_method(self.db.mark_user_not_found, user_id)
                                        break
                                    except sqlite3.OperationalError as db_err:
                                        if "database is locked" in str(db_err) and attempt < 2:
                                            logger.warning(f"Veritabanı kilitli, {attempt+1}/3 deneme...")
                                            await asyncio.sleep(1 * (attempt + 1))
                                        else:
                                            logger.error(f"Veritabanı hatası: {str(db_err)}")
                                            break
                            return False
                    else:
                        logger.warning(f"Kullanıcı bulunamadı ve veritabanı metodu yok: {user_id}")
                        return False
                except Exception as e2:
                    logger.error(f"Entity alma hatası (alternatif yöntem): {str(e2)}")
                    return False
                    
            # Entity bulundu, işleme devam et
            username = user_entity.username if hasattr(user_entity, 'username') else None
            first_name = user_entity.first_name if hasattr(user_entity, 'first_name') else None
            last_name = user_entity.last_name if hasattr(user_entity, 'last_name') else None
            
            # Kullanıcı veritabanında yoksa ekle
            if hasattr(self.db, 'add_user'):
                # Yeniden deneme mekanizması
                for attempt in range(3):
                    try:
                        await self._run_async_db_method(
                            self.db.add_user, 
                            id=user_id,
                            username=username,
                            first_name=first_name,
                            last_name=last_name,
                            update_time=datetime.now()
                        )
                        break
                    except sqlite3.OperationalError as db_err:
                        if "database is locked" in str(db_err) and attempt < 2:
                            logger.warning(f"Veritabanı kilitli, {attempt+1}/3 deneme...")
                            await asyncio.sleep(1 * (attempt + 1))
                        else:
                            logger.error(f"Veritabanı hatası: {str(db_err)}")
                            break
                    except Exception as e2:
                        logger.error(f"Kullanıcı ekleme hatası: {str(e2)}")
                        break
            
            # Önbelleğe ekle
            self.user_cache[user_id] = {
                'username': username,
                'first_name': first_name,
                'last_name': last_name,
                'cache_time': datetime.now()
            }
            
            # Belirtilen aksiyonu gerçekleştir
            if action and hasattr(self, f"_action_{action}"):
                action_method = getattr(self, f"_action_{action}")
                await action_method(user_id, user_entity)
            
            return True
            
        except errors.FloodWaitError as e:
            wait_time = e.seconds
            logger.warning(f"Hız sınırı aşıldı, {wait_time} saniye bekleniyor")
            await asyncio.sleep(wait_time)
            # İsteğe bağlı: İşlemi tekrar deneyebiliriz
            return False
        except Exception as e:
            self.error_count += 1
            logger.error(f"Kullanıcı işleme hatası: {str(e)}")
            return False

    async def get_safe_entity(self, user_id, username=None):
        """
        Kullanıcı entity'sini güvenli bir şekilde almaya çalışır.
        Çeşitli yöntemleri dener ve başarısız olursa None döndürür.
        
        Args:
            user_id: Kullanıcı ID
            username: Kullanıcı adı (opsiyonel)
            
        Returns:
            User entity veya None
        """
        try:
            # Önce ID ile deneyelim
            try:
                # InputPeerUser kullanarak deneyelim
                try:
                    from telethon.tl.types import InputPeerUser, InputUser
                    return await self.client.get_entity(InputPeerUser(user_id, 0))
                except (ValueError, TypeError):
                    # Doğrudan ID ile deneyelim
                    return await self.client.get_entity(user_id)
            except (ValueError, errors.RPCError) as e:
                logger.debug(f"ID ile entity alınamadı: {user_id}, hata: {str(e)}")
                # ID ile bulunamadı, username ile deneyelim
                pass
                
            # Username ile deneyelim (eğer varsa)
            if username:
                try:
                    return await self.client.get_entity(f"@{username}")
                except (ValueError, errors.RPCError) as e:
                    logger.debug(f"Username ile entity alınamadı: @{username}, hata: {str(e)}")
                    # Username ile de bulunamadı
                    pass
                    
            # Veritabanında kayıtlı username ile deneyelim
            if hasattr(self.db, 'get_user_by_id'):
                try:
                    user_data = await self._run_async_db_method(self.db.get_user_by_id, user_id)
                    if user_data and user_data.get('username'):
                        try:
                            return await self.client.get_entity(f"@{user_data['username']}")
                        except (ValueError, errors.RPCError) as e:
                            logger.debug(f"DB'deki username ile entity alınamadı: @{user_data['username']}, hata: {str(e)}")
                            # Veritabanındaki username ile de bulunamadı
                            pass
                except Exception as db_err:
                    logger.debug(f"DB'den kullanıcı bilgisi alınırken hata: {str(db_err)}")
                
            # Son çare: Get dialogs üzerinden arama yapabilir
            try:
                async for dialog in self.client.iter_dialogs():
                    if dialog.id == user_id or (dialog.entity and hasattr(dialog.entity, 'id') and dialog.entity.id == user_id):
                        return dialog.entity
            except Exception as dialog_err:
                logger.debug(f"Dialog üzerinden entity arama hatası: {str(dialog_err)}")
                    
            # Hiçbir yöntem işe yaramadı
            logger.warning(f"Kullanıcı entity'sine erişilemedi: {user_id}/{username}")
            return None
            
        except Exception as e:
            logger.error(f"Entity alımı sırasında beklenmedik hata: {str(e)}")
            return None

    def get_user_count(self):
        """
        Veritabanındaki toplam kullanıcı sayısını döndürür.
        
        Returns:
            int: Toplam kullanıcı sayısı
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users")
            result = cursor.fetchone()
            return result[0] if result else 0
        except Exception as e:
            logger.error(f"Kullanıcı sayısı alınırken hata: {str(e)}")
            return 0