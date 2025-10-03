"""
Telegram Bot Yanıt Servisi

Telegram botunun mesajlara otomatik yanıt vermesini yöneten servis.
"""

import asyncio
import json
import random
import functools
from datetime import datetime
from typing import Dict, Any, List, Optional
from telethon import events, utils, errors

from app.services.base_service import BaseService
from app.core.logger import get_logger

logger = get_logger(__name__)

class ReplyService(BaseService):
    """
    Gelen mesajlara otomatik yanıt vermeyi yöneten servis.
    
    Bu servis, bota gelen mesajları izler ve belirli kurallara göre
    otomatik yanıt verir. Özellikle bot mention'larını ve özel komutları
    işlemekten sorumludur.
    
    Attributes:
        responses: Yanıt şablonları
        reply_count: Gönderilen yanıt sayısı
        mention_stats: Mention istatistikleri
    """
    
    service_name = "reply_service"
    default_interval = 60  # 60 saniye
    
    def __init__(self, **kwargs):
        """
        ReplyService sınıfının başlatıcısı.
        
        Args:
            **kwargs: Temel servis parametreleri
        """
        super().__init__(**kwargs)
        
        # Çalışma durumu
        self.running = False
        
        # Yanıt şablonlarını yükle
        try:
            with open('data/responses.json', 'r', encoding='utf-8') as f:
                self.responses = json.load(f)
        except FileNotFoundError:
            logger.warning("responses.json dosyası bulunamadı, varsayılan yanıtlar kullanılacak")
            self.responses = {
                "flirty": ["Merhaba!", "Nasılsın?", "Size nasıl yardımcı olabilirim?"],
                "help": ["Yardım mesajı buraya gelecek"],
                "about": ["Hakkında bilgisi buraya gelecek"]
            }
            
        self.reply_count = 0
        self.mention_stats: Dict[int, int] = {}  # chat_id -> mention sayısı
        self.services = {}  # Diğer servislere referans
        self.replies = {}
        self.keywords = {}
        self.last_update = datetime.now()
        self.stats = {
            'total_replies': 0,
            'last_reply': None
        }
        
        # Telegram istemcisi için event handler'ları
        self.handlers = []
        
        # Durum değişkenleri
        self.is_running = False
        self.is_paused = False
        
    async def _start(self) -> bool:
        """
        ReplyService servisini başlatır.
        
        Returns:
            bool: Başlatma başarılıysa True
        """
        try:
            logger.info("Yanıt servisi başlatılıyor")
            
            # Bot modu kontrolünü kaldır, hep UserBot olarak kabul et
            self._is_user_mode = True
            logger.info("✅ Yanıt servisi kullanıcı hesabı ile çalışıyor, tüm özellikler etkin.")
            
            # Mention istatistiklerini yükle
            if hasattr(self.db, 'get_mention_stats'):
                stats = await self._run_async_db_method(self.db.get_mention_stats)
                if stats:
                    self.mention_stats = stats
                    
            # Telethon event handler'larını kaydet
            if self.client:
                self.client.add_event_handler(
                    self.handle_new_message,
                    events.NewMessage
                )
            
            # Yanıtları ve anahtar kelimeleri yükle
            await self._load_replies()
            await self._load_keywords()
            
            logger.info("Yanıt servisi başlatıldı")
            return True
            
        except Exception as e:
            logger.exception(f"Yanıt servisi başlatma hatası: {str(e)}")
            return False
            
    async def _stop(self) -> bool:
        """
        Yanıt servisini durdurur.
        
        Returns:
            bool: Durdurma başarılıysa True
        """
        try:
            logger.info("Yanıt servisi durduruluyor")
            
            # Event handler'ları kaldır
            if self.client:
                for handler in self.handlers:
                    self.client.remove_event_handler(handler)
                    
                # Özel olarak NewMessage handler'ını kaldır
                try:
                    self.client.remove_event_handler(self.handle_new_message)
                except Exception:
                    pass
                    
            # İstatistikleri kaydet
            if hasattr(self.db, 'save_mention_stats'):
                await self._run_async_db_method(self.db.save_mention_stats, self.mention_stats)
                
            logger.info("Yanıt servisi durduruldu")
            return True
            
        except Exception as e:
            logger.exception(f"Yanıt servisi durdurma hatası: {str(e)}")
            return False
            
    async def _update(self) -> None:
        """
        Periyodik güncelleme işlemleri.
        """
        try:
            # İstatistikleri kaydet
            if hasattr(self.db, 'save_mention_stats'):
                await self._run_async_db_method(self.db.save_mention_stats, self.mention_stats)
                
        except Exception as e:
            logger.exception(f"Yanıt servisi güncelleme hatası: {str(e)}")
                
    async def handle_new_message(self, event: Any) -> None:
        """
        Yeni mesaj olayını işler.
        
        Args:
            event: Telethon mesaj olayı
            
        Returns:
            None
        """
        try:
            if not event.message or not event.message.text:
                return
            # Eğer mesaj bir yanıt ise ve sohbet açıcıya cevap ise
            if event.message.reply_to_msg_id:
                try:
                    orig_msg = await event.client.get_messages(event.chat_id, ids=event.message.reply_to_msg_id)
                    with open('data/messages.json', 'r', encoding='utf-8') as f:
                        messages = json.load(f)
                    sohbet_acici_list = messages.get('sohbet_acici', [])
                    if orig_msg.text and orig_msg.text.strip() in sohbet_acici_list:
                        with open('data/responses.json', 'r', encoding='utf-8') as f:
                            responses = json.load(f)
                        reply_list = responses.get('sohbet_acici_reply', [])
                        if reply_list:
                            yanit = random.choice(reply_list)
                            await event.reply(yanit)
                            logger.info(f"Sohbet açıcıya otomatik yanıt gönderildi: {yanit}")
                            return
                except Exception as e:
                    logger.warning(f"Sohbet açıcı yanıtı kontrolünde hata: {e}")
            # Bot mention edildi mi kontrol et
            if event.message.mentioned:
                # DM'e yönlendirici yanıtlar
                try:
                    with open('data/responses.json', 'r', encoding='utf-8') as f:
                        responses = json.load(f)
                    dm_yonlendirici = responses.get('sohbet_acici_reply', [])
                    if dm_yonlendirici:
                        yanit = random.choice(dm_yonlendirici)
                        await event.reply(yanit)
                        logger.info(f"Mention'a DM yönlendirici yanıt gönderildi: {yanit}")
                        return
                except Exception as e:
                    logger.warning(f"Mention DM yanıtı kontrolünde hata: {e}")
                # Eski flirty yanıtı fallback
                await self._handle_mention(event)
            # Özel komutları kontrol et
            elif event.message.text.startswith('/'):
                await self._handle_command(event)
        except Exception as e:
            logger.error(f"Yeni mesaj işleme hatası: {str(e)}")
            
    async def _handle_mention(self, event):
        """Bot mention'larını işler."""
        try:
            chat_id = event.chat_id
            sender_id = event.sender_id
            
            # Mention istatistiklerini güncelle
            if chat_id not in self.mention_stats:
                self.mention_stats[chat_id] = 0
            self.mention_stats[chat_id] += 1
            
            # Yanıt vermek için uygun mu kontrol et
            should_reply = await self._should_reply_to_mention(chat_id, sender_id)
            
            if should_reply:
                # Flirty yanıtları seç - flirty tipi yanıt
                response = self._select_response('flirty')
                
                # Rate limiting kontrolü (get_wait_time metodu yoksa)
                if hasattr(self, 'rate_limiter'):
                    # get_wait_time metodunu güvenli şekilde kullan
                    if hasattr(self.rate_limiter, 'get_wait_time'):
                        wait_time = self.rate_limiter.get_wait_time()
                        if wait_time > 0:
                            logger.debug(f"Rate limit nedeniyle {wait_time:.1f} saniye bekleniyor")
                            await asyncio.sleep(wait_time)
                    else:
                        # Alternatif yöntem - yalnızca işlem yapılabilir mi kontrolü
                        can_execute = True
                        if hasattr(self.rate_limiter, 'can_execute'):
                            can_execute = self.rate_limiter.can_execute()
                        
                        if not can_execute:
                            logger.debug("Rate limit nedeniyle işlem yapılamıyor")
                            await asyncio.sleep(1)  # En az 1 saniye bekle
                
                # Yanıtı gönder
                await event.reply(response)
                
                # Rate limiter'ı güncelle (varsa)
                if hasattr(self, 'rate_limiter') and hasattr(self.rate_limiter, 'mark_used'):
                    self.rate_limiter.mark_used()
                
                # İstatistikleri güncelle    
                self.reply_count += 1
                self.stats['total_replies'] += 1
                self.stats['last_reply'] = datetime.now().isoformat()
                
        except Exception as e:
            logger.error(f"Mention işleme hatası: {str(e)}")
            
    async def _try_send_dm_to_user(self, user):
        """
        Kullanıcıya DM göndermeyi dener.
        
        Args:
            user: Kullanıcı ID veya username
            
        Returns:
            bool: Başarılıysa True
        """
        try:
            if not self.client:
                return False
                
            if not user:
                return False
                
            # DM servisi varsa onu kullan
            if 'dm_service' in self.services:
                dm_service = self.services['dm_service']
                if hasattr(dm_service, 'send_message'):
                    await dm_service.send_message(user, "Merhaba! Beni mention ettiğin için teşekkürler.")
                    return True
                    
            # Doğrudan mesaj gönder
            await self.client.send_message(user, "Merhaba! Beni mention ettiğin için teşekkürler.")
            return True
            
        except Exception as e:
            logger.error(f"DM gönderme hatası: {str(e)}")
            return False
            
    async def _handle_command(self, event: Any) -> None:
        """
        Komut mesajlarını işler.
        
        Args:
            event: Telethon mesaj olayı
            
        Returns:
            None
        """
        text = event.message.text.lower()
        
        if text.startswith('/help'):
            await self._send_help_message(event)
        elif text.startswith('/about'):
            await self._send_about_message(event)
        elif text.startswith('/stats'):
            await self._send_stats_message(event)
            
    def _select_response(self, response_type: str) -> str:
        """
        Belirli bir tipteki yanıtlardan rasgele birini seçer.
        
        Args:
            response_type: Yanıt tipi
            
        Returns:
            str: Seçilen yanıt
        """
        if response_type in self.responses and self.responses[response_type]:
            # Rasgele bir yanıt seç
            return random.choice(self.responses[response_type])
        else:
            # Varsayılan yanıt
            return "Merhaba! Size nasıl yardımcı olabilirim?"
            
    async def _should_reply_to_mention(self, chat_id: int, user_id: int) -> bool:
        """
        Bir mention'a yanıt verilip verilmeyeceğini belirler.
        
        Args:
            chat_id: Sohbet ID
            user_id: Kullanıcı ID
            
        Returns:
            bool: Yanıt verilmesi gerekiyorsa True
        """
        # Basit bir şekilde her zaman yanıt ver
        # Gerçek uygulamada burada daha karmaşık bir mantık olabilir
        return True
        
    async def _send_help_message(self, event: Any) -> None:
        """
        Yardım mesajını gönderir.
        
        Args:
            event: Telethon mesaj olayı
            
        Returns:
            None
        """
        try:
            help_message = """
**Komutlar:**
/help - Bu yardım mesajını gösterir
/about - Bot hakkında bilgi verir
/stats - İstatistikleri gösterir
            """
            await event.reply(help_message)
        except Exception as e:
            logger.error(f"Yardım mesajı gönderme hatası: {str(e)}")
            
    async def _send_about_message(self, event: Any) -> None:
        """
        Hakkında mesajını gönderir.
        
        Args:
            event: Telethon mesaj olayı
            
        Returns:
            None
        """
        try:
            about_message = """
**Telegram Bot Platform**
Sürüm: 1.0.0
Geliştirici: SiyahKare Yazılım
            """
            await event.reply(about_message)
        except Exception as e:
            logger.error(f"Hakkında mesajı gönderme hatası: {str(e)}")
            
    async def _send_stats_message(self, event: Any) -> None:
        """
        İstatistik mesajını gönderir.
        
        Args:
            event: Telethon mesaj olayı
            
        Returns:
            None
        """
        try:
            stats_message = f"""
**Bot İstatistikleri:**
Toplam yanıt sayısı: {self.reply_count}
Aktif sohbet sayısı: {len(self.mention_stats)}
            """
            
            # Diğer servislerden istatistik topla
            if 'user_service' in self.services:
                user_count = await self.services['user_service'].get_user_count()
                stats_message += f"Kullanıcı sayısı: {user_count}\n"
                
            if 'group_service' in self.services:
                group_count = await self.services['group_service'].get_group_count()
                stats_message += f"Grup sayısı: {group_count}\n"
                
            await event.reply(stats_message)
        except Exception as e:
            logger.error(f"İstatistik mesajı gönderme hatası: {str(e)}")
            
    async def _load_replies(self):
        """
        Veritabanından özel yanıtları yükler.
        """
        try:
            if hasattr(self.db, 'get_replies'):
                replies = await self._run_async_db_method(self.db.get_replies)
                if replies:
                    self.replies = replies
                    logger.info(f"{len(replies)} özel yanıt yüklendi")
        except Exception as e:
            logger.error(f"Yanıtları yükleme hatası: {str(e)}")
            
    async def _load_keywords(self):
        """
        Veritabanından anahtar kelimeleri yükler.
        """
        try:
            if hasattr(self.db, 'get_keywords'):
                keywords = await self._run_async_db_method(self.db.get_keywords)
                if keywords:
                    self.keywords = keywords
                    logger.info(f"{len(keywords)} anahtar kelime yüklendi")
        except Exception as e:
            logger.error(f"Anahtar kelimeleri yükleme hatası: {str(e)}")
            
    async def get_reply(self, message_text):
        """
        Verilen mesaja uygun yanıtı bulur.
        
        Args:
            message_text: Mesaj metni
            
        Returns:
            str: Uygun yanıt veya None
        """
        # Mesajı küçült
        lower_text = message_text.lower()
        
        # Her anahtar kelimeyi kontrol et
        for keyword, reply in self.keywords.items():
            if keyword.lower() in lower_text:
                return reply
                
        return None
        
    async def add_reply(self, reply_data):
        """
        Yeni bir yanıt ekler.
        
        Args:
            reply_data: Yanıt verisi
            
        Returns:
            bool: Başarılıysa True
        """
        try:
            if not reply_data or 'text' not in reply_data:
                return False
                
            if hasattr(self.db, 'add_reply'):
                reply_id = await self._run_async_db_method(self.db.add_reply, reply_data)
                
                if reply_id:
                    # Bellek içindeki yanıtları güncelle
                    reply_data['id'] = reply_id
                    self.replies[reply_id] = reply_data
                    logger.info(f"Yeni yanıt eklendi: {reply_id}")
                    return True
                    
            return False
            
        except Exception as e:
            logger.error(f"Yanıt ekleme hatası: {str(e)}")
            return False
            
    async def update_reply(self, reply_id, reply_data):
        """
        Bir yanıtı günceller.
        
        Args:
            reply_id: Yanıt ID'si
            reply_data: Yanıt verisi
            
        Returns:
            bool: Başarılıysa True
        """
        try:
            if not reply_id or not reply_data:
                return False
                
            if hasattr(self.db, 'update_reply'):
                result = await self._run_async_db_method(self.db.update_reply, reply_id, reply_data)
                
                if result:
                    # Bellek içindeki yanıtları güncelle
                    if reply_id in self.replies:
                        self.replies[reply_id].update(reply_data)
                    else:
                        reply_data['id'] = reply_id
                        self.replies[reply_id] = reply_data
                        
                    logger.info(f"Yanıt güncellendi: {reply_id}")
                    return True
                    
            return False
            
        except Exception as e:
            logger.error(f"Yanıt güncelleme hatası: {str(e)}")
            return False
            
    async def delete_reply(self, reply_id):
        """
        Bir yanıtı siler.
        
        Args:
            reply_id: Yanıt ID'si
            
        Returns:
            bool: Başarılıysa True
        """
        try:
            if not reply_id:
                return False
                
            if hasattr(self.db, 'delete_reply'):
                result = await self._run_async_db_method(self.db.delete_reply, reply_id)
                
                if result:
                    # Bellek içindeki yanıtı sil
                    if reply_id in self.replies:
                        del self.replies[reply_id]
                    logger.info(f"Yanıt silindi: {reply_id}")
                    return True
                    
            return False
            
        except Exception as e:
            logger.error(f"Yanıt silme hatası: {str(e)}")
            return False
            
    async def get_status(self) -> Dict[str, Any]:
        """
        Servis durum bilgilerini döndürür.
        
        Returns:
            Dict[str, Any]: Durum bilgileri
        """
        return {
            'service': 'reply',
            'running': self.is_running,
            'paused': self.is_paused,
            'reply_count': self.reply_count,
            'mention_stats_count': len(self.mention_stats),
            'replies_count': len(self.replies),
            'keywords_count': len(self.keywords)
        }
        
    async def get_statistics(self) -> Dict[str, Any]:
        """
        Servis istatistiklerini döndürür.
        
        Returns:
            Dict[str, Any]: İstatistik bilgileri
        """
        return {
            'total_replies': self.stats['total_replies'],
            'last_reply': self.stats['last_reply'],
            'mention_stats': self.mention_stats
        }
        
    async def _run_async_db_method(self, method, *args, **kwargs):
        """
        Asenkron veritabanı metodunu çalıştırır.
        
        Args:
            method: Çalıştırılacak metod
            *args: Argümanlar
            **kwargs: Anahtar kelime argümanları
            
        Returns:
            Any: Metod sonucu
        """
        try:
            if asyncio.iscoroutinefunction(method):
                return await method(*args, **kwargs)
            else:
                # Senkron metodu ThreadPoolExecutor içinde çalıştır
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None,
                    functools.partial(method, *args, **kwargs)
                )
        except Exception as e:
            logger.error(f"Veritabanı metodu çalıştırma hatası: {str(e)}")
            return None 