"""
# ============================================================================ #
# Dosya: reply_service.py
# Yol: /Users/siyahkare/code/telegram-bot/bot/services/reply_service.py
# İşlev: Telegram bot için otomatik yanıt servisi.
#
# Amaç: Belirli tetikleyicilere veya yanıtlara otomatik cevaplar göndererek Telegram gruplarındaki etkileşimi artırır.
#
# Build: 2025-04-01-02:45:00
# Versiyon: v3.4.0
# ============================================================================ #
#
# Bu modül, bot'un otomatik yanıt mekanizmasını yönetir.
# Temel özellikleri:
# - Yapılandırılabilir yanıt şablonları
# - Gelişmiş hız sınırlama (rate limiting)
# - İstatistik takibi (işlenen mesajlar, gönderilen yanıtlar, son aktivite)
# - Tekrarlı yanıtları önleme
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""
import asyncio
import logging
import random
from datetime import datetime
from telethon import events, errors
from bot.utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

class ReplyService:
    """
    Telegram gruplarında otomatik yanıtlar göndermeyi yöneten servis.
    
    Bu sınıf, belirli tetikleyicilere veya yanıtlara otomatik cevaplar göndererek
    Telegram gruplarındaki etkileşimi artırmak için tasarlanmıştır.
    """
    
    def __init__(self, client, config, db, stop_event=None):
        """
        ReplyService sınıfının başlatıcı metodu.
        
        Args:
            client: Telethon Telegram client nesnesi.
            config: Uygulama yapılandırma nesnesi.
            db: Veritabanı nesnesi.
            stop_event: Servisin durdurulmasını kontrol etmek için kullanılan olay nesnesi.
        """
        self.client = client
        self.config = config
        self.db = db
        self.stop_event = stop_event
        
        # Çalışma durumu
        self.running = True
        
        # İstatistikler
        self.processed_messages = 0
        self.replies_sent = 0
        self.last_activity = datetime.now()
        
        # Yanıt şablonları
        self.response_templates = config.response_templates
        
        # Yanıt gönderilen mesajların ID'lerini tutan set
        # Bu, tekrarlı yanıt gönderimi önlemeye yardımcı olur
        self.replied_messages = set()
        
        # Rate limiter örneği
        self.rate_limiter = RateLimiter(rate=8, per=60)  # Dakikada 5 mesaj varsayılan değer
        
        # Yanıt verilen kullanıcıların ID'lerini tutan set
        self.responded_users = set()
        
        logger.info("Yanıt servisi başlatıldı")
        
    async def run(self):
        """
        Servisin ana döngüsü. Telegram'dan gelen yeni mesajları dinler ve işler.
        
        Bu döngü, belirtilen durdurma eventi ayarlanana kadar çalışmaya devam eder.
        """
        logger.info("Yanıt servisi başlıyor")
        
        # Önce kendi ID'mizi al
        me = await self.client.get_me()
        my_id = me.id
        
        # Grup mesajlarını dinle
        @self.client.on(events.NewMessage(incoming=True, func=lambda e: 
                         e.is_group and not e.sender_id == my_id))
        async def handle_new_message(event):
            """Grup mesajlarını işler ve gerekirse yanıt verir"""
            if not self.running or self.stop_event and self.stop_event.is_set():
                return
                
            try:
                # Mesajı işle
                self.processed_messages += 1
                self.last_activity = datetime.now()
                
                # Botun mesajlarına yanıt geldi mi kontrol et
                if event.is_reply:
                    replied_to = await event.get_reply_message()
                    me = await self.client.get_me()
                    
                    # Eğer bizim mesajımıza yanıt geldiyse
                    if replied_to.sender_id == me.id:
                        # Mesaj ID'sini kontrol et, daha önce yanıt verdik mi?
                        if event.id not in self.replied_messages:
                            await self._send_response(event, "flirty")
                            self.replied_messages.add(event.id)
                            
                            # Set'in çok büyümesini engelle
                            if len(self.replied_messages) > 1000:
                                self.replied_messages = set(list(self.replied_messages)[-500:])
                
            except Exception as e:
                logger.error(f"Mesaj işleme hatası: {str(e)}")
        
        @self.client.on(events.NewMessage())
        async def handle_group_message(event):
            """Grup mesajlarını işler."""
            # Güvenlik kontrolleri
            if not event or not hasattr(event, 'sender_id') or not event.sender_id:
                return
                
            # Kendi mesajlarımızı işleme
            if event.sender_id == my_id:
                return
                
            # Özel mesajları atlayalım, onları DM servisi işler
            if not hasattr(event, 'is_private') or event.is_private:
                return
            
            # Durdurma kontrolü    
            if not self.running or self.stop_event and self.stop_event.is_set():
                return
                
            # Mention kontrolü - daha güvenli yöntem
            is_mentioned = False
            mentions = get_mentions(event)
            if me and hasattr(me, 'username') and me.username:
                is_mentioned = me.username.lower() in [m.lower() for m in mentions]
            
            # Yanıt kontrolü - asenkron işlem
            is_reply = False
            try:
                if hasattr(event, 'message') and hasattr(event.message, 'reply_to'):
                    replied_msg = await event.message.get_reply_message()
                    if replied_msg and hasattr(replied_msg, 'sender_id') and replied_msg.sender_id == my_id:
                        is_reply = True
            except Exception as e:
                logger.debug(f"Yanıt kontrolü hatası: {e}")
            
            # Eğer mention veya yanıt yoksa, sessizce çık
            if not is_mentioned and not is_reply:
                return
                
            # Log ve işleme
            try:
                sender = await event.get_sender()
                chat = await event.get_chat()
                
                sender_name = "Bilinmeyen"
                if sender:
                    if hasattr(sender, 'username') and sender.username:
                        sender_name = f"@{sender.username}"
                    elif hasattr(sender, 'first_name'):
                        sender_name = sender.first_name
                        
                chat_name = "Bilinmeyen Grup"
                if chat and hasattr(chat, 'title'):
                    chat_name = chat.title
                    
                if is_mentioned:
                    logger.info(f"📢 Mention: {sender_name} in {chat_name}")
                elif is_reply:
                    logger.info(f"↩️ Yanıt: {sender_name} in {chat_name}")
                    
                # Eğer botun yanıt vermesi gerekiyorsa:
                if is_mentioned or is_reply:
                    # Rate limiting kontrolü
                    if self.rate_limiter.is_allowed():
                        await self._send_response(event, "flirty")
                        self.rate_limiter.mark_used()
                    else:
                        logger.warning(f"Hız sınırlaması: Mention/yanıta cevap verilmedi")
                        
            except Exception as e:
                logger.error(f"Grup mesajı işleme hatası: {str(e)}")
        
        # Durma eventi ayarlanana kadar bekle
        try:
            while not (self.stop_event and self.stop_event.is_set()):
                if self.running:
                    # Her 30 dakikada bir istatistikleri logla
                    now = datetime.now()
                    if (now - self.last_activity).total_seconds() > 1800:  # 30 dakika
                        logger.info(f"Yanıt servisi aktif: {self.processed_messages} mesaj işlendi, {self.replies_sent} yanıt gönderildi")
                        self.last_activity = now
                
                await asyncio.sleep(5)  # CPU yükünü azaltmak için bekleme
                
        except asyncio.CancelledError:
            logger.info("Yanıt servisi durduruldu")
        except Exception as e:
            logger.error(f"Yanıt servisi hata: {str(e)}")
    
    async def _send_response(self, message, template_type):
        """
        Kullanıcıya yanıt mesajı gönderir.
        """
        try:
            # Yanıt mesajını oluştur
            response_message = self._choose_response_template(template_type)
            # Mesajı gönder
            await message.reply(response_message)
            self.replies_sent += 1
            self.last_activity = datetime.now()
            logger.info(f"Yanıt gönderildi: {message.sender_id}")
        except errors.FloodWaitError as e:
            logger.warning(f"FloodWaitError: {e.seconds} saniye bekleniyor")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            logger.error(f"Yanıt gönderme hatası: {str(e)}")
    
    def _choose_response_template(self, template_type):
        """
        Yapılandırmadan rastgele bir yanıt şablonu seçer.
        
        Returns:
            Seçilen yanıt şablonu (metin).
        """
        if not self.response_templates:
            return "Teşekkürler! 🙂"
            
        templates = self.response_templates.get(template_type, ["Teşekkürler! 🙂"])
        return random.choice(templates)  # Şablonlardan rastgele seçim yap
    
    def get_status(self):
        """
        Servisin mevcut durumunu ve istatistiklerini döndürür.
        
        Returns:
            Servisin durumu, işlenen mesaj sayısı, gönderilen yanıt sayısı ve son aktivite zamanı gibi bilgileri içeren bir sözlük.
        """
        return {
            "running": self.running,
            "processed_messages": self.processed_messages,
            "replies_sent": self.replies_sent,
            "last_activity": self.last_activity.strftime("%H:%M:%S")
        }

# Eksik fonksiyonları tanımla

def is_mention(event, my_username):
    """Mesajın bizi mention ettiğini kontrol eder."""
    if not event.message.entities:
        return False
        
    for entity in event.message.entities:
        # 'type' kontrolü yerine entity tipini kontrol et
        # MessageEntityMention tipinde olup olmadığını kontrol et
        if hasattr(entity, "offset") and hasattr(entity, "length"):
            try:
                mention_text = event.message.text[entity.offset:entity.offset + entity.length]
                if mention_text == f"@{my_username}":
                    return True
            except Exception:
                # Index hatalarını yutabiliriz
                pass
    return False

def is_reply_to_me(event, my_id):
    """Mesajın bize yanıt olduğunu kontrol eder."""
    if event.message.reply_to:
        try:
            replied_msg = event.message.reply_to
            if replied_msg and hasattr(replied_msg, 'reply_to_msg_id'):
                # Bu basitleştirilmiş bir kontrol, tam işlevsellik için event.get_reply_message() kullanmalıyız
                # Bu fonksiyon async olduğu için burada direkt kullanamayız
                return True  # Bu daha sonra geliştirilebilir
        except:
            pass
    return False

def get_mentions(event):
    """
    Bir mesajdaki mention'ları döndürür.
    
    Args:
        event: Telethon mesaj olayı
        
    Returns:
        list: Mention edilen kullanıcı adlarının listesi
    """
    mentions = []
    
    if not hasattr(event, 'message') or not event.message or not hasattr(event.message, 'text'):
        return mentions
        
    text = event.message.text
    
    # @ ile başlayan kullanıcı adlarını bul
    import re
    # Regex ile @ ile başlayan kullanıcı adlarını bul
    mentions_regex = re.findall(r'@([a-zA-Z0-9_]{5,32})', text)
    if mentions_regex:
        mentions.extend(mentions_regex)
    
    return mentions