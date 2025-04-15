"""
# ============================================================================ #
# Dosya: reply_service.py
# Yol: /Users/siyahkare/code/telegram-bot/bot/services/reply_service.py
# İşlev: Telegram botunun mesajlara otomatik yanıt vermesini yöneten servis.
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

import asyncio
import json
import logging
import random
import functools
from datetime import datetime
from typing import Dict, Any, List
from telethon import events, utils, errors

from bot.services.base_service import BaseService

logger = logging.getLogger(__name__)

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
    
    def __init__(self, client: Any, config: Any, db: Any, stop_event: asyncio.Event):
        """
        ReplyService sınıfının başlatıcısı.
        
        Args:
            client: Telethon istemcisi
            config: Uygulama yapılandırması
            db: Veritabanı bağlantısı
            stop_event: Durdurma sinyali için asyncio.Event nesnesi
        """
        super().__init__("reply", client, config, db, stop_event)
        
        # Yanıt şablonlarını yükle
        with open('data/responses.json', 'r', encoding='utf-8') as f:
            self.responses = json.load(f)
            
        self.reply_count = 0
        self.mention_stats: Dict[int, int] = {}  # chat_id -> mention sayısı
        self.services = {}  # Diğer servislere referans
        
    def set_services(self, services: Dict[str, Any]) -> None:
        """
        Diğer servislere referansları ayarlar.
        
        Args:
            services: Servis adı -> Servis nesnesi eşleşmesi
        """
        self.services = services
        logger.debug(f"{self.name} servisi diğer servislere bağlandı")
        
    async def initialize(self) -> bool:
        """
        ReplyService servisini başlatır.
        """
        # Temel servisi başlat
        await super().initialize()
        
        # Bot modu kontrolünü kaldır, hep UserBot olarak kabul et
        self._is_user_mode = True
        logger.info("✅ Yanıt servisi kullanıcı hesabı ile çalışıyor, tüm özellikler etkin.")
        
        # Mention istatistiklerini yükle
        if hasattr(self.db, 'get_mention_stats'):
            stats = await self._run_async_db_method(self.db.get_mention_stats)
            if stats:
                self.mention_stats = stats
                
        # Telethon event handler'larını kaydet
        self.client.add_event_handler(
            self.handle_new_message,
            events.NewMessage
        )
        
        return True
        
    async def run(self) -> None:
        """
        Servisin ana çalışma döngüsü. Bu servis için sadece event'leri dinler.
        
        Returns:
            None
        """
        logger.info("Reply servisi çalışıyor - event dinleme modunda")
        
        # Bu servis aktif çalışma döngüsü olmadan sadece event'leri dinler
        while self.running:
            if self.stop_event.is_set():
                break
                
            # Her 60 saniyede bir istatistikleri güncelle
            await asyncio.sleep(60)
            
            # İstatistikleri kaydet
            if hasattr(self.db, 'save_mention_stats'):
                await self._run_async_db_method(self.db.save_mention_stats, self.mention_stats)
                
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
                
            # Bot mention edildi mi kontrol et
            if event.message.mentioned:
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
                logger.info(f"Mention yanıtı gönderildi: {chat_id}")
                
                # Kişiye DM atmayı dene - güvenli metodla
                try:
                    await self._try_send_dm_to_user(event.sender)
                except Exception as dm_err:
                    logger.debug(f"DM gönderim hatası (önemsiz): {str(dm_err)}")
                    
        except errors.FloodWaitError as e:
            wait_time = e.seconds
            logger.warning(f"FloodWaitError mention yanıtı gönderirken: {wait_time} saniye bekleniyor")
            if hasattr(self, 'rate_limiter') and hasattr(self.rate_limiter, 'register_error'):
                self.rate_limiter.register_error(e)
            await asyncio.sleep(wait_time + 1)
        except Exception as e:
            logger.error(f"Mention işleme hatası: {str(e)}")

    # Entity hatalarına karşı _try_send_dm_to_user metodunu güçlendirin
    async def _try_send_dm_to_user(self, user):
        """Mention yapan kullanıcıya DM ile ulaşmayı dener."""
        if not user or not hasattr(self, 'services') or 'dm' not in self.services:
            return
            
        try:
            # DÜZELTME: Entity bilgilerini tam olarak al
            user_id = user.id
            username = getattr(user, 'username', None)
            first_name = getattr(user, 'first_name', None)
            
            # DM servisinin güvenli entity alma yöntemini kullan
            dm_service = self.services.get('dm')
            if dm_service and hasattr(dm_service, 'get_safe_entity'):
                entity = await dm_service.get_safe_entity(user_id, username)
                if not entity:
                    logger.debug(f"DM için entity bulunamadı: {user_id}/{username}")
                    return
            
            # Kullanıcı verisi oluştur
            user_data = {
                "user_id": user_id,
                "username": username,
                "first_name": first_name,
                "entity": entity  # Entity nesnesini de geçir
            }
            
            # İşleme devam et...
        except Exception as e:
            logger.debug(f"DM gönderme hatası: {str(e)}")
            
    async def _handle_command(self, event: Any) -> None:
        """
        Bot komutlarını işler.
        
        Args:
            event: Telethon mesaj olayı
            
        Returns:
            None
        """
        text = event.message.text
        command = text.split()[0][1:].lower()  # /command -> command
        
        # Komutları işle
        if command == 'help' or command == 'yardim':
            await self._send_help_message(event)
        elif command == 'hakkinda' or command == 'about':
            await self._send_about_message(event)
        elif command == 'stats' or command == 'istatistik':
            await self._send_stats_message(event)
            
    def _select_response(self, response_type: str) -> str:
        """
        Belirtilen tipteki yanıt şablonlarından birini rastgele seçer.
        
        Args:
            response_type: Yanıt tipi ('mention', 'greeting', vb.)
            
        Returns:
            str: Seçilen yanıt şablonu
        """
        if response_type in self.responses and self.responses[response_type]:
            return random.choice(self.responses[response_type])
        return "👋"
        
    async def _should_reply_to_mention(self, chat_id: int, user_id: int) -> bool:
        """
            user_id: Kullanıcı ID
            
        Returns:
            bool: Yanıt verilmeli ise True
        """
        # Bazı spam kontrolü yapabilirsiniz
        # Örneğin: Son 1 saatte aynı kullanıcıdan çok fazla mention geldiyse yanıtlamayı durdur
        
        # Örnek uygulama: %80 ihtimalle yanıt ver
        return random.random() < 0.8
        
    async def _send_help_message(self, event: Any) -> None:
        """
        Yardım mesajını gönderir.
        
        Args:
            event: Telethon mesaj olayı
            
        Returns:
            None
        """
        help_text = (
            "🤖 **Bot Komutları**\n\n"
            "/yardim veya /help - Bu mesajı gösterir\n"
            "/hakkinda veya /about - Bot hakkında bilgi\n"
            "/istatistik veya /stats - Bot istatistiklerini gösterir"
        )
        await event.reply(help_text)
        
    async def _send_about_message(self, event: Any) -> None:
        """
        Bot hakkında bilgi mesajını gönderir.
        
        Args:
            event: Telethon mesaj olayı
            
        Returns:
            None
        """
        about_text = (
            "🤖 **Bot Hakkında**\n\n"
            "Bu bot, otomatik olarak gruplarda etkileşime geçer ve gelen "
            "mention'lara yanıt verir. Ayrıca özel davet ve tanıtım "
            "mesajları da gönderebilir."
        )
        await event.reply(about_text)
        
    async def _send_stats_message(self, event: Any) -> None:
        """
        Bot istatistiklerini gönderir.
        
        Args:
            event: Telethon mesaj olayı
            
        Returns:
            None
        """
        stats_text = (
            "📊 **Bot İstatistikleri**\n\n"
            f"Yanıtlanan mention sayısı: {self.reply_count}\n"
        )
        
        # Diğer servislerden istatistik topla
        if 'group' in self.services:
            group_stats = await self.services['group'].get_statistics()
            stats_text += f"\nToplam gönderilen grup mesajı: {group_stats.get('total_sent', 0)}\n"
            
        if 'dm' in self.services:
            dm_stats = await self.services['dm'].get_statistics()
            stats_text += f"Toplam gönderilen özel mesaj: {dm_stats.get('total_sent', 0)}\n"
            
        await event.reply(stats_text)
        
    async def stop(self) -> None:
        """
        Servisi güvenli bir şekilde durdurur.
        
        Returns:
            None
        """
        self.running = False
        logger.info("Reply servisi durduruluyor...")
        
        # Event handler'ları kaldır
        self.client.remove_event_handler(self.handle_new_message)
        
        # İstatistikleri kaydet
        if hasattr(self.db, 'save_mention_stats'):
            await self._run_async_db_method(self.db.save_mention_stats, self.mention_stats)
            
        await super().stop()
        
    async def get_status(self) -> Dict[str, Any]:
        """
        Servisin mevcut durumunu döndürür.
        
        Returns:
            Dict: Servis durum bilgileri
        """
        status = await super().get_status()
        status.update({
            'reply_count': self.reply_count,
            'mention_stats_count': len(self.mention_stats)
        })
        return status
        
    async def get_statistics(self) -> Dict[str, Any]:
        """
        Servisin istatistiklerini döndürür.
        
        Returns:
            Dict: Servis istatistikleri
        """
        return {
            'reply_count': self.reply_count,
            'mention_stats': dict(self.mention_stats)  # Kopyasını oluştur
        }

    async def _run_async_db_method(self, method, *args, **kwargs):
        """Veritabanı metodunu thread-safe biçimde çalıştırır."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, 
            functools.partial(method, *args, **kwargs)
        )
