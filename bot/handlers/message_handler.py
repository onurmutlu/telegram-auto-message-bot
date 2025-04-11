"""
# ============================================================================ #
# Dosya: message_handler.py
# Yol: /Users/siyahkare/code/telegram-bot/bot/handlers/message_handler.py
# İşlev: Telegram bot için genel mesaj işleme ve analizi.
#
# Amaç: Bu modül, Telegram botunun gelen mesajlarını analiz eder, kategorize eder,
# ve uygun yanıtlar oluşturur. ServiceManager ile entegre çalışır ve istatistik
# verisi toplar. Çeşitli mesaj türleri için özel işleyiciler içerir.
#
# Temel Özellikler:
# - Mesaj içeriği analizi ve kategorilendirme
# - Spam koruması ve rate limiting
# - Otomatik yanıt mekanizması
# - Medya mesajları için özel işleme
# - Asenkron işlem desteği
# - Kapsamlı loglama ve izleme
# - ServiceManager ile uyumlu yaşam döngüsü
#
# Build: 2025-04-08-23:30:00
# Versiyon: v3.5.0
# ============================================================================ #
#
# Değişiklik Geçmişi:
# v3.5.0 (2025-04-08) - ServiceManager ile uyumlu hale getirildi
#                      - Yaşam döngüsü metodları eklendi (initialize, start, stop)
#                      - Asenkron işlem desteği eklendi
#                      - Farklı mesaj türleri için işleyiciler geliştirildi
#                      - İstatistik toplama ve durum izleme eklendi
#                      - Adaptif rate limiter entegrasyonu
#                      - Mesaj analiz algoritması geliştirildi
# v3.4.0 (2025-04-01) - İlk kapsamlı versiyon
# v3.3.0 (2025-03-15) - İlk sürüm
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

import logging
import random
import time
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional, Set, Union, Tuple
from enum import Enum

from telethon import events, errors
from colorama import Fore, Style, init

from bot.utils.rate_limiter import RateLimiter
from bot.utils.adaptive_rate_limiter import AdaptiveRateLimiter

# Initialize colorama
init(autoreset=True)

logger = logging.getLogger(__name__)

class MessageType(Enum):
    """Mesaj türlerini tanımlayan enum sınıfı."""
    TEXT = "text"
    MEDIA = "media"
    STICKER = "sticker"
    DOCUMENT = "document"
    PHOTO = "photo"
    VIDEO = "video"
    VOICE = "voice"
    CONTACT = "contact"
    LOCATION = "location"
    UNKNOWN = "unknown"

class MessageHandler:
    """
    Telegram bot için genel mesaj işleme sınıfı.
    
    Bu sınıf, gelen mesajları işler, analiz eder ve uygun yanıtlar oluşturur.
    ServiceManager ile entegre çalışabilir ve çeşitli mesaj türleri için
    özelleştirilmiş işleyiciler içerir.
    
    Attributes:
        bot: Ana bot nesnesi
        rate_limiter: Basit rate limiter
        adaptive_limiter: Adaptif rate limiter
        is_running: Servisin çalışıp çalışmadığını belirten bayrak
        is_paused: Servisin duraklatılmış olup olmadığını belirten bayrak
        stop_event: Servisin durdurulması için kullanılan Event nesnesi
        stats: İstatistik verileri
        processed_messages: İşlenen mesajlar hakkında bilgi tutan sözlük
        last_processed_time: Son mesaj işleme zamanı
    """
    
    def __init__(self, bot, stop_event=None):
        """
        MessageHandler sınıfının başlatıcı metodu.
        
        Args:
            bot: Bağlı olduğu bot nesnesi
            stop_event: Durdurma sinyali için Event nesnesi (opsiyonel)
        """
        self.bot = bot
        
        # Rate limiter yapılandırması
        self.rate_limiter = RateLimiter(max_requests=10, time_window=30)
        self.adaptive_limiter = AdaptiveRateLimiter(
            initial_rate=15,      # Başlangıç hızı (dakikada istek)
            initial_period=60,    # Başlangıç periyodu (saniye)
            error_backoff=1.2,    # Hata durumunda yavaşlama çarpanı
            max_jitter=1.0        # Maksimum rastgele gecikme (saniye)
        )
        
        # Durum değişkenleri
        self.is_running = False
        self.is_paused = False
        self.stop_event = stop_event or asyncio.Event()
        
        # İstatistik ve izleme
        self.stats = {
            "total_processed": 0,
            "text_messages": 0,
            "media_messages": 0,
            "sticker_messages": 0,
            "error_count": 0,
            "start_time": None,
            "last_activity": None
        }
        
        # İşlem izleme
        self.processed_messages = {}
        self.last_processed_time = datetime.now()
        
        # Log seviyesi
        logger.setLevel(logging.INFO)
        
        logger.info("MessageHandler başlatıldı")
    
    async def initialize(self) -> bool:
        """
        Mesaj işleyiciyi başlatmak için gerekli hazırlıkları yapar.
        
        Returns:
            bool: Başarılı ise True
        """
        try:
            # İstatistikleri sıfırla
            self.stats["start_time"] = datetime.now()
            self.stats["last_activity"] = datetime.now()
            
            # Mesaj şablonlarını veya diğer verileri buradan yükle
            
            logger.info("MessageHandler başarıyla initialize edildi")
            return True
            
        except Exception as e:
            logger.error(f"MessageHandler initialize hatası: {str(e)}", exc_info=True)
            return False
    
    async def start(self) -> bool:
        """
        Mesaj işleyiciyi başlatır.
        
        Returns:
            bool: Başarılı ise True
        """
        try:
            self.is_running = True
            self.is_paused = False
            
            # Rate limiter'ları sıfırla
            self.rate_limiter = RateLimiter(max_requests=10, time_window=30)
            if hasattr(self.adaptive_limiter, 'reset'):
                self.adaptive_limiter.reset()
            
            logger.info("MessageHandler başarıyla başlatıldı")
            return True
            
        except Exception as e:
            logger.error(f"MessageHandler start hatası: {str(e)}")
            return False
    
    async def stop(self) -> None:
        """
        Mesaj işleyiciyi durdurur.
        """
        logger.info("MessageHandler durduruluyor...")
        self.is_running = False
        self.stop_event.set()
        logger.info("MessageHandler durduruldu")
    
    async def pause(self) -> None:
        """
        Mesaj işleyici servisini geçici olarak duraklatır.
        """
        if not self.is_paused:
            self.is_paused = True
            logger.info("MessageHandler duraklatıldı")
    
    async def resume(self) -> None:
        """
        Duraklatılmış mesaj işleyici servisini devam ettirir.
        """
        if self.is_paused:
            self.is_paused = False
            logger.info("MessageHandler devam ettiriliyor")
    
    async def process_message(self, message: Any) -> Optional[str]:
        """
        Gelen mesajı asenkron olarak işler ve uygun yanıtı oluşturur.
        
        Bu metot mesajı türüne göre sınıflandırır ve uygun işleyiciyi çağırır.
        Rate limiting kontrolü yapar ve işlem istatistiklerini günceller.
        
        Args:
            message: İşlenecek mesaj nesnesi
            
        Returns:
            Optional[str]: Oluşturulan yanıt veya None
        """
        if not self.is_running or self.is_paused:
            return None
            
        try:
            # Mesaj kontrolü
            if not hasattr(message, 'text') and not hasattr(message, 'media'):
                logger.warning("İşlenemeyen mesaj formatı")
                return None
                
            # Rate limiter kontrolü
            wait_time = self.adaptive_limiter.get_wait_time()
            if wait_time > 0:
                logger.debug(f"Rate limiting: {wait_time:.1f}s bekleniyor")
                await asyncio.sleep(wait_time)
            
            # Mesaj türünü belirle
            message_type = self._determine_message_type(message)
            
            # Mesajı türüne göre işle
            response = None
            
            if message_type == MessageType.TEXT:
                response = await self._process_text_message(message)
                self.stats["text_messages"] += 1
            elif message_type == MessageType.STICKER:
                response = await self._process_sticker_message(message)
                self.stats["sticker_messages"] += 1
            elif message_type in [MessageType.PHOTO, MessageType.VIDEO, MessageType.DOCUMENT, MessageType.VOICE]:
                response = await self._process_media_message(message, message_type)
                self.stats["media_messages"] += 1
            else:
                logger.debug(f"Desteklenmeyen mesaj türü: {message_type}")
            
            # İstatistik ve durum güncelleme
            self.stats["total_processed"] += 1
            self.stats["last_activity"] = datetime.now()
            self.last_processed_time = datetime.now()
            
            # Rate limiter'ı güncelle
            self.adaptive_limiter.mark_used()
            
            # İşlem kaydı
            if hasattr(message, 'id'):
                self.processed_messages[message.id] = {
                    'type': message_type.value,
                    'time': datetime.now(),
                    'responded': response is not None
                }
            
            return response
            
        except errors.FloodWaitError as e:
            wait_time = e.seconds
            
            # Rate limiter'ı güncelle
            self.adaptive_limiter.register_error(e)
            
            logger.warning(f"⚠️ FloodWaitError: {wait_time}s bekleniyor")
            await asyncio.sleep(wait_time)
            return None
            
        except Exception as e:
            self.stats["error_count"] += 1
            logger.error(f"Mesaj işleme hatası: {str(e)}", exc_info=True)
            return None
    
    def _determine_message_type(self, message: Any) -> MessageType:
        """
        Mesajın türünü belirler.
        
        Args:
            message: Türü belirlenecek mesaj nesnesi
            
        Returns:
            MessageType: Belirlenen mesaj türü
        """
        try:
            # Text mesajı kontrolü
            if hasattr(message, 'text') and message.text:
                return MessageType.TEXT
                
            # Medya kontrolü
            if hasattr(message, 'media'):
                if hasattr(message.media, 'photo'):
                    return MessageType.PHOTO
                elif hasattr(message.media, 'document'):
                    if hasattr(message.media, 'document') and hasattr(message.media.document, 'mime_type'):
                        mime_type = message.media.document.mime_type
                        if mime_type.startswith('video/'):
                            return MessageType.VIDEO
                        elif mime_type.startswith('audio/'):
                            return MessageType.VOICE
                        else:
                            return MessageType.DOCUMENT
                    return MessageType.DOCUMENT
                elif hasattr(message.media, 'sticker'):
                    return MessageType.STICKER
                else:
                    return MessageType.MEDIA
                    
            # Diğer türler için kontrol ekle
            
            # Belirlenemezse UNKNOWN dön
            return MessageType.UNKNOWN
            
        except Exception as e:
            logger.error(f"Mesaj türü belirleme hatası: {str(e)}")
            return MessageType.UNKNOWN
    
    async def _process_text_message(self, message: Any) -> Optional[str]:
        """
        Metin mesajını işler.
        
        Args:
            message: İşlenecek metin mesajı
            
        Returns:
            Optional[str]: Oluşturulan yanıt veya None
        """
        try:
            text = message.text.strip()
            chat_id = getattr(message, 'chat_id', None)
            user_id = getattr(message.sender, 'id', None)
            
            # Mesaj içeriğini analiz et
            contains_question = any(q in text.lower() for q in ['?', 'ne', 'nasıl', 'nerede', 'ne zaman', 'kim'])
            contains_greeting = any(g in text.lower() for g in ['merhaba', 'selam', 'hey', 'hi', 'hello'])
            contains_thanks = any(t in text.lower() for t in ['teşekkür', 'sağol', 'eyvallah', 'thanks'])
            
            # Mesajın özelliğine göre yanıt belirle
            if contains_greeting:
                return random.choice([
                    "Merhaba! 👋",
                    "Selam! 😊",
                    "Hoş geldin! 🌟"
                ])
            elif contains_question:
                return random.choice([
                    "Bu konuda yardımcı olabilirim.",
                    "İlginç bir soru, düşüneyim...",
                    "Sanırım gruplarımızda bu konuda bilgi bulabilirsin."
                ])
            elif contains_thanks:
                return random.choice([
                    "Rica ederim! 😊",
                    "Ne demek, her zaman!",
                    "Bir şey değil!"
                ])
                
            return None  # Bazı mesajlara yanıt vermiyoruz
            
        except Exception as e:
            logger.error(f"Metin mesajı işleme hatası: {str(e)}")
            return None
    
    async def _process_sticker_message(self, message: Any) -> Optional[str]:
        """
        Sticker mesajını işler.
        
        Args:
            message: İşlenecek sticker mesajı
            
        Returns:
            Optional[str]: Oluşturulan yanıt veya None
        """
        try:
            # Sticker mesajlarına nadiren yanıt ver
            should_respond = random.random() < 0.2  # %20 şans
            
            if should_respond:
                return random.choice([
                    "Harika bir sticker! 😄",
                    "Bu sticker'ı beğendim!",
                    "👍"
                ])
            
            return None
            
        except Exception as e:
            logger.error(f"Sticker işleme hatası: {str(e)}")
            return None
    
    async def _process_media_message(self, message: Any, media_type: MessageType) -> Optional[str]:
        """
        Medya mesajını işler.
        
        Args:
            message: İşlenecek medya mesajı
            media_type: Medya türü
            
        Returns:
            Optional[str]: Oluşturulan yanıt veya None
        """
        try:
            # Medya türüne göre yanıt belirle
            if media_type == MessageType.PHOTO:
                return random.choice([
                    "Harika bir fotoğraf!",
                    "Çok güzel bir kare!",
                    "Paylaşım için teşekkürler!"
                ])
            elif media_type == MessageType.VIDEO:
                return random.choice([
                    "İlginç bir video!",
                    "Videoyu izledim, güzel içerik.",
                    "Paylaşım için teşekkürler!"
                ])
            elif media_type == MessageType.VOICE:
                return "Ses mesajını aldım."
            elif media_type == MessageType.DOCUMENT:
                return "Dokümanı aldım, teşekkürler."
                
            return None
            
        except Exception as e:
            logger.error(f"Medya işleme hatası: {str(e)}")
            return None
    
    def get_status(self) -> Dict[str, Any]:
        """
        Servis durumunu döndürür.
        
        Returns:
            Dict[str, Any]: Servis durum bilgileri
        """
        return {
            "running": self.is_running,
            "paused": self.is_paused,
            "total_processed": self.stats["total_processed"],
            "text_messages": self.stats["text_messages"],
            "media_messages": self.stats["media_messages"],
            "error_count": self.stats["error_count"],
            "last_activity": self.stats["last_activity"].strftime("%H:%M:%S") if self.stats["last_activity"] else "Hiç"
        }
        
    def get_statistics(self) -> Dict[str, Any]:
        """
        Detaylı istatistik verilerini döndürür.
        
        Returns:
            Dict[str, Any]: İstatistik verileri
        """
        # Çalışma süresi hesaplama
        uptime_seconds = 0
        if self.stats["start_time"]:
            uptime_seconds = (datetime.now() - self.stats["start_time"]).total_seconds()
        
        # İstatistik oluştur
        return {
            "running": self.is_running,
            "paused": self.is_paused,
            "start_time": self.stats["start_time"].strftime("%Y-%m-%d %H:%M:%S") if self.stats["start_time"] else None,
            "uptime_hours": round(uptime_seconds / 3600, 2),
            "total_processed": self.stats["total_processed"],
            "text_messages": self.stats["text_messages"],
            "media_messages": self.stats["media_messages"],
            "sticker_messages": self.stats["sticker_messages"],
            "error_count": self.stats["error_count"],
            "last_activity": self.stats["last_activity"].strftime("%Y-%m-%d %H:%M:%S") if self.stats["last_activity"] else None,
            "message_rate": round(self.stats["total_processed"] / (uptime_seconds / 3600), 2) if uptime_seconds > 0 else 0
        }