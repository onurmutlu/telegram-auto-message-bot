"""
Telegram Bot Duyuru Servisi

Gruplarda duyuru ve tanıtım mesajları gönderimi.
"""

import asyncio
import json
import os
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any, Set, Optional, Tuple

from app.services.base_service import BaseService
from app.utils.adaptive_rate_limiter import AdaptiveRateLimiter
from app.core.logger import get_logger
from telethon import errors

logger = get_logger(__name__)

class AnnouncementService(BaseService):
    """
    Gruplarda duyuru ve tanıtım mesajları gönderimi yapan servis.
    
    Bu servis:
    1. Farklı grup kategorilerine göre özelleştirilmiş duyurular yapar
    2. Grup trafiğine göre akıllı mesaj gönderimleri yapar
    3. Kendi gruplarımızda düzenli tanıtımlar yapar
    4. Riskli gruplarda dikkatli ve seyrek mesaj gönderir
    
    Attributes:
        group_categories: Grup kategorileri
    """
    
    service_name = "announcement_service"
    default_interval = 600  # 10 dakika
    
    def __init__(self, **kwargs):
        """
        AnnouncementService sınıfının başlatıcısı.
        
        Args:
            **kwargs: Temel servis parametreleri
        """
        super().__init__(**kwargs)
        
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
            initial_rate=20,  # Başlangıçta dakikada 20 mesaj
            period=10,        # 10 saniyelik periyot
            error_backoff=1.1, # Hata durumunda 1.1x yavaşlama
            max_jitter=1.0    # Maksimum 1 saniyelik rastgele gecikme
        )
        
        # Servisler
        self.services = {}
        
        # Ayarları yükle
        self._load_settings()
        self._load_templates()
        
        self.announcements = {}
        self.stats = {
            'total_sent': 0,
            'last_sent': None
        }
    
    def _load_settings(self):
        """Duyuru servisi ayarlarını yükler."""
        # Yapılandırma dosyasından veya çevre değişkenlerinden
        self.announcement_interval_minutes = self.config.get('announcement_interval_minutes', 10)
        
        # Grup kategorilerine göre gönderim aralıkları (saat)
        self.cooldown_hours = {
            'own_groups': 0.1,        # Kendi gruplarımızda çok sık mesaj
            'safe_groups': 0.25,      # Güvenli gruplarda sık mesaj
            'risky_groups': 0.5,      # Riskli gruplarda daha sık
            'high_traffic_groups': 0.3  # Yüksek trafikli gruplarda sık mesaj
        }
        
        # Kendi gruplarımızı yükle
        own_groups = os.getenv("GROUP_LINKS", "").split(',')
        self.own_groups = [g.strip() for g in own_groups if g.strip()]
        
        # Grup kategorileri için batchler
        self.batch_size = {
            'own_groups': 20,           # Kendi gruplarımızın hepsine
            'safe_groups': 30,          # Güvenli gruplara toplu
            'risky_groups': 15,         # Riskli gruplara çoklu
            'high_traffic_groups': 20   # Yüksek trafikli gruplara toplu
        }
        
        self.debug = self.config.get('debug', False)
        
        logger.info("Duyuru servisi ayarları yüklendi")
    
    def _load_templates(self):
        """Duyuru mesaj şablonlarını yükler."""
        try:
            # Şablon dosyası
            templates_path = 'data/announcements.json'
            if os.path.exists(templates_path):
                with open(templates_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Şablon formatını kontrol et ve yapılandır
                if isinstance(data, dict):
                    # Yeni format - ID'ye göre şablonlar
                    self.announcement_templates = {}
                    
                    # Şablonları grup tipine göre kategorize et
                    for template_id, template_info in data.items():
                        if isinstance(template_info, dict) and "group_type" in template_info:
                            group_type = template_info["group_type"]
                            category = template_info.get("category", "general")
                            
                            # Gerekirse grup tipine ait sözlüğü oluştur
                            if group_type not in self.announcement_templates:
                                self.announcement_templates[group_type] = {}
                            
                            # Gerekirse kategoriye ait listeyi oluştur
                            if category not in self.announcement_templates[group_type]:
                                self.announcement_templates[group_type][category] = []
                            
                            # Şablonu ekle
                            self.announcement_templates[group_type][category].append(template_info["content"])
                            
                    # Log şablon sayılarını
                    for group_type, categories in self.announcement_templates.items():
                        for category, templates in categories.items():
                            logger.debug(f"{group_type} - {category}: {len(templates)} şablon")
                else:
                    logger.warning("Geçersiz şablon formatı! Sözlük formatı bekleniyor")
                    self._set_default_templates()
            else:
                logger.warning(f"Şablon dosyası bulunamadı: {templates_path}")
                self._set_default_templates()
                
        except Exception as e:
            logger.error(f"Duyuru şablonları yüklenirken hata: {str(e)}")
            self._set_default_templates()
    
    def _set_default_templates(self):
        """Varsayılan şablonları ayarlar."""
        self.announcement_templates = {
            "own_groups": {
                "promotion": ["Grubumuzun yeni özelliklerini denediniz mi? t.me/{}"]
            },
            "safe_groups": {
                "promotion": ["Merhaba! Telegram grubumuza katılmak ister misiniz? t.me/{}"]
            },
            "risky_groups": {
                "promotion": ["t.me/{} - Yeni Telegram grubumuza göz atın"]
            },
            "high_traffic_groups": {
                "promotion": ["t.me/{} - En güncel içerikler için"]
            }
        }
    
    async def _start(self) -> bool:
        """
        Servisi başlatır ve verileri yükler.
        
        Returns:
            bool: Başarılı ise True
        """
        try:
            logger.info("Duyuru servisi başlatılıyor")
            
            # Grupları kategorilere ayır
            await self._categorize_groups()
            
            logger.info(f"Duyuru servisi başlatıldı")
            return True
            
        except Exception as e:
            logger.exception(f"Duyuru servisi başlatma hatası: {str(e)}")
            return False
    
    async def _stop(self) -> bool:
        """
        Servisi durdurur.
        
        Returns:
            bool: Başarılı ise True
        """
        try:
            logger.info("Duyuru servisi durduruluyor")
            
            self.running = False
            
            logger.info("Duyuru servisi durduruldu")
            return True
            
        except Exception as e:
            logger.exception(f"Duyuru servisi durdurma hatası: {str(e)}")
            return False
    
    async def _update(self) -> None:
        """Periyodik duyuru gönderimlerini gerçekleştirir."""
        try:
            # Grupları kategorilere göre güncelle
            await self._categorize_groups()
            
            # Her kategori için duyuru gönder
            for category in self.group_categories:
                await self._send_announcements_to_category(category)
                
        except Exception as e:
            logger.exception(f"Duyuru güncelleme hatası: {str(e)}")
    
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
            await self.categorize_groups(all_groups)
            
            # Grupların sayısını logla
            for category, groups in self.group_categories.items():
                logger.debug(f"{category}: {len(groups)} grup")
                
        except Exception as e:
            logger.exception(f"Grupları kategorilere ayırma hatası: {str(e)}")
    
    async def _get_all_groups(self):
        """Veritabanından tüm grupları getirir."""
        if 'group_service' in self.services:
            return await self.services['group_service'].get_all_groups()
        return []
    
    async def categorize_groups(self, groups):
        """
        Grupları özelliklerine göre kategorilere ayırır.
        
        Args:
            groups: Grup listesi
        """
        for group in groups:
            group_id = group.get('group_id') or group.get('id')
            
            # Kendi gruplarımız
            if group.get('is_admin', False) or group.get('is_owner', False):
                self.group_categories['own_groups'].add(group_id)
                
            # Güvenli gruplar
            elif group.get('is_verified', False) or group.get('is_safe', False):
                self.group_categories['safe_groups'].add(group_id)
                
            # Riskli gruplar
            elif group.get('is_restricted', False) or group.get('is_risky', False):
                self.group_categories['risky_groups'].add(group_id)
                
            # Yüksek trafikli gruplar
            elif group.get('member_count', 0) > 1000:
                self.group_categories['high_traffic_groups'].add(group_id)
                
            # Varsayılan olarak güvenli gruplara ekle
            else:
                self.group_categories['safe_groups'].add(group_id)
    
    async def _send_announcements_to_category(self, category: str) -> int:
        """
        Belirli bir kategorideki gruplara duyuru gönderir.
        
        Args:
            category: Grup kategorisi
            
        Returns:
            int: Gönderilen duyuru sayısı
        """
        # Kategorideki grupları al
        eligible_groups = await self._get_eligible_groups(category)
        
        if not eligible_groups:
            return 0
            
        # Kategoriye göre duyuru tipini belirle
        announcement_type = "promotion"  # Varsayılan
        
        # Batch boyutunu belirle
        batch_size = min(self.batch_size.get(category, 10), len(eligible_groups))
        
        # Rasgele grupları seç
        selected_groups = random.sample(eligible_groups, batch_size)
        
        # Seçilen gruplara duyuru gönder
        success_count = 0
        for group_id in selected_groups:
            success = await self._send_announcement_to_group(group_id, category, announcement_type)
            if success:
                success_count += 1
                
        return success_count
    
    async def _get_eligible_groups(self, category: str) -> List[int]:
        """
        Duyuru göndermeye uygun grupları belirler.
        
        Args:
            category: Grup kategorisi
            
        Returns:
            List[int]: Uygun grupların ID listesi
        """
        # Kategorideki tüm grupları al
        all_groups = self.group_categories.get(category, set())
        
        # Şu anki zaman
        now = datetime.now()
        
        # Cooldown süresi
        cooldown_hours = self.cooldown_hours.get(category, 24)
        cooldown = timedelta(hours=cooldown_hours)
        
        # Uygun grupları filtrele
        eligible_groups = []
        for group_id in all_groups:
            # Son mesaj zamanını kontrol et
            last_time = self.last_group_message.get(group_id)
            
            # Grup hiç mesaj almamış veya cooldown süresi geçmişse
            if not last_time or (now - last_time) > cooldown:
                eligible_groups.append(group_id)
                
        return eligible_groups
    
    async def _send_announcement_to_group(self, group_id: int, category: str, announcement_type: str) -> bool:
        """
        Belirli bir gruba duyuru gönderir.
        
        Args:
            group_id: Grup ID
            category: Grup kategorisi
            announcement_type: Duyuru tipi
            
        Returns:
            bool: Başarılı ise True
        """
        try:
            if not self.client:
                logger.error("Telegram istemcisi bulunamadı!")
                return False
                
            # Duyuru şablonu seç
            template = self._choose_announcement_template(category, announcement_type)
            if not template:
                logger.warning(f"Uygun duyuru şablonu bulunamadı: {category}/{announcement_type}")
                return False
                
            # Rate limiting kontrolü
            if hasattr(self.rate_limiter, 'get_wait_time'):
                wait_time = self.rate_limiter.get_wait_time()
                if wait_time > 0:
                    logger.debug(f"Rate limit nedeniyle {wait_time:.1f} saniye bekleniyor")
                    await asyncio.sleep(wait_time)
                    
            # Duyuruyu gönder
            message = await self.client.send_message(group_id, template)
            
            # Rate limiter'ı güncelle
            if hasattr(self.rate_limiter, 'mark_used'):
                self.rate_limiter.mark_used()
                
            # Son mesaj zamanını güncelle
            self.last_group_message[group_id] = datetime.now()
            
            # İstatistikleri güncelle
            self.announcement_count += 1
            self.stats['total_sent'] += 1
            self.stats['last_sent'] = datetime.now().isoformat()
            
            logger.info(f"Duyuru gönderildi: {group_id} - {category}")
            return True
            
        except errors.ChatWriteForbiddenError:
            # Grupta yazma izni yok
            logger.warning(f"Grupta yazma izni yok: {group_id}")
            return False
            
        except errors.ChatAdminRequiredError:
            # Grup yönetici izni gerekiyor
            logger.warning(f"Grupta yönetici izni gerekiyor: {group_id}")
            return False
            
        except Exception as e:
            logger.exception(f"Duyuru gönderme hatası: {str(e)}")
            return False
    
    def _choose_announcement_template(self, category: str, announcement_type: str) -> str:
        """
        Uygun duyuru şablonu seçer.
        
        Args:
            category: Grup kategorisi
            announcement_type: Duyuru tipi
            
        Returns:
            str: Seçilen duyuru şablonu
        """
        # Kategori için şablonları al
        category_templates = self.announcement_templates.get(category)
        if not category_templates:
            # Varsayılan şablonları kullan
            category_templates = self.announcement_templates.get("safe_groups", {})
            
        # Duyuru tipi için şablonları al
        templates = category_templates.get(announcement_type, [])
        if not templates:
            # Varsayılan tipi kullan
            templates = category_templates.get("promotion", [])
            
        if not templates:
            return None
            
        # Rasgele bir şablon seç
        template = random.choice(templates)
        
        # Şablonu formatla - grup bağlantılarını ekle
        group_links = self._parse_group_links()
        if group_links and "{}" in template:
            # Rasgele bir grup bağlantısı seç
            group_link = random.choice(group_links)
            template = template.format(group_link)
            
        return template
    
    def _parse_group_links(self) -> List[str]:
        """
        Çevre değişkenlerinden grup bağlantılarını ayrıştırır.
        
        Returns:
            List[str]: Grup bağlantıları listesi
        """
        if not self.own_groups:
            return []
            
        # Bağlantıları temizle
        clean_links = []
        for link in self.own_groups:
            # t.me/ önekini kaldır
            if "t.me/" in link:
                link = link.split("t.me/")[1]
            clean_links.append(link)
            
        return clean_links
    
    def set_services(self, services):
        """
        Diğer servislere referansları ayarlar.
        
        Args:
            services: Servis adı -> Servis nesnesi eşleşmesi
        """
        self.services = services
        logger.debug(f"{self.service_name} diğer servislere bağlandı")
    
    async def send_custom_announcement(self, message: str, category: str = None, group_ids: List[int] = None) -> int:
        """
        Özel bir duyuru gönderir.
        
        Args:
            message: Duyuru mesajı
            category: Grup kategorisi (belirtilmezse tüm kategoriler)
            group_ids: Belirli grup ID'leri (belirtilmezse kategori kullanılır)
            
        Returns:
            int: Gönderilen duyuru sayısı
        """
        try:
            if not self.client:
                logger.error("Telegram istemcisi bulunamadı!")
                return 0
                
            target_groups = []
            
            if group_ids:
                # Belirli grupları kullan
                target_groups = group_ids
            elif category:
                # Belirli kategorideki grupları kullan
                target_groups = list(self.group_categories.get(category, set()))
            else:
                # Tüm grupları kullan
                for groups in self.group_categories.values():
                    target_groups.extend(groups)
                    
            if not target_groups:
                logger.warning("Duyuru gönderilecek grup bulunamadı!")
                return 0
                
            # Gruplara duyuru gönder
            success_count = 0
            for group_id in target_groups:
                try:
                    # Rate limiting kontrolü
                    if hasattr(self.rate_limiter, 'get_wait_time'):
                        wait_time = self.rate_limiter.get_wait_time()
                        if wait_time > 0:
                            logger.debug(f"Rate limit nedeniyle {wait_time:.1f} saniye bekleniyor")
                            await asyncio.sleep(wait_time)
                            
                    # Duyuruyu gönder
                    await self.client.send_message(group_id, message)
                    
                    # Rate limiter'ı güncelle
                    if hasattr(self.rate_limiter, 'mark_used'):
                        self.rate_limiter.mark_used()
                        
                    # Son mesaj zamanını güncelle
                    self.last_group_message[group_id] = datetime.now()
                    
                    # İstatistikleri güncelle
                    self.announcement_count += 1
                    self.stats['total_sent'] += 1
                    self.stats['last_sent'] = datetime.now().isoformat()
                    
                    success_count += 1
                    
                except Exception as e:
                    logger.exception(f"Özel duyuru gönderme hatası: {str(e)}")
                    continue
                    
            return success_count
            
        except Exception as e:
            logger.exception(f"Özel duyuru işleme hatası: {str(e)}")
            return 0
    
    async def get_status(self) -> Dict[str, Any]:
        """
        Servis durum bilgilerini döndürür.
        
        Returns:
            Dict[str, Any]: Durum bilgileri
        """
        return {
            'service': 'announcement',
            'running': self.running,
            'announcement_count': self.announcement_count,
            'last_announcement': self.last_announcement_time,
            'own_groups': len(self.group_categories.get('own_groups', [])),
            'safe_groups': len(self.group_categories.get('safe_groups', [])),
            'risky_groups': len(self.group_categories.get('risky_groups', [])),
            'high_traffic_groups': len(self.group_categories.get('high_traffic_groups', []))
        }
    
    async def get_statistics(self) -> Dict[str, Any]:
        """
        Servis istatistiklerini döndürür.
        
        Returns:
            Dict[str, Any]: İstatistik bilgileri
        """
        return {
            'total_sent': self.stats['total_sent'],
            'last_sent': self.stats['last_sent'],
            'group_categories': {
                category: len(groups) for category, groups in self.group_categories.items()
            }
        } 