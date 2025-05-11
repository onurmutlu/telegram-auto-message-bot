from datetime import datetime, timedelta
import asyncio
import random
from typing import Dict, List, Optional, Tuple
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from telethon import TelegramClient
from telethon.errors import (
    ChatAdminRequiredError, 
    ChatWriteForbiddenError, 
    FloodWaitError,
    UserBannedInChannelError
)

from app.core.config import settings
from app.db.session import get_db
from app.models.group import Group
from app.models.message import Message
from app.models.message_template import MessageTemplate
from app.services.base import BaseService
from app.services.analytics.activity_service import ActivityService

logger = logging.getLogger(__name__)

class EngagementService(BaseService):
    """
    Gruplara engaging mesajlar gönderme servisi.
    - Mesaj trafiğine göre gönderim sıklığını dinamik olarak ayarlar
    - Hata durumunda grupları geçici olarak soğutur
    - Engaging mesajları çeşitlendirir
    """
    
    service_name = "engagement_service"
    
    def __init__(self, client: TelegramClient, db: AsyncSession = None):
        super().__init__(name="engagement_service")
        self.client = client
        self.db = db
        self.activity_service = None
        self.initialized = False
        self.running = False
        
        # Soğutulan grupları izlemek için
        self.cooling_groups: Dict[int, datetime] = {}
        
        # Grup bazında son mesaj gönderim zamanlarını izlemek için
        self.last_message_times: Dict[int, datetime] = {}
        
        # Grup bazlı hata sayaçları
        self.error_counters: Dict[int, int] = {}
        
        # Engaging mesaj şablonları
        self.message_templates = []
        
        # Cevap şablonları
        self.reply_templates = []
    
    async def initialize(self):
        """Servisi başlat ve mesaj şablonlarını yükle."""
        self.db = self.db or await get_db().__anext__()
        self.activity_service = ActivityService(db=self.db)
        await self.activity_service.initialize()
        await self._load_message_templates()
        logger.info(f"EngagementService initialized with {len(self.message_templates)} message templates")
        self.initialized = True
        return True
    
    async def _load_message_templates(self):
        """Veritabanından mesaj şablonlarını yükle."""
        # Mesaj şablonlarını veritabanından yükleme
        query = """
            SELECT id, content, type, engagement_rate 
            FROM message_templates 
            WHERE is_active = true
            ORDER BY engagement_rate DESC
        """
        result = await self.db.execute(query)
        self.message_templates = result.fetchall()
        
        # Cevap şablonlarını yükle
        query = """
            SELECT id, content, type
            FROM message_templates 
            WHERE is_active = true AND type = 'reply'
        """
        result = await self.db.execute(query)
        self.reply_templates = result.fetchall()
    
    async def start_engagement_loop(self):
        """Ana engagement döngüsünü başlat."""
        logger.info("Starting engagement loop")
        self.running = True
        
        while self.running:
            try:
                # Hedef grupları al
                target_groups = await self._get_target_groups()
                
                if not target_groups:
                    logger.info("No target groups found, waiting for 5 minutes...")
                    await asyncio.sleep(300)  # 5 dakika bekle
                    continue
                
                # Her grup için mesaj gönderme süreci
                for group in target_groups:
                    if not self.running:
                        break
                        
                    group_id = group["id"]
                    
                    # Grup hala soğutuluyorsa atla
                    if await self._is_group_cooling(group_id):
                        continue
                    
                    # Grup için son mesaj zamanını kontrol et
                    if not await self._should_send_message(group):
                        continue
                    
                    # Mesaj göndermeyi dene
                    success = await self._send_engaging_message(group)
                    
                    # Mesaj gönderim başarısına göre işlem yap
                    if success:
                        # Başarılı gönderim, son gönderim zamanını güncelle
                        self.last_message_times[group_id] = datetime.now()
                        self.error_counters[group_id] = 0  # Hata sayacını sıfırla
                    else:
                        # Başarısız gönderim, hata sayacını artır
                        self.error_counters[group_id] = self.error_counters.get(group_id, 0) + 1
                        
                        # Belirli sayıda başarısız denemeden sonra grubu soğut
                        if self.error_counters[group_id] >= 3:
                            await self._cool_down_group(group_id)
                
                # İşlemler arasında kısa bekle
                await asyncio.sleep(10)
                
            except Exception as e:
                logger.error(f"Error in engagement loop: {str(e)}", exc_info=True)
                await asyncio.sleep(60)  # Hata durumunda 1 dakika bekle
    
    async def _get_target_groups(self) -> List[Dict]:
        """Mesaj gönderilecek hedef grupları belirle."""
        # Aktif grupları getir
        query = """
            SELECT g.id, g.chat_id, g.title, g.member_count, 
                   (SELECT COUNT(*) FROM messages WHERE group_id = g.id AND created_at > NOW() - INTERVAL '24 hours') as message_count,
                   g.is_admin, g.last_activity_at, g.created_at,
                   COALESCE(g.engagement_rate, 0) as engagement_rate
            FROM groups g
            WHERE g.is_active = true 
              AND g.is_banned = false 
              AND g.id NOT IN (SELECT group_id FROM group_cooldowns WHERE until > NOW())
            ORDER BY g.priority DESC, g.last_activity_at DESC
        """
        result = await self.db.execute(query)
        groups = result.fetchall()
        
        # Dict formatına dönüştür
        target_groups = []
        for row in groups:
            group_dict = dict(row)
            # Soğutulan grupları filtrele
            if group_dict["chat_id"] not in self.cooling_groups:
                target_groups.append(group_dict)
        
        return target_groups
    
    async def _is_group_cooling(self, group_id: int) -> bool:
        """Grup soğutma sürecinde mi kontrol et."""
        if group_id in self.cooling_groups:
            cool_until = self.cooling_groups[group_id]
            if datetime.now() < cool_until:
                return True
            else:
                # Soğutma süresi dolmuş, listeden çıkar
                del self.cooling_groups[group_id]
        return False
    
    async def _should_send_message(self, group: Dict) -> bool:
        """Gruba mesaj gönderme zamanı gelmiş mi kontrol et."""
        group_id = group["id"]
        chat_id = group["chat_id"]
        message_count = group["message_count"]
        is_admin = group["is_admin"]
        
        # Son mesaj gönderim zamanını kontrol et
        last_sent = self.last_message_times.get(chat_id, datetime.now() - timedelta(days=1))
        time_since_last = (datetime.now() - last_sent).total_seconds() / 60  # dakika
        
        # Mesaj trafiğine göre bekleme süresini ayarla
        if is_admin:
            # Admin olduğumuz gruplara daha sık mesaj gönder
            wait_time = random.randint(15, 30)  # 15-30 dakika
        elif message_count > 500:  # Son 24 saatte çok aktif
            wait_time = random.randint(3, 7)  # 3-7 dakika
        elif message_count > 200:  # Son 24 saatte aktif
            wait_time = random.randint(7, 15)  # 7-15 dakika
        elif message_count > 50:   # Son 24 saatte orta düzeyde aktif
            wait_time = random.randint(15, 30)  # 15-30 dakika
        else:  # Az aktif
            wait_time = random.randint(30, 60)  # 30-60 dakika
        
        # Grup büyüklüğüne göre bekleme süresini ayarla
        member_count = group.get("member_count", 0)
        if member_count > 5000:
            wait_time = max(wait_time, 10)  # En az 10 dakika bekle
        
        # Engagement rate'e göre bekleme süresini ayarla
        engagement_rate = group.get("engagement_rate", 0)
        if engagement_rate > 0.1:  # %10'dan fazla engagement
            wait_time = max(int(wait_time * 0.8), 3)  # %20 daha az bekle
        
        return time_since_last >= wait_time
    
    async def _select_message_template(self, group: Dict) -> Optional[Dict]:
        """Grup için uygun mesaj şablonunu seç."""
        if not self.message_templates:
            await self._load_message_templates()
            if not self.message_templates:
                return None
        
        # Son gönderilen mesajları kontrol et
        query = """
            SELECT template_id
            FROM messages
            WHERE group_id = :group_id
            ORDER BY created_at DESC
            LIMIT 5
        """
        result = await self.db.execute(query, {"group_id": group["id"]})
        recent_templates = [row[0] for row in result.fetchall()]
        
        # Son kullanılan şablonları filtreleme
        available_templates = [
            t for t in self.message_templates 
            if t["id"] not in recent_templates and t["type"] == 'engagement'
        ]
        
        if not available_templates:
            # Tüm şablonlar kullanılmışsa, en yüksek engagement rate'e sahip olanı seç
            available_templates = sorted(
                [t for t in self.message_templates if t["type"] == 'engagement'],
                key=lambda x: x["engagement_rate"],
                reverse=True
            )
        
        # En iyi şablonu seç
        if available_templates:
            # Biraz rastgelelik ekleyerek, yüksek engagement'lı şablonlara ağırlık ver
            weights = [max(0.1, t["engagement_rate"]) for t in available_templates]
            sum_weights = sum(weights)
            normalized_weights = [w/sum_weights for w in weights]
            
            template = random.choices(
                available_templates, 
                weights=normalized_weights, 
                k=1
            )[0]
            return template
        
        return None
    
    async def _send_engaging_message(self, group: Dict) -> bool:
        """Gruba engaging mesaj gönder."""
        try:
            template = await self._select_message_template(group)
            if not template:
                logger.warning(f"No suitable template found for group {group['title']}")
                return False
            
            # Mesaj içeriğini hazırla
            message_content = template["content"]
            
            # Grup adı gibi değişkenleri yerleştir
            message_content = message_content.replace("{group_name}", group["title"])
            
            # Mesajı gönder
            chat_id = group["chat_id"]
            message = await self.client.send_message(chat_id, message_content)
            
            # Mesajı veritabanına kaydet
            query = """
                INSERT INTO messages (group_id, message_id, content, template_id, sent_at, created_at)
                VALUES (:group_id, :message_id, :content, :template_id, NOW(), NOW())
                RETURNING id
            """
            params = {
                "group_id": group["id"],
                "message_id": message.id,
                "content": message_content,
                "template_id": template["id"]
            }
            await self.db.execute(query, params)
            await self.db.commit()
            
            logger.info(f"Sent engaging message to group {group['title']} (ID: {chat_id})")
            return True
            
        except FloodWaitError as e:
            # FloodWait hatasında belirtilen süre kadar bekle
            wait_seconds = e.seconds
            logger.warning(f"FloodWait for {wait_seconds}s in group {group['title']}")
            await self._cool_down_group(group["id"], minutes=max(wait_seconds//60 + 5, 30))
            return False
            
        except (ChatAdminRequiredError, ChatWriteForbiddenError, UserBannedInChannelError) as e:
            # Gruba mesaj gönderme izni yok, uzun süre soğut
            logger.warning(f"No permission to send message to group {group['title']}: {str(e)}")
            await self._cool_down_group(group["id"], minutes=60*24)  # 1 gün soğut
            
            # Grubu veritabanında güncelle
            query = """
                UPDATE groups
                SET is_banned = true, last_error = :error, updated_at = NOW()
                WHERE id = :group_id
            """
            await self.db.execute(query, {"group_id": group["id"], "error": str(e)})
            await self.db.commit()
            return False
            
        except Exception as e:
            logger.error(f"Error sending message to group {group['title']}: {str(e)}", exc_info=True)
            return False
    
    async def _cool_down_group(self, group_id: int, minutes: int = 30) -> None:
        """Grubu belirtilen süre kadar soğut."""
        cool_until = datetime.now() + timedelta(minutes=minutes)
        self.cooling_groups[group_id] = cool_until
        
        # Veritabanına kaydedelim
        query = """
            INSERT INTO group_cooldowns (group_id, until, reason, created_at)
            VALUES (:group_id, :until, 'Error threshold exceeded', NOW())
            ON CONFLICT (group_id) DO UPDATE
            SET until = :until, updated_at = NOW()
        """
        await self.db.execute(query, {"group_id": group_id, "until": cool_until})
        await self.db.commit()
        
        logger.info(f"Cooling down group {group_id} until {cool_until}")
    
    async def handle_message_reply(self, message):
        """Kullanıcıların engaging mesajlara verdiği cevaplara yanıt ver."""
        try:
            # Cevaplanan mesajın bizim gönderdiğimiz mesaj olup olmadığını kontrol et
            if not message.reply_to:
                return
            
            replied_msg_id = message.reply_to.reply_to_msg_id
            
            # Veritabanından kontrol et
            query = """
                SELECT id FROM messages 
                WHERE group_id = :group_id AND message_id = :message_id
            """
            params = {"group_id": message.chat_id, "message_id": replied_msg_id}
            result = await self.db.execute(query, params)
            our_message = result.fetchone()
            
            if not our_message:
                return  # Bizim mesajımıza cevap değil
            
            # Cevap şablonu seç
            if not self.reply_templates:
                await self._load_message_templates()
            
            if not self.reply_templates:
                logger.warning("No reply templates available")
                return
            
            template = random.choice(self.reply_templates)
            reply_text = template["content"]
            
            # Kullanıcı adını ekle
            sender = await message.get_sender()
            reply_text = reply_text.replace("{user}", f"@{sender.username}" if sender.username else sender.first_name)
            
            # Cevap ver
            await message.reply(reply_text)
            
            # Aktiviteyi kaydet
            await self.activity_service.log_interaction(
                user_id=sender.id,
                group_id=message.chat_id,
                message_id=message.id,
                interaction_type="reply_received"
            )
            
            logger.info(f"Replied to user @{sender.username} in group {message.chat_id}")
            
        except Exception as e:
            logger.error(f"Error handling message reply: {str(e)}", exc_info=True)
    
    async def cleanup(self):
        """Servis kapatılırken temizlik."""
        self.running = False
        logger.info("EngagementService cleanup completed")
        
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
            "active_groups": len(self.last_message_times),
            "cooling_groups": len(self.cooling_groups),
            "message_templates": len(self.message_templates),
            "reply_templates": len(self.reply_templates),
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
            logger.error(f"EngagementService durdurma hatası: {e}")
            return False
            
    async def _update(self) -> bool:
        """Periyodik güncelleme metodu"""
        # Şablonları yeniden yükle 
        await self._load_message_templates()
        return True 