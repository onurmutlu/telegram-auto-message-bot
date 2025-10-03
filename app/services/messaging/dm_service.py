"""
# ============================================================================ #
# Dosya: dm_service.py
# Yol: /Users/siyahkare/code/telegram-bot/app/services/messaging/dm_service.py
# İşlev: Direkt mesaj gönderimi için servis sınıfı.
#
# Versiyon: v1.0.0
# ============================================================================ #
"""

import logging
import random
import json
import os
import asyncio
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, UserIsBlockedError

from app.services.base_service import BaseService
from app.db.session import get_session
from app.core.config import settings
from app.models.user import User
from app.services.analytics.user_service import UserService

logger = logging.getLogger(__name__)

class DirectMessageService(BaseService):
    """
    Doğrudan mesajları yöneten servis.
    
    Bu servis şunları yapar:
    - Yeni gelen özel mesajları işler
    - Otomatik cevaplar gönderir
    - Mesaj istatistiklerini toplar
    """
    
    def __init__(self, client: TelegramClient, db=None):
        """DM servisini başlat."""
        super().__init__(name="dm_service", db=db)
        self.client = client
        self.service_name = "dm_service"
        self.handlers = []
        
        # Son mesaj zamanlarını takip için
        self.last_dm_times: Dict[int, datetime] = {}
        
        # Şablonlar
        self.welcome_templates = []
        self.service_templates = []
        self.group_invite_templates = []
        self.service_list = []
        self.group_list = []
        
        # İstatistik verileri
        self.sent_count = 0
        self.daily_limit = 200
        self.send_interval = 60  # saniye
        self.last_reset = datetime.now()
        self.templates = {}
        self.active_campaigns = []
        
        # Kayıt durumu
        logger.info(f"{self.service_name} servisi başlatıldı")
        
    async def run(self):
        """Servis ana döngüsü."""
        self.running = True
        logger.info("DM servisi çalışıyor...")
        
        # Event handler'ları ayarla
        @self.client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
        async def handle_private_message(event):
            """Özel mesajları işle"""
            if not self.running:
                return
                
            try:
                sender = await event.get_sender()
                logger.info(f"Özel mesaj alındı: {sender.first_name} (@{sender.username}): {event.text}")
                
                # Mesajı yanıtla
                if event.text.lower() in ["selam", "merhaba", "hi", "hello"]:
                    await event.respond(f"Merhaba {sender.first_name}! Size nasıl yardımcı olabilirim?")
                
            except Exception as e:
                logger.error(f"Özel mesaj işlenirken hata: {e}")
        
        # Handler'ı listeye ekle
        self.handlers.append(handle_private_message)
        
        try:
            # Servis çalışırken aktif kal
            while self.running:
                await asyncio.sleep(10)  # Düzenli kontrol
                
        except asyncio.CancelledError:
            logger.info("DM servisi iptal edildi")
            self.running = False
        except Exception as e:
            logger.error(f"DM servisi çalışırken hata: {e}")
            self.running = False
    
    async def stop(self):
        """Servisi durdur."""
        if not self.running:
            return
            
        self.running = False
        
        # Event handler'ları temizle
        for handler in self.handlers:
            self.client.remove_event_handler(handler)
        
        self.handlers = []
        
        # Üst sınıf stop metodunu çağır
        await super().stop()
        
        logger.info("DM servisi durduruldu")
    
    async def initialize(self):
        """Servisi başlat ve şablonları yükle."""
        self.db = self.db or next(get_session())
        self.user_service = UserService(db=self.db)
        await self._load_templates()
        await self._load_service_list()
        await self._load_group_list()
        logger.info(f"DirectMessageService initialized with {len(self.welcome_templates)} welcome templates")
        
        # Event handler'ları kaydet
        self.client.add_event_handler(
            self.handle_new_private_message,
            events.NewMessage(incoming=True, func=lambda e: e.is_private)
        )
        
        self.initialized = True
        return True
    
    async def _load_templates(self):
        """Mesaj şablonlarını yükle."""
        try:
            # Önce veritabanı şemasını kontrol et
            schema_query = """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
            """
            schema_result = self.db.execute(text(schema_query))
            tables = [row[0] for row in schema_result.fetchall()]
            
            if 'message_templates' not in tables:
                logger.warning("Message templates table not found, using default templates")
                # Varsayılan şablonlar ekle
                self.welcome_templates = [(1, "Merhaba, Telegram botumuza hoş geldiniz! 👋")]
                self.service_templates = [(1, "Hizmetlerimiz hakkında bilgi almak ister misiniz?")]
                self.group_invite_templates = [(1, "Gruplarımıza katılarak destek olabilirsiniz.")]
            else:
                # Karşılama şablonları
                query = """
                    SELECT id, content FROM message_templates 
                    WHERE is_active = true AND type = 'dm_welcome'
                """
                result = self.db.execute(text(query))
                self.welcome_templates = result.fetchall()
                
                # Hizmet tanıtım şablonları
                query = """
                    SELECT id, content FROM message_templates 
                    WHERE is_active = true AND type = 'dm_service'
                """
                result = self.db.execute(text(query))
                self.service_templates = result.fetchall()
                
                # Grup davet şablonları
                query = """
                    SELECT id, content FROM message_templates 
                    WHERE is_active = true AND type = 'dm_invite'
                """
                result = self.db.execute(text(query))
                self.group_invite_templates = result.fetchall()
            
            # Templates sözlüğünü güncelle
            self.templates = {
                "welcome": self.welcome_templates,
                "service": self.service_templates,
                "invite": self.group_invite_templates
            }
            
            logger.info(f"Loaded templates: welcome={len(self.welcome_templates)}, " + 
                        f"service={len(self.service_templates)}, invite={len(self.group_invite_templates)}")
        except Exception as e:
            logger.error(f"Error loading templates: {str(e)}")
            # En azından varsayılan şablonlar ekle
            self.welcome_templates = [(1, "Merhaba, Telegram botumuza hoş geldiniz! 👋")]
            self.service_templates = [(1, "Hizmetlerimiz hakkında bilgi almak ister misiniz?")]
            self.group_invite_templates = [(1, "Gruplarımıza katılarak destek olabilirsiniz.")]
            self.templates = {
                "welcome": self.welcome_templates,
                "service": self.service_templates,
                "invite": self.group_invite_templates
            }
    
    async def _load_service_list(self):
        """Sunulan hizmetleri yükle."""
        try:
            # Önce veritabanı şemasını kontrol et
            schema_query = """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
            """
            schema_result = self.db.execute(text(schema_query))
            tables = [row[0] for row in schema_result.fetchall()]
            
            if 'services' in tables:
                query = """
                    SELECT id, name, description, price, is_active 
                    FROM services 
                    WHERE is_active = true
                    ORDER BY id DESC
                """
                result = self.db.execute(text(query))
                self.service_list = result.fetchall()
                logger.info(f"Loaded {len(self.service_list)} active services")
            else:
                logger.warning("Services table not found in database")
                self.service_list = []
        except Exception as e:
            logger.error(f"Error loading service list: {str(e)}")
            self.service_list = []
    
    async def _load_group_list(self):
        """Davet edilecek gruplarımızı yükle."""
        try:
            # Önce veritabanı şemasını kontrol et
            schema_query = """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'groups'
            """
            schema_result = self.db.execute(text(schema_query))
            columns = [row[0] for row in schema_result.fetchall()]
            
            if not columns:
                logger.warning("Groups table has no columns or doesn't exist")
                self.group_list = []
                return
                
            # Her sütun için kontrol et ve dinamik sorgu oluştur
            # "title" sütunu yoksa "name" veya "group_name" sütununu kullan
            name_column = "title"
            if "title" not in columns:
                if "name" in columns:
                    name_column = "name"
                elif "group_name" in columns:
                    name_column = "group_name"
            
            # chat_id yerine alternatif sütun isimleri kontrol et
            chat_id_column = None
            for possible_column in ["chat_id", "group_id", "telegram_id", "tg_id"]:
                if possible_column in columns:
                    chat_id_column = possible_column
                    break
            
            # Gerekli sütunlar mevcut değilse
            if not chat_id_column:
                logger.warning("Chat ID column not found in groups table")
                # Sadece mevcut olan sütunlarla çalışalım
                query = f"""
                    SELECT id, {name_column} AS title 
                    FROM groups 
                    WHERE is_active = true
                    ORDER BY id DESC
                """
            else:
                # Diğer sütunları da kontrol et
                invite_column = "invite_link" if "invite_link" in columns else "NULL as invite_link"
                desc_column = "description" if "description" in columns else "NULL as description"
                member_column = "member_count" if "member_count" in columns else "0 as member_count"
                admin_check = "AND is_admin = true" if "is_admin" in columns else ""
                
                query = f"""
                    SELECT id, {name_column} AS title, {chat_id_column} as chat_id, 
                           {invite_column}, {desc_column}, {member_column}
                    FROM groups 
                    WHERE is_active = true {admin_check}
                    ORDER BY id DESC
                """
            
            # Sorguyu çalıştır ve sonuçları kaydet
            self.db.rollback()  # Önceki hatadan kalan işlemi temizle
            result = self.db.execute(text(query))
            self.group_list = result.fetchall()
            logger.info(f"Loaded {len(self.group_list)} groups for invites")
        except Exception as e:
            logger.error(f"Error loading group list: {str(e)}")
            # Önceki hatalı işlemi geri al ve devam et
            try:
                self.db.rollback()
            except:
                pass
            self.group_list = []
    
    async def handle_new_private_message(self, event):
        """Kullanıcılardan gelen özel mesajları işle."""
        try:
            message = event.message
            sender = await message.get_sender()
            user_id = sender.id
            
            logger.info(f"Received DM from user {user_id}")
            
            # Kullanıcıyı veritabanında kaydet/güncelle
            await self.user_service.register_or_update_user(sender)
            
            # Kullanıcı bilgilerini getir
            user = await self.user_service.get_user(user_id)
            
            # Eğer yeni kullanıcıysa veya ilk mesajıysa karşılama mesajı gönder
            if not user or user.get("messages_received", 0) <= 1:
                await self._send_welcome_message(user_id)
            
            # Hizmet listesi istenirse
            message_text = message.text.lower() if message.text else ""
            if "hizmet" in message_text or "fiyat" in message_text or "ücret" in message_text:
                await self._send_service_list(user_id)
            elif "grup" in message_text or "kanal" in message_text or "davet" in message_text:
                await self._send_group_invites(user_id)
            else:
                # Diğer durumlarda genel bir yanıt ver
                await self._send_auto_dm_reply(user_id)
                
        except Exception as e:
            logger.error(f"Error handling private message: {str(e)}", exc_info=True)
    
    async def _send_welcome_message(self, user_id: int):
        """Yeni kullanıcıya karşılama mesajı gönder."""
        try:
            if not self.welcome_templates:
                logger.warning("No welcome templates found")
                await self.client.send_message(user_id, "Merhaba, Telegram botumuza hoş geldiniz! 👋")
                return
                
            # Rastgele bir hoşgeldin mesajı seç
            template = random.choice(self.welcome_templates)
            message_text = template.content if hasattr(template, 'content') else template[1]
            
            # Mesajı gönder
            await self.client.send_message(user_id, message_text)
            logger.info(f"Sent welcome message to user {user_id}")
            
            # Kullanıcı istatistiklerini güncelle
            if self.user_service:
                await self.user_service.update_user_stat(user_id, "welcome_message_sent", 1)
                    
        except Exception as e:
            logger.error(f"Error sending welcome message: {str(e)}", exc_info=True)
            # Hata durumunda standart bir karşılama göndermeyi dene
            try:
                await self.client.send_message(user_id, "Merhaba, Telegram botumuza hoş geldiniz! 👋")
            except:
                pass
    
    async def _send_service_list(self, user_id: int):
        """Kullanıcıya hizmet listesini gönder."""
        try:
            if not self.service_list:
                await self.client.send_message(user_id, "Şu an için aktif bir hizmet bulunmamaktadır.")
                return
                
            message_text = "📋 **Hizmet Listesi**\n\n"
            valid_services_count = 0
            
            for service in self.service_list:
                try:
                    # Service objesi veya tuple/list olabilir
                    if hasattr(service, '__dict__'):  # SQLAlchemy nesnesiyse
                        name = getattr(service, 'name', '')
                        description = getattr(service, 'description', '')
                        price = getattr(service, 'price', 0)
                        is_active = getattr(service, 'is_active', True)
                    else:  # Tuple ise
                        # En az 2 sütun olmalı (id ve name)
                        if len(service) < 2:
                            continue
                            
                        name = service[1]
                        description = service[2] if len(service) > 2 else ""
                        price = service[3] if len(service) > 3 else 0
                        is_active = service[4] if len(service) > 4 else True
                    
                    # Sadece aktif hizmetleri göster
                    if not is_active:
                        continue
                    
                    # Mesajı oluştur
                    message_text += f"**{name}**\n"
                    if description:
                        message_text += f"{description}\n"
                    message_text += f"Fiyat: {price} TL\n\n"
                    valid_services_count += 1
                    
                except Exception as e:
                    logger.warning(f"Error formatting service: {e}")
                    continue
            
            # Hiç geçerli hizmet yoksa
            if valid_services_count == 0:
                await self.client.send_message(user_id, "Şu an için aktif bir hizmet bulunmamaktadır.")
                return
                
            message_text += "\nDetaylı bilgi için lütfen iletişime geçin."
            
            # Mesaj çok uzunsa bölmek gerekebilir
            if len(message_text) > 4000:
                chunks = [message_text[i:i+4000] for i in range(0, len(message_text), 4000)]
                for chunk in chunks:
                    await self.client.send_message(user_id, chunk)
                    await asyncio.sleep(0.5)  # Mesajlar arasında kısa bekle
            else:
                await self.client.send_message(user_id, message_text)
                
            logger.info(f"Sent service list to user {user_id}")
            
            # Kullanıcı istatistiklerini güncelle
            if self.user_service:
                try:
                    await self.user_service.update_user_stat(user_id, "service_list_viewed", 1)
                except Exception as e:
                    logger.warning(f"Could not update user stats: {e}")
            
        except Exception as e:
            logger.error(f"Error sending service list: {str(e)}", exc_info=True)
            # Hata durumunda basit bir mesaj gönder
            try:
                await self.client.send_message(user_id, "Hizmet listesi şu anda yüklenemiyor. Lütfen daha sonra tekrar deneyiniz.")
            except:
                pass
    
    async def _send_group_invites(self, user_id: int):
        """Kullanıcıya grup davetlerini gönder."""
        try:
            if not self.group_list:
                await self.client.send_message(user_id, "Şu an için aktif bir grup daveti bulunmamaktadır.")
                return
                
            # Davet şablonu seç
            template = random.choice(self.group_invite_templates) if self.group_invite_templates else None
            
            # Ana mesaj metni
            message_text = "🌟 **Telegram Gruplarımız**\n\n"
            
            # Eğer bir şablon varsa onu ekle
            if template:
                template_text = template.content if hasattr(template, 'content') else template[1]
                message_text += f"{template_text}\n\n"
            
            # En fazla 5 grup göster (Telegram mesaj limitleri için)
            group_count = min(5, len(self.group_list))
            valid_groups_count = 0
            
            for group in self.group_list[:group_count]:
                # Group objesi veya tuple/list olabilir
                try:
                    # Değerleri almaya çalış (farklı sütun yapıları dikkate alınarak)
                    if hasattr(group, '__dict__'):  # SQLAlchemy nesnesiyse
                        title = getattr(group, 'title', '')
                        invite_link = getattr(group, 'invite_link', None)
                        description = getattr(group, 'description', '')
                        member_count = getattr(group, 'member_count', 0)
                    else:  # Tuple ise
                        # En az 2 sütun olmalı (id ve title)
                        if len(group) < 2:
                            continue
                            
                        title = group[1]  # title zaten seçilmiş
                        
                        # Diğer sütunlar yapıya göre opsiyonel
                        invite_link = group[3] if len(group) > 3 else None
                        description = group[4] if len(group) > 4 else ""
                        member_count = group[5] if len(group) > 5 else 0
                
                    # Sadece davet linki olan grupları göster
                    if not invite_link:
                        continue
                    
                    # Mesajı oluştur
                    message_text += f"**{title}**\n"
                    if description:
                        message_text += f"{description}\n"
                    if member_count:
                        message_text += f"Üye Sayısı: {member_count}\n"
                    message_text += f"Katılmak için: {invite_link}\n\n"
                    valid_groups_count += 1
                    
                except Exception as e:
                    logger.warning(f"Error formatting group invitation: {e}")
                    continue
            
            # Hiç geçerli grup yoksa
            if valid_groups_count == 0:
                await self.client.send_message(user_id, "Şu an için aktif bir grup daveti bulunmamaktadır.")
                return
                
            # Sonda bilgilendirme
            message_text += "Tüm gruplarımız için web sitemizi ziyaret edebilirsiniz."
            
            await self.client.send_message(user_id, message_text)
            logger.info(f"Sent group invites to user {user_id}")
            
            # Kullanıcı istatistiklerini güncelle
            if self.user_service:
                try:
                    await self.user_service.update_user_stat(user_id, "invites_sent", 1)
                except Exception as e:
                    logger.warning(f"Could not update user stats: {e}")
            
        except Exception as e:
            logger.error(f"Error sending group invites: {str(e)}", exc_info=True)
            # Hata durumunda basit bir mesaj gönder
            try:
                await self.client.send_message(user_id, "Grup davetleri şu anda yüklenemiyor. Lütfen daha sonra tekrar deneyiniz.")
            except:
                pass
    
    async def _send_auto_dm_reply(self, user_id: int):
        """
        DM'ye gelen mesajlara otomatik yanıt gönderir (data/dm_auto_reply.json'dan).
        """
        try:
            import json
            import random
            with open('data/dm_auto_reply.json', 'r', encoding='utf-8') as f:
                replies = json.load(f)
            reply_list = replies.get('dm_auto_reply', [])
            if not reply_list:
                await self.client.send_message(user_id, "Şu anda otomatik yanıt verilemiyor.")
                return
            yanit = random.choice(reply_list)
            await self.client.send_message(user_id, yanit)
            logger.info(f"DM'ye otomatik yanıt gönderildi: {user_id}")
        except Exception as e:
            logger.error(f"DM otomatik yanıt hatası: {str(e)}")
            await self.client.send_message(user_id, "Yanıt gönderilirken bir hata oluştu.")
    
    async def _send_response(self, user_id: int, message_text: str):
        """
        Kullanıcının mesajına özel yanıt gönderir. (Otomatik DM reply de dahil)
        """
        await self._send_auto_dm_reply(user_id)
    
    async def send_promotional_dm(self, user_id: int, promo_type: str = "service"):
        """Kullanıcıya tanıtım mesajı gönder."""
        try:
            # Son mesaj gönderim zamanını kontrol et
            last_sent = self.last_dm_times.get(user_id, datetime.now() - timedelta(days=1))
            time_since_last = (datetime.now() - last_sent).total_seconds() / 60  # dakika
            
            if time_since_last < 60:  # Son 1 saat içinde mesaj gönderdiysen atla
                logger.debug(f"Skipping promotional DM to user {user_id} (sent {time_since_last:.2f} minutes ago)")
                return False
            
            # Tanıtım türüne göre şablon seç
            templates = self.templates.get(promo_type, [])
            if not templates:
                logger.warning(f"No templates found for promo_type: {promo_type}")
                return False
            
            template = random.choice(templates)
            message_text = template.content if hasattr(template, 'content') else template[1]
            
            # Mesajı gönder
            await self.client.send_message(user_id, message_text)
            
            # Son gönderim zamanını güncelle
            self.last_dm_times[user_id] = datetime.now()
            self.sent_count += 1
            
            logger.info(f"Sent promotional DM ({promo_type}) to user {user_id}")
            return True
            
        except UserIsBlockedError:
            logger.warning(f"User {user_id} has blocked the bot")
            return False
            
        except FloodWaitError as e:
            wait_time = e.seconds
            logger.warning(f"FloodWaitError: Need to wait {wait_time} seconds")
            return False
            
        except Exception as e:
            logger.error(f"Error sending promotional DM: {str(e)}", exc_info=True)
            return False
    
    async def start_promo_loop(self):
        """Tanıtım mesajı döngüsü."""
        logger.info("Starting promotional DM loop")
        self.running = True
        
        while self.running:
            try:
                # Günlük limiti sıfırla (eğer gün değiştiyse)
                now = datetime.now()
                if now.day != self.last_reset.day:
                    self.sent_count = 0
                    self.last_reset = now
                
                # Günlük limite ulaşıldıysa bekle
                if self.sent_count >= self.daily_limit:
                    logger.info(f"Daily DM limit reached ({self.sent_count}/{self.daily_limit}). Waiting until next day.")
                    await asyncio.sleep(3600)  # 1 saat bekle
                    continue
                
                # Hedef kullanıcıları al
                query = """
                    SELECT user_id, first_name, last_name, username
                    FROM users
                    WHERE is_active = true 
                      AND is_blocked = false
                      AND last_dm_sent < NOW() - INTERVAL '24 hours'
                    ORDER BY last_activity_at DESC
                    LIMIT 20
                """
                result = self.db.execute(text(query))
                users = result.fetchall()
                
                if not users:
                    logger.info("No users found for DM promo, waiting 30 minutes")
                    await asyncio.sleep(1800)
                    continue
                
                # Her kullanıcıya tanıtım mesajı gönder
                for user in users:
                    if not self.running or self.sent_count >= self.daily_limit:
                        break
                        
                    user_id = user.user_id if hasattr(user, 'user_id') else user[0]
                    
                    # Tanıtım mesajını gönder
                    success = await self.send_promotional_dm(user_id)
                    
                    if success:
                        # Veritabanını güncelle
                        query = """
                            UPDATE users 
                            SET last_dm_sent = NOW() 
                            WHERE user_id = :user_id
                        """
                        self.db.execute(text(query), {"user_id": user_id})
                        self.db.commit()
                    
                    # FloodWait'ten kaçınmak için bekle
                    await asyncio.sleep(self.send_interval)
                
                # İşlemler arasında ara ver
                await asyncio.sleep(300)  # 5 dakika
                
            except Exception as e:
                logger.error(f"Error in promo DM loop: {str(e)}", exc_info=True)
                await asyncio.sleep(600)  # Hata durumunda 10 dakika bekle
    
    async def cleanup(self):
        """Servis kapatılırken temizlik."""
        if hasattr(self, 'client') and self.client:
            self.client.remove_event_handler(self.handle_new_private_message)
        logger.info("DirectMessageService cleanup completed")
    
    async def get_status(self) -> Dict[str, Any]:
        """
        Servis durumunu döndürür.
        
        Returns:
            Dict[str, Any]: Durum bilgileri
        """
        return {
            "name": "DirectMessageService",
            "running": self.running,
            "initialized": self.initialized,
            "daily_limit": self.daily_limit,
            "sent_today": self.sent_count,
            "welcome_templates": len(self.welcome_templates),
            "service_templates": len(self.service_templates),
            "group_templates": len(self.group_invite_templates),
            "service_list_count": len(self.service_list),
            "group_list_count": len(self.group_list),
            "last_reset": self.last_reset.isoformat()
        }

    async def _start(self) -> bool:
        """BaseService için başlatma metodu"""
        return await self.initialize()
        
    async def _stop(self) -> bool:
        """BaseService için durdurma metodu"""
        try:
            self.running = False
            await self.cleanup()
            return True
        except Exception as e:
            logger.error(f"Error stopping DirectMessageService: {str(e)}", exc_info=True)
            return False

    async def _update(self) -> bool:
        """Periyodik güncelleme metodu"""
        # Şablonları yeniden yükle 
        await self._load_templates()
        await self._load_service_list()
        await self._load_group_list()
        return True
