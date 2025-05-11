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
from app.db.session import get_session, get_db
from app.core.config import settings
from app.models.user import User
from app.services.analytics.user_service import UserService

logger = logging.getLogger(__name__)

class DirectMessageService(BaseService):
    """
    DM yönetim servisi.
    - Kullanıcılardan gelen özel mesajlara yanıt verir
    - Hizmet satışı mesajları gönderir
    - Gruplara katılım daveti gönderir
    """
    
    service_name = "dm_service"
    default_interval = 3600  # 1 saat
    
    def __init__(self, client: TelegramClient, db: AsyncSession = None):
        """
        DirectMessageService sınıfını başlatır.
        
        Args:
            client: TelegramClient
            db: AsyncSession
        """
        super().__init__(name="direct_message_service")
        self.client = client
        self.db = db
        self.user_service = None
        self.initialized = False
        self.running = False
        
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
        
    async def initialize(self):
        """Servisi başlat ve şablonları yükle."""
        self.db = self.db or await get_db().__anext__()
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
        # Karşılama şablonları
        query = """
            SELECT id, content FROM message_templates 
            WHERE is_active = true AND type = 'dm_welcome'
        """
        result = await self.db.execute(query)
        self.welcome_templates = result.fetchall()
        
        # Hizmet tanıtım şablonları
        query = """
            SELECT id, content FROM message_templates 
            WHERE is_active = true AND type = 'dm_service'
        """
        result = await self.db.execute(query)
        self.service_templates = result.fetchall()
        
        # Grup davet şablonları
        query = """
            SELECT id, content FROM message_templates 
            WHERE is_active = true AND type = 'dm_invite'
        """
        result = await self.db.execute(query)
        self.group_invite_templates = result.fetchall()
        
        # Templates sözlüğünü güncelle
        self.templates = {
            "welcome": self.welcome_templates,
            "service": self.service_templates,
            "invite": self.group_invite_templates
        }
    
    async def _load_service_list(self):
        """Sunulan hizmetleri yükle."""
        query = """
            SELECT id, name, description, price, is_active 
            FROM services 
            WHERE is_active = true
            ORDER BY priority DESC
        """
        result = await self.db.execute(query)
        self.service_list = result.fetchall()
    
    async def _load_group_list(self):
        """Davet edilecek gruplarımızı yükle."""
        query = """
            SELECT id, title, chat_id, invite_link, description, member_count 
            FROM groups 
            WHERE is_admin = true AND is_active = true AND invite_link IS NOT NULL
            ORDER BY priority DESC
        """
        result = await self.db.execute(query)
        self.group_list = result.fetchall()
    
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
            if any(keyword in message.text.lower() for keyword in ["hizmet", "servis", "fiyat", "ücret", "service", "price"]):
                await self._send_service_list(user_id)
            
            # Grup davetleri istenirse
            elif any(keyword in message.text.lower() for keyword in ["grup", "group", "davet", "invite", "katıl", "join"]):
                await self._send_group_invites(user_id)
            
            # Normal yanıt
            else:
                await self._send_response(user_id, message.text)
            
            # Kullanıcının mesaj sayısını güncelle
            await self.user_service.update_user_stats(
                user_id=user_id,
                messages_received=1
            )
            
        except Exception as e:
            logger.error(f"Error handling private message: {str(e)}", exc_info=True)
    
    async def _send_welcome_message(self, user_id: int):
        """Yeni kullanıcıya karşılama mesajı gönder."""
        try:
            if not self.welcome_templates:
                await self._load_templates()
                
            if not self.welcome_templates:
                logger.warning("No welcome templates available")
                return
            
            template = random.choice(self.welcome_templates)
            welcome_text = template["content"]
            
            # Kullanıcı bilgilerini al
            user = await self.client.get_entity(user_id)
            first_name = user.first_name if hasattr(user, "first_name") else "Değerli Kullanıcı"
            
            # Kullanıcı adını yerleştir
            welcome_text = welcome_text.replace("{first_name}", first_name)
            
            # Mesajı gönder
            await self.client.send_message(user_id, welcome_text)
            
            # Biraz bekleyip hizmet listesini de gönder
            await asyncio.sleep(2)
            await self._send_service_list(user_id)
            
            # Aktiviteyi kaydet
            await self.user_service.log_dm_activity(
                user_id=user_id,
                content=welcome_text,
                message_type="welcome"
            )
            
            logger.info(f"Sent welcome message to user {user_id}")
                    
        except Exception as e:
            logger.error(f"Error sending welcome message to {user_id}: {str(e)}", exc_info=True)
    
    async def _send_service_list(self, user_id: int):
        """Kullanıcıya hizmet listesini gönder."""
        try:
            if not self.service_list:
                await self._load_service_list()
                
            if not self.service_list:
                logger.warning("No services available")
                return
                    
            # Hizmet tanıtım şablonunu seç
            if not self.service_templates:
                await self._load_templates()
                
            if not self.service_templates:
                logger.warning("No service templates available")
                return
            
            template = random.choice(self.service_templates)
            intro_text = template["content"]
            
            # Hizmet listesini oluştur
            service_text = "📋 *Hizmet Listesi*\n\n"
            for service in self.service_list:
                service_text += f"🔹 *{service['name']}*\n"
                service_text += f"  {service['description']}\n"
                service_text += f"  💰 Fiyat: {service['price']} TL\n\n"
            
            service_text += "\nBir hizmet satın almak veya detaylı bilgi almak için lütfen hizmet adını yazarak mesaj gönderin."
            
            # Önce giriş metnini gönder
            await self.client.send_message(user_id, intro_text)
            
            # Kısa bir bekleme
            await asyncio.sleep(1.5)
            
            # Hizmet listesini gönder
            await self.client.send_message(user_id, service_text, parse_mode='markdown')
            
            # Biraz bekleyip grup davetlerini de gönder
            await asyncio.sleep(3)
            await self._send_group_invites(user_id)
            
            # Aktiviteyi kaydet
            await self.user_service.log_dm_activity(
                user_id=user_id,
                content="Service list sent",
                message_type="service_list"
            )
            
            logger.info(f"Sent service list to user {user_id}")
            
        except Exception as e:
            logger.error(f"Error sending service list to {user_id}: {str(e)}", exc_info=True)
    
    async def _send_group_invites(self, user_id: int):
        """Kullanıcıya grup davetlerini gönder."""
        try:
            if not self.group_list:
                await self._load_group_list()
                
            if not self.group_list:
                logger.warning("No groups available for invite")
                return
            
            # Davet şablonunu seç
            if not self.group_invite_templates:
                await self._load_templates()
                
            if not self.group_invite_templates:
                logger.warning("No invite templates available")
                return
            
            template = random.choice(self.group_invite_templates)
            invite_text = template["content"]
            
            # Grup listesini oluştur
            group_text = "👥 *Gruplarımız*\n\n"
            for group in self.group_list:
                group_text += f"🔸 *{group['title']}*\n"
                if group.get('description'):
                    group_text += f"  {group['description']}\n"
                group_text += f"  👤 Üye Sayısı: {group['member_count']}\n"
                group_text += f"  🔗 Katılmak için: {group['invite_link']}\n\n"
            
            group_text += "\nGruplarımıza katılarak hizmetlerimizden faydalanabilir ve topluluk üyeleriyle etkileşimde bulunabilirsiniz."
            
            # Önce davet metnini gönder
            await self.client.send_message(user_id, invite_text)
            
            # Kısa bir bekleme
            await asyncio.sleep(1.5)
            
            # Grup listesini gönder
            await self.client.send_message(user_id, group_text, parse_mode='markdown')
            
            # Aktiviteyi kaydet
            await self.user_service.log_dm_activity(
                user_id=user_id,
                content="Group invites sent",
                message_type="group_invite"
            )
            
            logger.info(f"Sent group invites to user {user_id}")
            
        except Exception as e:
            logger.error(f"Error sending group invites to {user_id}: {str(e)}", exc_info=True)
    
    async def _send_response(self, user_id: int, message_text: str):
        """Kullanıcının mesajına özel yanıt gönder."""
        try:
            # Basit anahtar kelime yanıtları
            keywords = {
                "selam": ["Merhaba! Nasıl yardımcı olabilirim?", "Selam! Bugün size nasıl yardımcı olabilirim?"],
                "merhaba": ["Merhaba! Nasıl yardımcı olabilirim?", "Merhaba, size nasıl yardımcı olabilirim?"],
                "teşekkür": ["Rica ederim! Başka bir konuda yardıma ihtiyacınız olursa lütfen bildirin.", "Ne demek, her zaman yardımcı olmaktan memnuniyet duyarız!"],
                "fiyat": ["Hizmet fiyatlarımız için size hemen bir liste gönderiyorum.", "Size hizmet fiyatlarımızı hemen iletiyorum."]
            }
            
            lower_text = message_text.lower()
            
            # Anahtar kelime kontrolü
            for key, responses in keywords.items():
                if key in lower_text:
                    response = random.choice(responses)
                    await self.client.send_message(user_id, response)
                    
                    # Özel anahtar kelimelere göre ek işlemler
                    if key == "fiyat":
                        await asyncio.sleep(1)
                        await self._send_service_list(user_id)
                    
                    return
            
            # Genel yanıt
            general_responses = [
                "Mesajınız için teşekkürler! Size nasıl yardımcı olabilirim?",
                "Talebinizi aldım, kısa süre içinde size dönüş yapacağım.",
                "Mesajınız için teşekkür ederim. Hizmetlerimiz hakkında bilgi almak ister misiniz?",
                "Merhaba! Mesajınızı aldım. Size hizmetlerimiz ve gruplarımız hakkında bilgi vermemi ister misiniz?"
            ]
            
            response = random.choice(general_responses)
            await self.client.send_message(user_id, response)
            
            # Aktiviteyi kaydet
            await self.user_service.log_dm_activity(
                user_id=user_id,
                content=response,
                message_type="response",
                response_to=message_text[:100]  # İlk 100 karakter
            )
            
            logger.info(f"Sent response to user {user_id}")
            
        except Exception as e:
            logger.error(f"Error sending response to {user_id}: {str(e)}", exc_info=True)
    
    async def send_promotional_dm(self, user_id: int, promo_type: str = "service"):
        """Kullanıcıya tanıtım mesajı gönder."""
        try:
            # Son mesaj zaman kontrolü
            last_sent = self.last_dm_times.get(user_id, datetime.now() - timedelta(days=7))
            hours_since_last = (datetime.now() - last_sent).total_seconds() / 3600
            
            # Son 24 saat içinde mesaj göndermişsek, tekrar gönderme
            if hours_since_last < 24:
                logger.info(f"Skipping promo DM to user {user_id}, last message was {hours_since_last:.1f} hours ago")
                return False
            
            # Promosyon tipine göre içerik seç
            if promo_type == "service":
                await self._send_service_list(user_id)
            elif promo_type == "group":
                await self._send_group_invites(user_id)
            else:
                # Genel tanıtım mesajı
                if not self.service_templates:
                    await self._load_templates()
                
                template = random.choice(self.service_templates)
                promo_text = template["content"]
                
                await self.client.send_message(user_id, promo_text)
                
                # Biraz bekleyip servis listesini de gönder
                await asyncio.sleep(2)
                await self._send_service_list(user_id)
            
            # Son mesaj zamanını güncelle
            self.last_dm_times[user_id] = datetime.now()
            
            # Aktiviteyi kaydet
            await self.user_service.log_dm_activity(
                user_id=user_id,
                content=f"Promotional message ({promo_type})",
                message_type="promo"
            )
            
            # Kullanıcı stats güncelle
            await self.user_service.update_user_stats(
                user_id=user_id,
                promos_sent=1
            )
            
            logger.info(f"Sent promotional message to user {user_id}")
            return True
            
        except UserIsBlockedError:
            logger.warning(f"Cannot send promo to user {user_id}: User has blocked the bot")
            await self.user_service.update_user(user_id, {"is_blocked": True})
            return False
            
        except FloodWaitError as e:
            wait_seconds = e.seconds
            logger.warning(f"FloodWait for {wait_seconds}s when sending promo to user {user_id}")
            return False
            
        except Exception as e:
            logger.error(f"Error sending promo to {user_id}: {str(e)}", exc_info=True)
            return False
    
    async def start_promo_loop(self):
        """Tanıtım mesajı döngüsü."""
        logger.info("Starting promotional DM loop")
        self.running = True
        
        while self.running:
            try:
                # Aktif kullanıcıları getir (son 30 gün içinde etkileşimde bulunanlar)
                query = """
                    SELECT u.id, u.username, u.first_name, 
                           (SELECT COUNT(*) FROM user_activities 
                            WHERE user_id = u.id AND created_at > NOW() - INTERVAL '30 days') as activity_count,
                           u.last_dm_at, u.promos_sent
                    FROM users u
                    WHERE u.is_active = true 
                      AND u.is_blocked = false
                      AND (u.last_dm_at IS NULL OR u.last_dm_at < NOW() - INTERVAL '24 hours')
                    ORDER BY u.last_dm_at ASC NULLS FIRST
                    LIMIT 50
                """
                result = await self.db.execute(query)
                users = result.fetchall()
                
                if not users:
                    logger.info("No users available for promo, waiting for 1 hour...")
                    await asyncio.sleep(3600)  # 1 saat bekle
                    continue
                
                # Her kullanıcı için promosyon mesajı gönder
                for user in users:
                    if not self.running:
                        break
                        
                    user_id = user["id"]
                    
                    # Promosyon tipini belirle: Hizmet ya da grup daveti
                    promo_type = "service" if random.random() < 0.7 else "group"
                    
                    # Mesaj gönder
                    success = await self.send_promotional_dm(user_id, promo_type)
                    
                    if success:
                        # Kullanıcı son DM zamanını güncelle
                        query = """
                            UPDATE users
                            SET last_dm_at = NOW(), promos_sent = promos_sent + 1
                            WHERE id = :user_id
                        """
                        await self.db.execute(query, {"user_id": user_id})
                        await self.db.commit()
                        
                        # Günlük sayacı güncelle
                        self.sent_count += 1
                    
                    # Flood Wait'ten kaçınmak için her mesaj arasında bekle
                    await asyncio.sleep(random.randint(30, 60))
                
                # Tüm grup tamamlandığında biraz daha uzun bekle
                await asyncio.sleep(300)  # 5 dakika
                
            except Exception as e:
                logger.error(f"Error in promo loop: {str(e)}", exc_info=True)
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
            "name": self.service_name,
            "running": self.running,
            "initialized": self.initialized,
            "active_campaigns": len(self.active_campaigns),
            "templates": {k: len(v) for k, v in self.templates.items()},
            "sent_today": self.sent_count,
            "daily_limit": self.daily_limit,
            "send_interval": f"{self.send_interval}s",
            "last_reset": self.last_reset.isoformat()
        }

    async def _start(self) -> bool:
        """BaseService için başlatma metodu"""
        return await self.initialize()
        
    async def _stop(self) -> bool:
        """BaseService için durdurma metodu"""
        try:
            self.initialized = False
            self.running = False
            await self.cleanup()
            return True
        except Exception as e:
            logger.error(f"DirectMessageService durdurma hatası: {e}")
            return False 