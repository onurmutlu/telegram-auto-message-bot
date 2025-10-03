#!/usr/bin/env python3
# Telegram Bot - Engagement Service
import os
import asyncio
import logging
import random
import time
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from telethon import TelegramClient

from app.core.config import settings
from app.services.base_service import BaseService
from app.models.group import Group
from app.models.message import Message

logger = logging.getLogger(__name__)

class EngagementService(BaseService):
    """
    Gruplara otomatik mesaj gönderen servis.
    
    Bu servis şunları yapar:
    - Belirlenen aralıklarla gruplara etkileşim sağlayacak mesajlar gönderir
    - Grup aktivitelerine göre mesaj gönderme stratejileri belirler
    - Grup etkileşim istatistiklerini takip eder
    """
    
    def __init__(self, client: TelegramClient, db=None):
        """Engagement servisi başlat."""
        super().__init__(name="engagement_service", db=db)
        self.client = client
        self.service_name = "engagement_service"
        self.target_groups = []
        self.message_templates = []
        self.running = False
        self.last_message_time = {}  # Son mesaj gönderme zamanlarını tut
        self.interval = self._get_interval()
        self.mode = os.getenv("ENGAGE_MODE", "Grup aktivitesine göre")
        self.auto_engage = os.getenv("AUTO_ENGAGE", "True").lower() == "true"
        
        # Mesaj şablonlarını yükle
        self._load_message_templates()
        
    def _get_interval(self) -> int:
        """Mesaj gönderme aralığını (saniye cinsinden) döndürür."""
        interval_str = os.getenv("ENGAGE_INTERVAL", "1")
        try:
            # Sayı olarak çevir
            interval = int(interval_str)
            # Saat cinsinden ise saniyeye çevir
            return interval * 3600  # saat -> saniye
        except ValueError:
            # Varsayılan: 1 saat
            return 3600
    
    def _load_message_templates(self):
        """Mesaj şablonlarını yükler."""
        try:
            template_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "templates"
            )
            
            # Dizin yoksa oluştur
            os.makedirs(template_dir, exist_ok=True)
            
            template_file = os.path.join(template_dir, "engagement_messages.json")
            
            # Dosya yoksa oluştur
            if not os.path.exists(template_file):
                default_templates = {
                    "general": [
                        "Merhaba arkadaşlar! Bugün nasılsınız? 😊",
                        "Gruba yeni bir konu açmak istiyorum. Sizce ne konuşalım?",
                        "Bugün ilginç bir şey yaşadınız mı? Paylaşmak ister misiniz?",
                        "Herkesin güzel bir günü olsun! 🌟",
                        "Bu aralar neler izliyorsunuz/okuyorsunuz? Tavsiyelerinizi bekliyorum."
                    ],
                    "question": [
                        "Sizce teknoloji hayatımızı nasıl etkiliyor?",
                        "En sevdiğiniz film veya dizi nedir? Neden?",
                        "Eğer bir süper gücünüz olsaydı, ne olmasını isterdiniz?",
                        "Gelecekte hangi teknolojinin hayatımızı değiştireceğini düşünüyorsunuz?",
                        "Hangi konuda kendinizi geliştirmek istiyorsunuz?"
                    ],
                    "poll": [
                        "Evden çalışmak mı, ofiste çalışmak mı?",
                        "Android mi, iOS mu?",
                        "Sabah insanı mısınız, gece insanı mısınız?",
                        "Çay mı, kahve mi?",
                        "Kitap okumak mı, film izlemek mi?"
                    ]
                }
                
                with open(template_file, "w", encoding="utf-8") as f:
                    json.dump(default_templates, f, ensure_ascii=False, indent=4)
            
            # Şablonları yükle
            with open(template_file, "r", encoding="utf-8") as f:
                templates = json.load(f)
            
            # Tüm şablonları düzleştir
            self.message_templates = []
            for category, messages in templates.items():
                self.message_templates.extend(messages)
            
            logger.info(f"{len(self.message_templates)} mesaj şablonu yüklendi.")
            
        except Exception as e:
            logger.error(f"Mesaj şablonları yüklenirken hata: {e}")
            # Varsayılan şablonlar
            self.message_templates = [
                "Merhaba arkadaşlar! Bugün nasılsınız? 😊",
                "Bu grupta yeni konular konuşalım!",
                "Herkesin güzel bir günü olsun! 🌟"
            ]
    
    async def _load_target_groups(self):
        """Hedef grupları yükler."""
        try:
            if self.db and False:  # Veritabanı işlevselliği gerçeklenene kadar devre dışı
                # Veritabanından grupları al
                pass
            else:
                # DB yoksa, diyaloglardan grup bul
                self.target_groups = []
                
                dialogs = await self.client.get_dialogs()
                for dialog in dialogs:
                    if dialog.is_group or dialog.is_channel:
                        self.target_groups.append({
                            "entity_id": dialog.entity.id,
                            "title": dialog.entity.title,
                            "username": getattr(dialog.entity, "username", None),
                            "is_active": True
                        })
            
            logger.info(f"{len(self.target_groups)} hedef grup yüklendi.")
                
        except Exception as e:
            logger.error(f"Hedef grupları alırken hata: {e}")
            self.target_groups = []
    
    async def _select_target_group(self):
        """Mesaj gönderilecek grubu seçer."""
        if not self.target_groups:
            await self._load_target_groups()
            
        if not self.target_groups:
            logger.warning("Mesaj gönderilecek grup bulunamadı.")
            return None
        
        if self.mode == "Tüm gruplara":
            # Tüm gruplara sırayla gönder (son mesaj zamanına göre)
            current_time = time.time()
            
            # Hiç mesaj gönderilmemiş veya uzun süre önce gönderilmiş grupları bul
            eligible_groups = [
                group for group in self.target_groups
                if (group.get("entity_id") not in self.last_message_time or
                    current_time - self.last_message_time[group.get("entity_id")] > self.interval)
            ]
            
            if eligible_groups:
                return random.choice(eligible_groups)
            
        elif self.mode == "Grup aktivitesine göre":
            # En aktif gruba gönder
            # Burada normalde veritabanından grup aktiviteleri alınır
            # Basitlik için rastgele seçim yapıyoruz
            return random.choice(self.target_groups)
        
        elif self.mode == "Son mesajlara göre":
            # Uzun süredir mesaj atılmamış gruba gönder
            # Burada son mesaj zamanları kontrol edilir
            return random.choice(self.target_groups)
        
        elif self.mode == "Aktif kullanıcılara göre":
            # En çok aktif kullanıcı olan gruba gönder
            return random.choice(self.target_groups)
        
        # Varsayılan olarak rastgele bir grup seç
        return random.choice(self.target_groups)
    
    async def _select_message(self, group):
        """Gönderilecek mesajı seçer."""
        if not self.message_templates:
            return "Merhaba! Nasılsınız? 😊"
        
        # Rastgele bir mesaj seç
        return random.choice(self.message_templates)
    
    async def _send_message(self, group, message):
        """Gruba mesaj gönderir."""
        try:
            entity = None
            
            # Grup ID'sini al
            if isinstance(group, dict):
                entity_id = group.get("entity_id")
                username = group.get("username")
                
                if username:
                    entity = username
                else:
                    entity = entity_id
            else:
                entity_id = getattr(group, "entity_id", None)
                entity = entity_id
            
            if not entity:
                logger.error(f"Geçersiz grup: {group}")
                return False
            
            # Mesajı gönder
            sent_message = await self.client.send_message(entity, message)
            
            # Son mesaj zamanını güncelle
            self.last_message_time[entity_id] = time.time()
            
            logger.info(f"Mesaj gönderildi: {message[:30]}... (Grup: {getattr(group, 'title', entity)})")
            return True
            
        except Exception as e:
            logger.error(f"Mesaj gönderilirken hata: {e}")
            return False
    
    async def engage(self):
        """Gruplara otomatik mesaj gönderme işlemi."""
        if not self.auto_engage:
            logger.info("Otomatik mesajlaşma devre dışı.")
            return
        
        # Hedef grup seç
        group = await self._select_target_group()
        
        if not group:
            logger.warning("Uygun aktif grup bulunamadı veya mesaj listesi boş, 60 saniye bekleniyor...")
            await asyncio.sleep(60)
            return
        
        # Mesaj seç
        message = await self._select_message(group)
        
        # Mesajı gönder
        await self._send_message(group, message)
    
    async def run(self):
        """Engagement servisini çalıştır."""
        self.running = True
        logger.info(f"Engagement servisi başlatıldı. Aralık: {self.interval/3600} saat, Mod: {self.mode}")
        
        try:
            while self.running:
                if not self.client or not self.client.is_connected():
                    logger.warning("Telegram bağlantısı kapalı, engagement servisi beklemede...")
                    await asyncio.sleep(30)
                    continue
                
                await self.engage()
                
                # Bir sonraki mesaj için bekle (aralığın %10 rastgele değişimi ile)
                variation = random.uniform(0.9, 1.1)
                wait_time = int(self.interval * variation)
                logger.debug(f"Bir sonraki mesaj için {wait_time/3600:.2f} saat bekleniyor...")
                
                await asyncio.sleep(wait_time)
                
        except asyncio.CancelledError:
            logger.info("Engagement servisi iptal edildi.")
            self.running = False
        except Exception as e:
            logger.error(f"Engagement servisi çalışırken hata: {e}")
            self.running = False
    
    async def start(self):
        """Servisi başlat."""
        if self.running:
            logger.warning("Engagement servisi zaten çalışıyor.")
            return
        
        self.task = asyncio.create_task(self.run())
        logger.info("Engagement servisi başlatıldı.")
    
    async def stop(self):
        """Servisi durdur."""
        self.running = False
        
        if hasattr(self, 'task') and self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                logger.info("Engagement servisi durduruldu.")

    async def initialize(self):
        """Servisi başlat ve şablonları yükle."""
        # Şablonları yükle
        self._load_message_templates()
        
        # Hedef grupları yükle
        await self._load_target_groups()
        
        self.initialized = True
        logger.info(f"Engagement servisi başlatıldı: {len(self.message_templates)} mesaj şablonu ve {len(self.target_groups)} hedef grup")
        return True

    async def _scan_and_analyze_groups(self):
        """Grup durumlarını analiz eder."""
        logger.info("Grup analizi yapılıyor...")
        try:
            # Kullanıcının katıldığı tüm diyalogları al
            dialogs = await self.client.get_dialogs()
            active_groups = []
            
            for dialog in dialogs:
                if dialog.is_group or dialog.is_channel:
                    try:
                        # Grup ID'sini al
                        group_id = dialog.entity.id
                        title = dialog.entity.title
                        entity = dialog.entity
                        
                        # Son aktiviteyi al
                        last_message_time = dialog.date if dialog.date else None
                        
                        # Grup bilgilerini ekle
                        active_groups.append({
                            "entity_id": group_id,
                            "title": title,
                            "last_activity": last_message_time,
                            "entity": entity,
                            "is_active": True
                        })
                    except Exception as e:
                        logger.error(f"Grup analizi sırasında hata: {e} - Grup: {getattr(dialog, 'title', 'Bilinmeyen')}")
            
            # Hedef grupları güncelle
            self.target_groups = active_groups
            logger.info(f"{len(active_groups)} aktif grup bulundu.")
            
            return active_groups
        except Exception as e:
            logger.error(f"Grup analizi sırasında genel hata: {e}")
            return [] 