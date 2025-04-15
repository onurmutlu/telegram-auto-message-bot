"""
# ============================================================================ #
# Dosya: announcement_service.py
# Yol: /Users/siyahkare/code/telegram-bot/bot/services/announcement_service.py
# İşlev: Gruplarda duyuru ve tanıtım mesajları gönderimi.
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

import asyncio
import json
import logging
import os
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any, Set, Optional, Tuple

from bot.services.base_service import BaseService
from bot.utils.adaptive_rate_limiter import AdaptiveRateLimiter

logger = logging.getLogger(__name__)

class AnnouncementService(BaseService):
    """
    Gruplarda duyuru ve tanıtım mesajları gönderimi yapan servis.
    
    Bu servis:
    1. Farklı grup kategorilerine göre özelleştirilmiş duyurular yapar
    2. Grup trafiğine göre akıllı mesaj gönderimleri yapar
    3. Kendi gruplarımızda düzenli tanıtımlar yapar
    4. Riskli gruplarda dikkatli ve seyrek mesaj gönderir
    
    Attributes:
        client: Telegram istemcisi
        config: Bot yapılandırma nesnesi
        db: Veritabanı nesnesi
        group_categories: Grup kategorileri
    """
    
    def __init__(self, client, config, db, stop_event=None):
        """
        AnnouncementService sınıfının başlatıcısı.
        
        Args:
            client: Telegram istemcisi
            config: Bot yapılandırma nesnesi
            db: Veritabanı nesnesi
            stop_event: Durdurma sinyali
        """
        super().__init__("announcement", client, config, db, stop_event)
        
        # Durum takibi
        self.running = False
        self.announcement_count = 0
        self.last_announcement_time = None
        
        # Grup kategorileri
        self.group_categories = {
            'own_groups': set(),     # Kendi gruplarımız
            'safe_groups': set(),    # Güvenli gruplar
            'risky_groups': set(),   # Riskli gruplar (dikkatli olunmalı)
            'high_traffic_groups': set(),  # Yüksek trafikli gruplar
        }
        
        # Grupların son mesaj zamanları
        self.last_group_message = {}
        
        # Mesajlar için rate_limiter
        self.rate_limiter = AdaptiveRateLimiter(
            initial_rate=2,  # Başlangıçta dakikada 2 mesaj
            period=60,
            error_backoff=2.0,
            max_jitter=3.0
        )
        
        # Servisler
        self.services = {}
        
        # Ayarları yükle
        self._load_settings()
        self._load_templates()
    
    def _load_settings(self):
        """Duyuru servisi ayarlarını yükler."""
        # Yapılandırma dosyasından veya çevre değişkenlerinden
        self.announcement_interval_minutes = self.config.get_setting('announcement_interval_minutes', 120)
        
        # Grup kategorilerine göre gönderim aralıkları (saat)
        self.cooldown_hours = {
            'own_groups': 1,           # Kendi gruplarımızda sık mesaj
            'safe_groups': 4,          # Güvenli gruplarda orta sıklıkta
            'risky_groups': 12,        # Riskli gruplarda çok nadir
            'high_traffic_groups': 6   # Yüksek trafikli gruplarda orta-nadir
        }
        
        # Kendi gruplarımızı yükle
        own_groups = os.getenv("GROUP_LINKS", "").split(',')
        self.own_groups = [g.strip() for g in own_groups if g.strip()]
        
        # Grup kategorileri için batchler
        self.batch_size = {
            'own_groups': 3,           # Kendi gruplarımızın hepsine
            'safe_groups': 5,          # Güvenli gruplara toplu
            'risky_groups': 1,         # Riskli gruplara tek tek
            'high_traffic_groups': 3   # Yüksek trafikli gruplara orta batch
        }
        
        self.debug = self.config.get_setting('debug', False)
        
        logger.info("Duyuru servisi ayarları yüklendi")
    
    def _load_templates(self):
        """Duyuru mesaj şablonlarını yükler."""
        try:
            # Şablon dosyası
            with open('data/announcements.json', 'r', encoding='utf-8') as f:
                self.announcement_templates = json.load(f)
            
            # Şablon kontrolleri
            if not self.announcement_templates:
                logger.warning("Duyuru şablonları boş! data/announcements.json dosyasını kontrol edin.")
                self.announcement_templates = {
                    "own_groups": {
                        "promotion": ["Grubumuzun yeni özelliklerini denediniz mi? t.me/{}"]
                    }
                }
                
            # Log şablon sayılarını
            for category, content in self.announcement_templates.items():
                for msg_type, templates in content.items():
                    logger.debug(f"{category} - {msg_type}: {len(templates)} şablon")
                    
        except Exception as e:
            logger.error(f"Duyuru şablonları yüklenirken hata: {str(e)}")
            # Basit varsayılan şablon
            self.announcement_templates = {
                "own_groups": {
                    "promotion": ["Grubumuzun yeni özelliklerini denediniz mi? t.me/{}"]
                }
            }
    
    async def initialize(self) -> bool:
        """
        Servisi başlatır ve verileri yükler.
        
        Returns:
            bool: Başarılı ise True
        """
        # Temel servisi başlat
        await super().initialize()
        
        # Grupları kategorilere ayır
        await self._categorize_groups()
        
        logger.info(f"Duyuru servisi başlatıldı")
        return True
    
    async def _categorize_groups(self):
        """Grupları kategorilere ayırır."""
        try:
            # Grup kategorilerini sıfırla
            for category in self.group_categories:
                self.group_categories[category] = set()
                
            # Veritabanından tüm grupları al
            all_groups = await self._get_all_groups()
                
            if not all_groups:
                logger.warning("Veritabanında grup bulunamadı!")
                return
            
            # Grupları kategorilere ayır
            for group in all_groups:
                group_id = group.get('group_id')
                username = group.get('username', '')
                name = group.get('name', '')
                member_count = group.get('member_count', 0)
                is_public = group.get('is_public', False)
                can_send_messages = group.get('can_send_messages', False)
                
                # Mesaj gönderilemeyen grupları atla
                if not can_send_messages:
                    continue
                
                # 1. Kendi gruplarımız
                if username in self.own_groups or any(own in name.lower() for own in self.own_groups):
                    self.group_categories['own_groups'].add(group_id)
                    continue
                
                # 2. Güvenli gruplar (çeşitli kriterlere göre)
                if is_public and member_count > 500:
                    self.group_categories['safe_groups'].add(group_id)
                    continue
                
                # 3. Yüksek trafikli gruplar
                if member_count > 1000:
                    self.group_categories['high_traffic_groups'].add(group_id)
                    continue
                
                # 4. Geriye kalanlar riskli gruplar
                self.group_categories['risky_groups'].add(group_id)
                
            # Log kategorileri
            for category, groups in self.group_categories.items():
                logger.info(f"{category}: {len(groups)} grup")
                
        except Exception as e:
            logger.error(f"Grupları kategorilere ayırırken hata: {str(e)}")
    
    async def _get_all_groups(self):
        """
        Tüm grupları getirir.
        
        Returns:
            List[Dict]: Grup listesi
        """
        try:
            # Önce veritabanından grupları almaya çalış
            if hasattr(self.db, 'get_all_groups'):
                try:
                    groups = await self.db.get_all_groups()  # await kullanımı
                    return groups  # direkt objeyi dön
                except Exception as e:
                    logger.error(f"get_all_groups hatası: {str(e)}")
            
            # Veritabanında metod yoksa diğer alternatifleri dene
            if hasattr(self.db, 'get_groups'):
                try:
                    groups = await self._run_async_db_method(self.db.get_groups)
                    return groups
                except Exception as e:
                    logger.error(f"get_groups hatası: {str(e)}")
            
            # Diğer alternatifler...
            
        except Exception as e:
            logger.error(f"Grupları alma hatası: {str(e)}")
            return []

    async def categorize_groups(self, groups):
        """
        Grupları kategorilere ayırır.
        """
        try:
            # groups bir coroutine değil, bir liste olmalı
            if not isinstance(groups, list):
                logger.warning("Gruplar için geçersiz tip, boş liste kullanılıyor")
                groups = []
                
            # Boş kategoriler oluştur
            categories = {
                'large': [],
                'medium': [],
                'small': []
            }
            
            # Grupları üye sayılarına göre kategorize et
            for group in groups:
                member_count = group.get('members_count', 0)
                
                if member_count > 500:
                    categories['large'].append(group)
                elif member_count > 100:
                    categories['medium'].append(group)
                else:
                    categories['small'].append(group)
                    
            return categories
            
        except Exception as e:
            logger.error(f"Grupları kategorilere ayırırken hata: {str(e)}")
            return {'large': [], 'medium': [], 'small': []}
    
    async def start(self) -> bool:
        """
        Duyuru servisini başlatır.
        
        Returns:
            bool: Başarılı ise True
        """
        if self.running:
            return True
            
        self.running = True
        logger.info("Duyuru servisi başlatılıyor...")
        
        # Otomatik duyuru görevi
        asyncio.create_task(self._announcement_loop())
        
        return True
    
    async def stop(self) -> None:
        """
        Duyuru servisini durdurur.
        
        Returns:
            None
        """
        self.running = False
        logger.info("Duyuru servisi durduruluyor...")
        
        # Temel servisin stop metodunu çağır
        await super().stop()
    
    async def _announcement_loop(self):
        """Periyodik duyuru gönderimlerini yönetir."""
        logger.info("Duyuru döngüsü başlatıldı")
        
        while self.running and not self.stop_event.is_set():
            try:
                # Her kategori için bir turda bir grup seçip mesaj gönder
                for category, groups in self.group_categories.items():
                    if not groups:
                        continue
                        
                    # Bu kategoriden kaç gruba mesaj göndereceğiz?
                    batch_count = min(self.batch_size.get(category, 1), len(groups))
                    
                    # Gruba göre duyuru türü seç (promotion, services, showcase, ads)
                    announcement_type = random.choice(['promotion', 'services', 'showcase', 'ads'])
                    
                    # Bu kategoriden uygun grupları seç
                    eligible_groups = await self._get_eligible_groups(category)
                    if not eligible_groups:
                        logger.debug(f"{category} kategorisinde uygun grup bulunamadı")
                        continue
                        
                    # Batch'ten fazla grup varsa random örneklem al
                    selected_groups = random.sample(eligible_groups, min(batch_count, len(eligible_groups)))
                    
                    # Seçilen gruplara mesaj gönder
                    for group_id in selected_groups:
                        success = await self._send_announcement_to_group(group_id, category, announcement_type)
                        if success:
                            self.last_group_message[group_id] = datetime.now()
                            self.announcement_count += 1
                            
                        # Her mesaj arasında biraz bekle
                        await asyncio.sleep(2 + random.random() * 3)
                
                # Bir sonraki tura kadar bekle
                interval = self.announcement_interval_minutes * 60
                logger.debug(f"Bir sonraki duyuru turu için {interval} saniye bekleniyor")
                await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                logger.info("Duyuru döngüsü iptal edildi")
                break
            except Exception as e:
                logger.error(f"Duyuru döngüsünde hata: {str(e)}")
                await asyncio.sleep(300)  # Hata durumunda 5 dakika bekle
    
    async def _get_eligible_groups(self, category: str) -> List[int]:
        """
        Mesaj gönderilebilecek uygun grupları belirler.
        
        Args:
            category: Grup kategorisi
            
        Returns:
            List[int]: Uygun grup ID'leri
        """
        eligible_groups = []
        now = datetime.now()
        cooldown_hours = self.cooldown_hours.get(category, 6)
        
        for group_id in self.group_categories[category]:
            # Bu gruba en son ne zaman mesaj gönderdik?
            last_msg_time = self.last_group_message.get(group_id)
            
            # Hiç gönderilmemişse veya cooldown süresi geçmişse
            if not last_msg_time or (now - last_msg_time) >= timedelta(hours=cooldown_hours):
                eligible_groups.append(group_id)
        
        return eligible_groups
    
    async def _send_announcement_to_group(self, group_id: int, category: str, announcement_type: str) -> bool:
        """
        Belirli bir gruba duyuru mesajı gönderir.
        
        Args:
            group_id: Grup ID
            category: Grup kategorisi
            announcement_type: Duyuru türü
            
        Returns:
            bool: Başarılı ise True
        """
        try:
            # Önce hız sınırlayıcısını kontrol et
            wait_time = self.rate_limiter.get_wait_time()
            if wait_time > 0:
                logger.debug(f"Rate limit - {wait_time:.1f} saniye bekleniyor")
                await asyncio.sleep(wait_time)
            
            # Grup bilgilerini al
            group_info = None
            if hasattr(self.db, 'get_group_info'):
                group_info = await self._run_async_db_method(self.db.get_group_info, group_id)
                
            if not group_info:
                logger.warning(f"Grup bilgisi alınamadı: {group_id}")
                return False
            
            # Şablon seç
            template = self._choose_announcement_template(category, announcement_type)
            if not template:
                logger.warning(f"{category}/{announcement_type} için şablon bulunamadı")
                return False
            
            # Grup linklerini hazırla
            group_links = self._parse_group_links()
            if not group_links:
                logger.warning("Mesaja eklemek için grup linki bulunamadı")
                return False
                
            # Link seç ve mesajı formatla
            link = random.choice(group_links)
            message = template.format(link)
            
            # Mesajı gönder
            await self.client.send_message(group_id, message)
            logger.info(f"Duyuru gönderildi - Grup: {group_id}, Tür: {announcement_type}")
            
            # Rate limiter'ı güncelle
            self.rate_limiter.mark_used()
            
            return True
            
        except Exception as e:
            logger.error(f"Duyuru gönderme hatası (Grup {group_id}): {str(e)}")
            self.rate_limiter.register_error(e)
            return False
    
    def _choose_announcement_template(self, category: str, announcement_type: str) -> str:
        """
        Belirtilen kategori ve tür için bir duyuru şablonu seçer.
        
        Args:
            category: Grup kategorisi
            announcement_type: Duyuru türü
            
        Returns:
            str: Şablon metni veya None
        """
        try:
            # Kategori için şablonlar var mı?
            if category not in self.announcement_templates:
                category = "own_groups"  # Fallback to default
            
            category_templates = self.announcement_templates[category]
            
            # Türe göre şablonlar var mı?
            if announcement_type not in category_templates:
                announcement_type = "promotion"  # Fallback to default
            
            templates = category_templates[announcement_type]
            
            if templates:
                return random.choice(templates)
            else:
                return None
                
        except Exception as e:
            logger.error(f"Şablon seçme hatası: {str(e)}")
            return None
            
    def _parse_group_links(self) -> List[str]:
        """Grup linklerini çevre değişkenlerinden veya yapılandırmadan yükler."""
        # Çevre değişkeninden deneyelim
        links_str = os.getenv("GROUP_LINKS", "")
        
        # Virgülle ayrılmış değerleri dizi haline getir
        links = [link.strip() for link in links_str.split(',') if link.strip()]
        
        # Bağlantı yoksa fallback
        if not links:
            links = ["arayisplatin"]
        
        return links
    
    def set_services(self, services):
        """
        Diğer servislere referansları ayarlar.
        
        Args:
            services: Servis adı -> servis nesnesi eşleşmesi
        """
        self.services = services
        logger.debug(f"Duyuru servisi diğer servislere bağlandı")
    
    async def send_custom_announcement(self, message: str, category: str = None, group_ids: List[int] = None) -> int:
        """
        Özel bir duyuru mesajı gönderir.
        
        Args:
            message: Gönderilecek mesaj
            category: Hedef grup kategorisi (belirtilmezse tüm kategoriler)
            group_ids: Belirli grup ID'leri (belirtilmezse kategoriye göre)
            
        Returns:
            int: Başarıyla gönderilen mesaj sayısı
        """
        target_groups = []
        
        # Hedef grupları belirle
        if group_ids:
            target_groups = group_ids
        elif category and category in self.group_categories:
            target_groups = list(self.group_categories[category])
        else:
            # Tüm kategorilerden grupları al
            for groups in self.group_categories.values():
                target_groups.extend(groups)
                
        if not target_groups:
            logger.warning("Özel duyuru için hedef grup bulunamadı")
            return 0
        
        # Mesajları gönder
        sent_count = 0
        for group_id in target_groups:
            try:
                # Hız sınırı kontrolü
                wait_time = self.rate_limiter.get_wait_time()
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                    
                await self.client.send_message(group_id, message)
                self.rate_limiter.mark_used()
                sent_count += 1
                
                # Son mesaj zamanını güncelle
                self.last_group_message[group_id] = datetime.now()
                
                # Kısa bir bekleme
                await asyncio.sleep(1 + random.random() * 2)
                
            except Exception as e:
                logger.error(f"Özel duyuru gönderirken hata (Grup {group_id}): {str(e)}")
                self.rate_limiter.register_error(e)
                
        logger.info(f"Özel duyuru gönderimi tamamlandı: {sent_count}/{len(target_groups)} başarılı")
        return sent_count
    
    async def get_status(self) -> Dict[str, Any]:
        """
        Servisin mevcut durumunu döndürür.
        
        Returns:
            Dict: Servis durum bilgileri
        """
        status = await super().get_status()
        
        # Grup kategorilerini say
        categories_count = {
            category: len(groups)
            for category, groups in self.group_categories.items()
        }
        
        status.update({
            'announcement_count': self.announcement_count,
            'last_announcement': self.last_announcement_time.strftime('%Y-%m-%d %H:%M:%S') if self.last_announcement_time else None,
            'group_categories': categories_count
        })
        
        return status
    
    async def get_statistics(self) -> Dict[str, Any]:
        """
        Servis istatistiklerini döndürür.
        
        Returns:
            Dict: Servis istatistikleri
        """
        return {
            'total_sent': self.announcement_count,
            'categories': {
                category: len(groups)
                for category, groups in self.group_categories.items()
            }
        }
    
    async def _run_async_db_method(self, method, *args, **kwargs):
        """Veritabanı metodunu thread-safe biçimde çalıştırır."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, 
            lambda: method(*args, **kwargs)
        )
    
    async def run(self):
        """Duyuru servisi için ana döngü."""
        logger.info("Duyuru servisi çalışıyor...")
        while self.running and not self.stop_event.is_set():
            try:
                # Duyuru işlemlerini belirli aralıklarla yap
                await asyncio.sleep(60)  # 1 dakika bekle
                # Burada duyuru gönderimi için gerekli işlemleri yapabilirsiniz
            except asyncio.CancelledError:
                logger.info("Duyuru servis döngüsü iptal edildi")
                break
            except Exception as e:
                logger.error(f"Duyuru servisi çalışırken hata: {str(e)}")
        
        logger.info("Duyuru servis döngüsü sonlandı")