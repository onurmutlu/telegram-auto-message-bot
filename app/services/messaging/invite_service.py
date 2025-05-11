"""
Telegram Bot Davet Servisi

Grup davetlerini yönetme ve kullanıcı katılım servisi.
"""

import asyncio
import json
import logging
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any, Set, Optional, Tuple, Union

from app.services.base_service import BaseService
from app.utils.rate_limiter import RateLimiter
from app.core.logger import get_logger
from telethon import errors

logger = get_logger(__name__)

class InviteService(BaseService):
    """
    Grup davetlerini yönetme ve kullanıcı katılım servisi.
    
    Bu servis:
    1. Yeni kullanıcıları gruplara davet eder
    2. Davet bağlantılarını oluşturur ve takip eder
    3. Davet istatistiklerini tutar
    4. Özel davet kampanyaları düzenler
    
    Attributes:
        invites: Aktif davetler
        invite_stats: Davet istatistikleri
        invite_links: Davet bağlantıları
    """
    
    service_name = "invite_service"
    default_interval = 1800  # 30 dakika
    
    def __init__(self, **kwargs):
        """
        InviteService sınıfının başlatıcısı.
        
        Args:
            **kwargs: Temel servis parametreleri
        """
        super().__init__(**kwargs)
        
        # Durum takibi
        self.running = False
        
        # Davetler ve istatistikler
        self.invites = {}  # user_id -> [group_ids]
        self.invite_stats = {
            'total_invites': 0,
            'successful_invites': 0,
            'failed_invites': 0
        }
        
        # Davet bağlantıları
        self.invite_links = {}  # group_id -> invite_link
        
        # Davet limitleri
        self.daily_invite_limit = self.config.get('daily_invite_limit', 50)
        self.daily_invite_count = 0
        self.last_daily_reset = datetime.now()
        
        # Rate limiter
        self.rate_limiter = RateLimiter(max_per_minute=10)  # Dakikada 10 davet
        
        # Kampanyalar
        self.active_campaigns = []
        self._load_campaigns()
    
    def _load_campaigns(self):
        """Davet kampanyalarını yükler."""
        try:
            # Kampanya dosyasını oku
            with open('data/invite_campaigns.json', 'r', encoding='utf-8') as f:
                campaigns = json.load(f)
                
            if isinstance(campaigns, list):
                self.active_campaigns = campaigns
                logger.info(f"Davet kampanyaları yüklendi: {len(campaigns)} kampanya")
            else:
                logger.warning("Geçersiz kampanya formatı! Liste formatı bekleniyor")
                self._set_default_campaigns()
                
        except FileNotFoundError:
            logger.warning("Kampanya dosyası bulunamadı, varsayılan kampanyalar kullanılacak")
            self._set_default_campaigns()
            
        except Exception as e:
            logger.error(f"Kampanyalar yüklenirken hata: {str(e)}")
            self._set_default_campaigns()
    
    def _set_default_campaigns(self):
        """Varsayılan kampanyaları ayarlar."""
        self.active_campaigns = [
            {
                "id": "default_campaign",
                "name": "Varsayılan Kampanya",
                "description": "Yeni kullanıcıları ana gruba davet et",
                "target_group_id": -1001234567890,  # Örnek grup ID
                "status": "active",
                "start_date": datetime.now().isoformat(),
                "end_date": (datetime.now() + timedelta(days=30)).isoformat(),
                "target_count": 100,
                "current_count": 0
            }
        ]
    
    async def _start(self) -> bool:
        """
        Servisi başlatır.
        
        Returns:
            bool: Başarılı ise True
        """
        try:
            logger.info("Davet servisi başlatılıyor")
            
            # Davet verilerini yükle
            await self._load_invite_data()
            
            # Davet bağlantılarını güncelle
            await self._update_invite_links()
            
            self.running = True
            logger.info("Davet servisi başlatıldı")
            return True
            
        except Exception as e:
            logger.exception(f"Davet servisi başlatma hatası: {str(e)}")
            return False
    
    async def _stop(self) -> bool:
        """
        Servisi durdurur.
        
        Returns:
            bool: Başarılı ise True
        """
        try:
            logger.info("Davet servisi durduruluyor")
            
            # Davet verilerini kaydet
            await self._save_invite_data()
            
            self.running = False
            logger.info("Davet servisi durduruldu")
            return True
            
        except Exception as e:
            logger.exception(f"Davet servisi durdurma hatası: {str(e)}")
            return False
    
    async def _update(self) -> None:
        """Periyodik davet işlemleri."""
        try:
            # Günlük limiti sıfırla
            self._reset_daily_limit_if_needed()
            
            # Davet kampanyalarını güncelle
            await self._update_campaigns()
            
            # Otomatik davetler gönder
            if self.is_under_daily_limit():
                await self._send_automated_invites()
                
        except Exception as e:
            logger.exception(f"Davet servisi güncelleme hatası: {str(e)}")
    
    async def _load_invite_data(self):
        """Davet verilerini yükler."""
        try:
            # Veritabanından davet verilerini yükle
            if hasattr(self.db, 'get_invites'):
                invite_data = await self._run_async_db_method(self.db.get_invites)
                
                if invite_data:
                    self.invites = invite_data.get('invites', {})
                    self.invite_stats = invite_data.get('stats', self.invite_stats)
                    self.invite_links = invite_data.get('links', {})
                    
                    logger.info(f"Davet verileri yüklendi: {len(self.invites)} davet, {len(self.invite_links)} bağlantı")
                    
        except Exception as e:
            logger.error(f"Davet verileri yüklenirken hata: {str(e)}")
    
    async def _save_invite_data(self):
        """Davet verilerini kaydeder."""
        try:
            # Veritabanına davet verilerini kaydet
            if hasattr(self.db, 'save_invites'):
                invite_data = {
                    'invites': self.invites,
                    'stats': self.invite_stats,
                    'links': self.invite_links
                }
                
                await self._run_async_db_method(self.db.save_invites, invite_data)
                logger.info("Davet verileri kaydedildi")
                
        except Exception as e:
            logger.error(f"Davet verileri kaydedilirken hata: {str(e)}")
    
    async def _update_invite_links(self):
        """Davet bağlantılarını günceller."""
        try:
            if not self.client:
                logger.error("Telegram istemcisi bulunamadı!")
                return
                
            # Grupları al
            groups = await self._get_manageable_groups()
            
            for group in groups:
                group_id = group.get('group_id') or group.get('id')
                
                # Grup yöneticisi veya sahibi ise bağlantı oluştur
                if group.get('is_admin', False) or group.get('is_owner', False):
                    try:
                        # Davet bağlantısı var mı kontrol et
                        if str(group_id) not in self.invite_links:
                            # Yeni davet bağlantısı oluştur
                            invite_link = await self.client.export_chat_invite_link(group_id)
                            
                            # Bağlantıyı kaydet
                            self.invite_links[str(group_id)] = invite_link
                            logger.info(f"Yeni davet bağlantısı oluşturuldu: {group_id}")
                            
                    except errors.ChatAdminRequiredError:
                        logger.warning(f"Davet oluşturmak için yönetici izni gerekiyor: {group_id}")
                        
                    except Exception as e:
                        logger.error(f"Davet bağlantısı oluşturma hatası: {str(e)}")
                        
            logger.info(f"Davet bağlantıları güncellendi: {len(self.invite_links)} bağlantı")
            
        except Exception as e:
            logger.exception(f"Davet bağlantıları güncellenirken hata: {str(e)}")
    
    async def _get_manageable_groups(self):
        """
        Yönetilebilir grupları getirir.
        
        Returns:
            List[Dict]: Grup listesi
        """
        if 'group_service' in self.services:
            return await self.services['group_service'].get_manageable_groups()
        return []
    
    def _reset_daily_limit_if_needed(self):
        """Günlük davet limitini gerekirse sıfırlar."""
        now = datetime.now()
        
        # Son sıfırlamadan bu yana 24 saat geçtiyse
        if (now - self.last_daily_reset).total_seconds() > 24 * 60 * 60:
            self.daily_invite_count = 0
            self.last_daily_reset = now
            logger.info("Günlük davet limiti sıfırlandı")
    
    def is_under_daily_limit(self) -> bool:
        """
        Günlük davet limitinin altında olup olmadığını kontrol eder.
        
        Returns:
            bool: Limit altındaysa True
        """
        return self.daily_invite_count < self.daily_invite_limit
    
    async def _update_campaigns(self):
        """Davet kampanyalarını günceller."""
        now = datetime.now()
        
        for campaign in self.active_campaigns:
            # Kampanya aktif mi kontrol et
            if campaign.get('status') != 'active':
                continue
                
            # Tarih aralığı kontrolü
            try:
                start_date = datetime.fromisoformat(campaign.get('start_date', '2000-01-01'))
                end_date = datetime.fromisoformat(campaign.get('end_date', '2099-12-31'))
                
                # Kampanya tarihi geçtiyse
                if now > end_date:
                    campaign['status'] = 'completed'
                    logger.info(f"Kampanya tamamlandı: {campaign.get('id')}")
                    continue
                    
                # Kampanya henüz başlamadıysa
                if now < start_date:
                    continue
                    
                # Hedef sayıya ulaşıldıysa
                if campaign.get('current_count', 0) >= campaign.get('target_count', 100):
                    campaign['status'] = 'target_reached'
                    logger.info(f"Kampanya hedefi tamamlandı: {campaign.get('id')}")
                    continue
                    
            except (ValueError, TypeError):
                logger.warning(f"Kampanya tarih formatı geçersiz: {campaign.get('id')}")
                continue
    
    async def _send_automated_invites(self):
        """Otomatik davetler gönderir."""
        try:
            # Aktif kampanyaları kontrol et
            active_campaigns = [c for c in self.active_campaigns if c.get('status') == 'active']
            
            if not active_campaigns:
                return
                
            # Rasgele bir kampanya seç
            campaign = random.choice(active_campaigns)
            
            # Kampanyanın hedef grubunu al
            target_group_id = campaign.get('target_group_id')
            if not target_group_id:
                return
                
            # Kullanıcı servisi mevcutsa
            if 'user_service' in self.services:
                # Aktif kullanıcıları al
                active_users = await self.services['user_service'].get_all_active_users()
                
                if not active_users:
                    return
                    
                # Günlük limitin altındaysa ve kullanıcı varsa
                if self.is_under_daily_limit() and active_users:
                    # Kaç kullanıcıya davet gönderilecek
                    remaining = self.daily_invite_limit - self.daily_invite_count
                    batch_size = min(5, remaining)  # En fazla 5 kullanıcı
                    
                    # Rasgele kullanıcıları seç
                    random.shuffle(active_users)
                    target_users = active_users[:batch_size]
                    
                    # Seçilen kullanıcılara davet gönder
                    for user in target_users:
                        user_id = user.get('user_id') or user.get('id')
                        
                        # Kullanıcı zaten davet edilmiş mi
                        if self._is_already_invited(user_id, target_group_id):
                            continue
                            
                        # Kullanıcıyı davet et
                        await self.invite_user(user_id, target_group_id)
                        
                        # Kampanya sayacını güncelle
                        campaign['current_count'] = campaign.get('current_count', 0) + 1
                        
        except Exception as e:
            logger.exception(f"Otomatik davet hatası: {str(e)}")
    
    def _is_already_invited(self, user_id: int, group_id: int) -> bool:
        """
        Kullanıcının zaten davet edilmiş olup olmadığını kontrol eder.
        
        Args:
            user_id: Kullanıcı ID
            group_id: Grup ID
            
        Returns:
            bool: Kullanıcı zaten davet edilmişse True
        """
        user_invites = self.invites.get(str(user_id), [])
        return str(group_id) in user_invites
    
    async def invite_user(self, user_id: Union[int, str], group_id: int) -> bool:
        """
        Kullanıcıyı gruba davet eder.
        
        Args:
            user_id: Kullanıcı ID veya kullanıcı adı
            group_id: Grup ID
            
        Returns:
            bool: Başarılı ise True
        """
        try:
            if not self.client:
                logger.error("Telegram istemcisi bulunamadı!")
                return False
                
            # Günlük limiti kontrol et
            if not self.is_under_daily_limit():
                logger.warning("Günlük davet limiti aşıldı!")
                return False
                
            # Rate limiting kontrolü
            if hasattr(self.rate_limiter, 'can_execute'):
                if not self.rate_limiter.can_execute():
                    logger.warning("Rate limit sebebiyle davet gönderilemiyor")
                    return False
                    
            # Grup davet bağlantısını al
            invite_link = self.invite_links.get(str(group_id))
            
            if not invite_link:
                # Yeni bağlantı oluştur
                try:
                    invite_link = await self.client.export_chat_invite_link(group_id)
                    self.invite_links[str(group_id)] = invite_link
                except Exception as e:
                    logger.error(f"Davet bağlantısı oluşturma hatası: {str(e)}")
                    return False
                    
            # DM servisi mevcutsa
            if 'dm_service' in self.services:
                # Davet mesajı gönder
                invite_message = f"Merhaba! Sizi grubumuzda görmek isteriz: {invite_link}"
                
                success = await self.services['dm_service'].send_message(
                    user_id,
                    invite_message,
                    message_type="invite"
                )
                
                if success:
                    # Davet kaydını oluştur
                    if str(user_id) not in self.invites:
                        self.invites[str(user_id)] = []
                        
                    if str(group_id) not in self.invites[str(user_id)]:
                        self.invites[str(user_id)].append(str(group_id))
                        
                    # Sayaçları güncelle
                    self.daily_invite_count += 1
                    self.invite_stats['total_invites'] += 1
                    self.invite_stats['successful_invites'] += 1
                    
                    # Rate limiter'ı güncelle
                    if hasattr(self.rate_limiter, 'mark_used'):
                        self.rate_limiter.mark_used()
                        
                    logger.info(f"Kullanıcı davet edildi: {user_id} -> {group_id}")
                    return True
                else:
                    self.invite_stats['failed_invites'] += 1
                    logger.warning(f"Kullanıcıya davet mesajı gönderilemedi: {user_id}")
                    return False
                    
            else:
                # DM servisi yoksa kendi gönder
                try:
                    invite_message = f"Merhaba! Sizi grubumuzda görmek isteriz: {invite_link}"
                    await self.client.send_message(user_id, invite_message)
                    
                    # Davet kaydını oluştur
                    if str(user_id) not in self.invites:
                        self.invites[str(user_id)] = []
                        
                    if str(group_id) not in self.invites[str(user_id)]:
                        self.invites[str(user_id)].append(str(group_id))
                        
                    # Sayaçları güncelle
                    self.daily_invite_count += 1
                    self.invite_stats['total_invites'] += 1
                    self.invite_stats['successful_invites'] += 1
                    
                    # Rate limiter'ı güncelle
                    if hasattr(self.rate_limiter, 'mark_used'):
                        self.rate_limiter.mark_used()
                        
                    logger.info(f"Kullanıcı davet edildi: {user_id} -> {group_id}")
                    return True
                    
                except Exception as e:
                    self.invite_stats['failed_invites'] += 1
                    logger.error(f"Kullanıcıya davet mesajı gönderme hatası: {str(e)}")
                    return False
                    
        except Exception as e:
            self.invite_stats['failed_invites'] += 1
            logger.exception(f"Davet gönderme hatası: {str(e)}")
            return False
    
    async def create_invite_link(self, group_id: int, expire_date: Optional[datetime] = None) -> Optional[str]:
        """
        Grup için davet bağlantısı oluşturur.
        
        Args:
            group_id: Grup ID
            expire_date: Geçerlilik süresi
            
        Returns:
            Optional[str]: Davet bağlantısı
        """
        try:
            if not self.client:
                logger.error("Telegram istemcisi bulunamadı!")
                return None
                
            # Zaten bir bağlantı var mı kontrol et
            if str(group_id) in self.invite_links:
                link = self.invite_links[str(group_id)]
                logger.debug(f"Mevcut davet bağlantısı kullanılıyor: {group_id}")
                return link
                
            # Yeni bağlantı oluştur
            if expire_date:
                # Süreli bağlantı
                link = await self.client.export_chat_invite_link(
                    group_id,
                    expire_date=expire_date
                )
            else:
                # Süresiz bağlantı
                link = await self.client.export_chat_invite_link(group_id)
                
            # Bağlantıyı kaydet
            self.invite_links[str(group_id)] = link
            logger.info(f"Yeni davet bağlantısı oluşturuldu: {group_id}")
            
            return link
            
        except errors.ChatAdminRequiredError:
            logger.warning(f"Davet oluşturmak için yönetici izni gerekiyor: {group_id}")
            return None
            
        except Exception as e:
            logger.exception(f"Davet bağlantısı oluşturma hatası: {str(e)}")
            return None
    
    async def get_user_invites(self, user_id: int) -> List[str]:
        """
        Kullanıcının davet edildiği grupları getirir.
        
        Args:
            user_id: Kullanıcı ID
            
        Returns:
            List[str]: Davet edilen grup ID'leri
        """
        return self.invites.get(str(user_id), [])
    
    async def create_campaign(self, campaign_data: Dict[str, Any]) -> Optional[str]:
        """
        Yeni bir davet kampanyası oluşturur.
        
        Args:
            campaign_data: Kampanya verisi
            
        Returns:
            Optional[str]: Kampanya ID
        """
        try:
            # Gerekli alanları kontrol et
            required_fields = ['name', 'target_group_id']
            for field in required_fields:
                if field not in campaign_data:
                    logger.error(f"Kampanya oluşturulamadı: {field} alanı eksik")
                    return None
                    
            # Kampanya ID'si oluştur
            campaign_id = f"campaign_{int(datetime.now().timestamp())}"
            
            # Kampanya oluştur
            campaign = {
                "id": campaign_id,
                "name": campaign_data['name'],
                "description": campaign_data.get('description', ''),
                "target_group_id": campaign_data['target_group_id'],
                "status": "active",
                "start_date": campaign_data.get('start_date', datetime.now().isoformat()),
                "end_date": campaign_data.get('end_date', (datetime.now() + timedelta(days=30)).isoformat()),
                "target_count": campaign_data.get('target_count', 100),
                "current_count": 0
            }
            
            # Kampanyayı ekle
            self.active_campaigns.append(campaign)
            logger.info(f"Yeni kampanya oluşturuldu: {campaign_id}")
            
            return campaign_id
            
        except Exception as e:
            logger.exception(f"Kampanya oluşturma hatası: {str(e)}")
            return None
    
    async def get_campaigns(self) -> List[Dict[str, Any]]:
        """
        Tüm kampanyaları getirir.
        
        Returns:
            List[Dict[str, Any]]: Kampanya listesi
        """
        return self.active_campaigns
    
    async def update_campaign(self, campaign_id: str, update_data: Dict[str, Any]) -> bool:
        """
        Kampanyayı günceller.
        
        Args:
            campaign_id: Kampanya ID
            update_data: Güncelleme verisi
            
        Returns:
            bool: Başarılı ise True
        """
        try:
            # Kampanyayı bul
            for campaign in self.active_campaigns:
                if campaign.get('id') == campaign_id:
                    # Kampanyayı güncelle
                    for key, value in update_data.items():
                        campaign[key] = value
                        
                    logger.info(f"Kampanya güncellendi: {campaign_id}")
                    return True
                    
            logger.warning(f"Güncellenecek kampanya bulunamadı: {campaign_id}")
            return False
            
        except Exception as e:
            logger.exception(f"Kampanya güncelleme hatası: {str(e)}")
            return False
    
    async def get_status(self) -> Dict[str, Any]:
        """
        Servis durum bilgilerini döndürür.
        
        Returns:
            Dict[str, Any]: Durum bilgileri
        """
        active_campaign_count = len([c for c in self.active_campaigns if c.get('status') == 'active'])
        
        return {
            'service': 'invite',
            'running': self.running,
            'invite_links_count': len(self.invite_links),
            'daily_invite_count': self.daily_invite_count,
            'daily_invite_limit': self.daily_invite_limit,
            'last_daily_reset': self.last_daily_reset.isoformat() if self.last_daily_reset else None,
            'active_campaigns': active_campaign_count,
            'total_campaigns': len(self.active_campaigns)
        }
    
    async def get_statistics(self) -> Dict[str, Any]:
        """
        Servis istatistiklerini döndürür.
        
        Returns:
            Dict[str, Any]: İstatistik bilgileri
        """
        return {
            'total_invites': self.invite_stats['total_invites'],
            'successful_invites': self.invite_stats['successful_invites'],
            'failed_invites': self.invite_stats['failed_invites'],
            'success_rate': (self.invite_stats['successful_invites'] / self.invite_stats['total_invites']) * 100 if self.invite_stats['total_invites'] > 0 else 0
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
                # Senkron metodu threadpool'da çalıştır
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None,
                    lambda: method(*args, **kwargs)
                )
        except Exception as e:
            logger.error(f"Veritabanı metodu çalıştırma hatası: {str(e)}")
            return None 