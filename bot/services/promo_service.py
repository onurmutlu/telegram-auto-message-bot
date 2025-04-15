"""
# ============================================================================ #
# Dosya: promo_service.py
# Yol: /Users/siyahkare/code/telegram-bot/bot/services/promo_service.py
# İşlev: Tanıtım ve duyuru mesajları gönderimini yöneten servis.
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

import asyncio
import logging
import random
import json
import traceback
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Set, Optional

from bot.services.base_service import BaseService
from bot.utils.adaptive_rate_limiter import AdaptiveRateLimiter

logger = logging.getLogger(__name__)

class PromoService(BaseService):
    """
    Kullanıcılara tanıtım ve duyuru mesajları gönderen servis.
    
    Bu servis, belirlenen sıklıkta ve stratejilerle kullanıcılara
    tanıtım mesajları gönderir, kullanıcı segmentasyonu yapar ve
    mesajların etkisini analiz eder.
    """
    
    def __init__(self, client, config, db, stop_event=None):
        """
        PromoService sınıfının başlatıcısı.
        
        Args:
            client: Telegram istemcisi
            config: Bot yapılandırma nesnesi
            db: Veritabanı nesnesi
            stop_event: Durdurma sinyali
        """
        super().__init__("promo", client, config, db, stop_event)
        
        # Durum takibi
        self.running = False
        self.promo_sent = 0
        self.last_batch_time = None
        self.active_campaign = None
        
        # Kullanıcı segmentleri
        self.user_segments = {
            'new': set(),        # Yeni kullanıcılar
            'active': set(),     # Aktif kullanıcılar
            'inactive': set(),   # İnaktif kullanıcılar
            'vip': set()         # VIP kullanıcılar
        }
        
        # Kampanya yapılandırması
        self.campaigns = {}
        
        # Rate limiter ayarlaması
        self.rate_limiter = AdaptiveRateLimiter(
            initial_rate=3,  # Başlangıçta dakikada 3 mesaj
            period=60,
            error_backoff=1.5,
            max_jitter=2.0
        )
        
        # Servisler
        self.services = {}
        
        # Ayarları yükle
        self._load_settings()
        self._load_templates()
        
        # Son gönderim zamanlarını takip eden sözlük
        self.last_sent_times = {}
        # Minimum gönderim aralığı (saniye)
        self.min_send_interval = 360  # 6 dakika
    
    def _load_settings(self):
        """Tanıtım servisi ayarlarını yükler."""
        # Yapılandırma dosyasından veya çevre değişkenlerinden
        self.batch_size = self.config.get_setting('promo_batch_size', 20)
        self.cooldown_hours = self.config.get_setting('promo_cooldown_hours', 48)
        self.vip_cooldown_hours = self.config.get_setting('promo_vip_cooldown_hours', 72)
        self.campaign_interval_minutes = self.config.get_setting('promo_campaign_interval_minutes', 120)
        self.auto_campaign = self.config.get_setting('promo_auto_campaign', False)
        
        # Debug modu
        self.debug = self.config.get_setting('debug', False)
        
        logger.info(f"Tanıtım servisi ayarları yüklendi: batch={self.batch_size}, interval={self.campaign_interval_minutes}dk")
    
    def _load_templates(self):
        """Tanıtım mesaj şablonlarını yükler."""
        try:
            # Şablon dosyası
            with open('data/promos.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.promo_templates = data.get('templates', {})
            
            # Segment bazlı şablon sayıları
            segments = ['new', 'active', 'inactive', 'vip', 'general']
            for segment in segments:
                count = len(self.promo_templates.get(segment, []))
                logger.debug(f"{segment} segmenti için {count} şablon yüklendi")
                
            # Genel şablonları kontrol et
            if not self.promo_templates.get('general'):
                logger.warning("Genel tanıtım şablonları eksik! data/promos.json dosyasını kontrol edin.")
                self.promo_templates['general'] = ["Merhaba! Grup linklerimiz: t.me/{}"]
                
        except Exception as e:
            logger.error(f"Tanıtım şablonları yüklenirken hata: {str(e)}")
            # Basit varsayılan şablon ekleyin
            self.promo_templates = {
                'general': ["Merhaba! Grup linklerimiz: t.me/{}"]
            }
    
    def _load_group_links(self):
        """Yapılandırmadan grup linklerini yükler."""
        links = []
        
        # Çevre değişkenlerinden
        env_links = os.getenv("GROUP_LINKS", "")
        if env_links:
            links.extend([link.strip() for link in env_links.split(",") if link.strip()])
            
        # Config nesnesinden
        if hasattr(self.config, 'promotion') and hasattr(self.config.promotion, 'group_links'):
            config_links = self.config.promotion.group_links
            if isinstance(config_links, list):
                links.extend(config_links)
                
        # Tüm linkleri normalize et
        return [self._normalize_group_link(link) for link in links]
    
    async def initialize(self) -> bool:
        """
        Servisi başlatır ve verileri yükler.
        
        Returns:
            bool: Başarılı ise True
        """
        # Temel servisi başlat
        await super().initialize()
        
        # Kampanyaları yükle (veritabanından)
        await self._load_campaigns()
        
        # Kullanıcı segmentlerini hazırla
        await self._prepare_user_segments()
        
        logger.info(f"Tanıtım servisi başlatıldı: {sum(len(segment) for segment in self.user_segments.values())} kullanıcı")
        return True
    
    async def _load_campaigns(self):
        """Veritabanından kampanya bilgilerini yükler."""
        try:
            # Kampanya verilerini veritabanından çek
            if hasattr(self.db, 'get_campaigns'):
                campaigns = await self._run_async_db_method(self.db.get_campaigns)
                if campaigns:
                    self.campaigns = campaigns
                    logger.info(f"{len(campaigns)} kampanya yüklendi")
            
            # Aktif kampanya var mı kontrol et
            for campaign_id, campaign in self.campaigns.items():
                if campaign.get('is_active') and not campaign.get('completed'):
                    self.active_campaign = campaign_id
                    logger.info(f"Aktif kampanya bulundu: {campaign_id}")
                    break
        
        except Exception as e:
            logger.error(f"Kampanyalar yüklenirken hata: {str(e)}")
    
    async def _prepare_user_segments(self):
        """Kullanıcı segmentlerini hazırlar"""
        try:
            segments = {}
            
            # Kullanıcı segmentlerini veritabanından çek
            if hasattr(self.db, 'get_user_segments'):
                # Bu bir coroutine olduğu için await kullan
                segments = await self._run_async_db_method(self.db.get_user_segments)
                
            # Segmentlerde kullanıcı yoksa veya database fonksiyonu yoksa
            if not segments:
                # Varsayılan segmentler oluştur
                segments = {
                    'active': [],
                    'inactive': [],
                    'new': []
                }
                
                # Tüm kullanıcıları getir
                all_users = []
                if hasattr(self.db, 'get_all_users'):
                    # Bu bir coroutine olduğu için await kullan
                    all_users = await self._run_async_db_method(self.db.get_all_users)
                    
                # Kullanıcıları segmentlere ayır
                for user in all_users:
                    # İşleme mantığı...
                    pass
                    
            return segments
            
        except Exception as e:
            logger.error(f"Kullanıcı segmentleri hazırlanırken hata: {str(e)}")
            logger.debug(traceback.format_exc())
            return {'active': [], 'inactive': [], 'new': []}
    
    async def start(self) -> bool:
        """
        Tanıtım servisini başlatır.
        
        Returns:
            bool: Başarılı ise True
        """
        if self.running:
            return True
            
        self.running = True
        logger.info("Tanıtım servisi başlatılıyor...")
        
        # Otomatik kampanya başlatma görevi
        if self.auto_campaign:
            asyncio.create_task(self._campaign_loop())
        
        return True
    
    async def stop(self) -> None:
        """
        Tanıtım servisini durdurur.
        
        Returns:
            None
        """
        self.running = False
        logger.info("Tanıtım servisi durduruluyor...")
        
        # Aktif kampanyayı güvenli şekilde durdur
        if self.active_campaign:
            await self._save_campaign_state(self.active_campaign)
            
        # Temel servisin stop metodunu çağır
        await super().stop()
    
    async def _campaign_loop(self):
        """Periyodik tanıtım kampanyalarını yönetir."""
        logger.info("Tanıtım kampanya döngüsü başlatıldı")
        
        while self.running and not self.stop_event.is_set():
            try:
                # Aktif kampanya kontrolü
                if not self.active_campaign:
                    # Yeni bir kampanya seç
                    await self._select_next_campaign()
                
                if self.active_campaign:
                    # Kampanyayı çalıştır
                    await self._run_campaign_batch(self.active_campaign)
                    
                    # Kampanya tamamlandı mı?
                    if await self._is_campaign_completed(self.active_campaign):
                        logger.info(f"Kampanya tamamlandı: {self.active_campaign}")
                        await self._mark_campaign_completed(self.active_campaign)
                        self.active_campaign = None
                
                # Bir sonraki kampanya veya iteme kadar bekle
                interval = self.campaign_interval_minutes * 60
                logger.debug(f"Bir sonraki tanıtım kampanya değerlendirmesine kadar {interval} saniye bekleniyor")
                await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                logger.info("Tanıtım kampanya döngüsü iptal edildi")
                break
            except Exception as e:
                logger.error(f"Kampanya döngüsünde hata: {str(e)}")
                await asyncio.sleep(300)  # Hata durumunda 5 dakika bekle
    
    async def _select_next_campaign(self):
        """Bir sonraki aktif kampanyayı belirler."""
        # Tamamlanmamış kampanyaları kontrol et
        for campaign_id, campaign in self.campaigns.items():
            if not campaign.get('completed') and not campaign.get('paused'):
                self.active_campaign = campaign_id
                logger.info(f"Yeni aktif kampanya seçildi: {campaign_id}")
                return
        
        # Kampanya yoksa, genel tanıtım öğelerini gönder
        # Bu varsayılan bir kampanya oluşturabilir
        self.active_campaign = 'general_promo'
        self.campaigns[self.active_campaign] = {
            'name': 'Genel Tanıtım',
            'description': 'Varsayılan genel tanıtım kampanyası',
            'segment': 'general',
            'start_date': datetime.now().isoformat(),
            'completed': False,
            'paused': False,
            'batch_size': self.batch_size,
            'interval_minutes': self.campaign_interval_minutes
        }
        logger.info("Varsayılan genel tanıtım kampanyası oluşturuldu")
    
    async def _run_campaign_batch(self, campaign_id):
        """
        Kampanyanın bir batch'ini çalıştırır.
        
        Args:
            campaign_id: Kampanya ID'si
        """
        if campaign_id not in self.campaigns:
            logger.error(f"Kampanya bulunamadı: {campaign_id}")
            return 0
            
        campaign = self.campaigns[campaign_id]
        segment = campaign.get('segment', 'general')
        batch_size = campaign.get('batch_size', self.batch_size)
        
        # Bu kampanya için en son gönderim zamanını kontrol et
        last_send = campaign.get('last_batch_time')
        if last_send:
            last_time = datetime.fromisoformat(last_send)
            cooldown = campaign.get('cooldown_hours', self.cooldown_hours)
            if datetime.now() - last_time < timedelta(hours=cooldown):
                logger.info(f"Kampanya {campaign_id} cooldown süresi dolmadı: {cooldown} saat")
                return 0
        
        # Segment için kullanıcıları al
        user_ids = []
        if segment in self.user_segments and self.user_segments[segment]:
            # Segmentten kullanıcı seç
            users_in_segment = list(self.user_segments[segment])
            user_ids = random.sample(
                users_in_segment, 
                min(batch_size, len(users_in_segment))
            )
        else:
            # Segmentte kullanıcı yoksa, veritabanından kullanıcı al
            try:
                users = await self._run_async_db_method(
                    self.db.get_users_for_promo, 
                    batch_size, 
                    segment
                )
                if users:
                    user_ids = [user['user_id'] for user in users]
            except Exception as e:
                logger.error(f"Tanıtım için kullanıcılar alınırken hata: {str(e)}")
        
        if not user_ids:
            logger.warning(f"Kampanya {campaign_id} için gönderilecek kullanıcı bulunamadı")
            return 0
        
        # Şablon seç
        template = self._choose_promo_template(segment)
        if not template:
            logger.error(f"Kampanya {campaign_id} için şablon bulunamadı")
            return 0
            
        # Mesajları gönder
        sent_count = await self._send_promo_batch(user_ids, template, campaign)
        
        # Kampanya durumunu güncelle
        self.campaigns[campaign_id]['last_batch_time'] = datetime.now().isoformat()
        self.campaigns[campaign_id]['sent_count'] = campaign.get('sent_count', 0) + sent_count
        
        # Veritabanını güncelle
        await self._save_campaign_state(campaign_id)
        
        logger.info(f"Kampanya {campaign_id} batch gönderimi: {sent_count}/{len(user_ids)}")
        return sent_count
    
    async def _send_promo_batch(self, user_ids, template, campaign):
        """
        Bir grup kullanıcıya tanıtım mesajı gönderir.
        
        Args:
            user_ids: Kullanıcı ID'leri listesi
            template: Mesaj şablonu
            campaign: Kampanya bilgisi
            
        Returns:
            int: Gönderilen mesaj sayısı
        """
        if not self.services.get('dm'):
            logger.error("DM servisi bulunamadı!")
            return 0
            
        dm_service = self.services.get('dm')
        if not hasattr(dm_service, '_send_promo_to_user'):
            logger.error("DM servisinde _send_promo_to_user metodu bulunamadı!")
            return 0
            
        sent_count = 0
        for user_id in user_ids:
            # Önce hız sınırlaması
            wait_time = self.rate_limiter.get_wait_time()
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            
            # Mesajı gönder
            try:
                user_data = await self._run_async_db_method(self.db.get_user, user_id)
                if user_data:
                    success = await dm_service._send_promo_to_user(user_data, template, is_campaign=True)
                    if success:
                        sent_count += 1
                        # Veritabanını güncelle
                        await self._run_async_db_method(
                            self.db.mark_promo_sent, 
                            user_id, 
                            campaign.get('id', 'general')
                        )
                    
                    # Rate limiter güncelle
                    self.rate_limiter.mark_used()
                    
            except Exception as e:
                logger.error(f"Kullanıcı {user_id}'ye tanıtım gönderilirken hata: {str(e)}")
            
            # Kullanıcılar arası biraz bekle
            await asyncio.sleep(1)
        
        # İstatistikleri güncelle
        self.promo_sent += sent_count
        return sent_count
    
    def _choose_promo_template(self, segment='general'):
        """
        Belirtilen segment için bir tanıtım şablonu seçer.
        
        Args:
            segment: Kullanıcı segmenti
            
        Returns:
            str: Şablon metni
        """
        # Segment için şablon var mı?
        templates = self.promo_templates.get(segment, [])
        if not templates:
            # Segment için şablon yoksa, genel şablonları kullan
            templates = self.promo_templates.get('general', ["Merhaba! Grup linklerimiz: t.me/{}"])
        
        return random.choice(templates) if templates else None
    
    async def _is_campaign_completed(self, campaign_id):
        """
        Kampanyanın tamamlanıp tamamlanmadığını kontrol eder.
        
        Args:
            campaign_id: Kampanya ID'si
            
        Returns:
            bool: Tamamlandıysa True
        """
        if campaign_id not in self.campaigns:
            return True
            
        campaign = self.campaigns[campaign_id]
        # Hedef kullanıcı sayısı doldu mu?
        target = campaign.get('target_count', 0)
        sent = campaign.get('sent_count', 0)
        
        if target > 0 and sent >= target:
            return True
            
        # Bitiş tarihi geçti mi?
        end_date = campaign.get('end_date')
        if end_date:
            end_time = datetime.fromisoformat(end_date)
            if datetime.now() > end_time:
                return True
                
        # Manuel olarak durduruldu mu?
        if campaign.get('completed', False) or campaign.get('paused', False):
            return True
            
        return False
    
    async def _mark_campaign_completed(self, campaign_id):
        """
        Kampanyayı tamamlandı olarak işaretler.
        
        Args:
            campaign_id: Kampanya ID'si
        """
        if campaign_id in self.campaigns:
            self.campaigns[campaign_id]['completed'] = True
            self.campaigns[campaign_id]['completion_date'] = datetime.now().isoformat()
            
            # Veritabanını güncelle
            await self._save_campaign_state(campaign_id)
            logger.info(f"Kampanya {campaign_id} tamamlandı olarak işaretlendi")
    
    async def _save_campaign_state(self, campaign_id):
        """
        Kampanya durumunu veritabanına kaydeder.
        
        Args:
            campaign_id: Kampanya ID'si
        """
        if campaign_id not in self.campaigns:
            return
            
        try:
            if hasattr(self.db, 'update_campaign'):
                await self._run_async_db_method(
                    self.db.update_campaign,
                    campaign_id,
                    self.campaigns[campaign_id]
                )
                logger.debug(f"Kampanya {campaign_id} durumu veritabanına kaydedildi")
        except Exception as e:
            logger.error(f"Kampanya durumu kaydedilirken hata: {str(e)}")
    
    def set_services(self, services):
        """
        Diğer servislere referansları ayarlar.
        
        Args:
            services: Servis adı -> servis nesnesi eşleşmesi
        """
        self.services = services
        logger.debug(f"Tanıtım servisi diğer servislere bağlandı")
    
    async def create_campaign(self, name, segment, target_count=0, batch_size=None, 
                           cooldown_hours=None, end_date=None, description=None):
        """
        Yeni bir tanıtım kampanyası oluşturur.
        
        Args:
            name: Kampanya adı
            segment: Hedef segment
            target_count: Hedef kullanıcı sayısı (0=tümü)
            batch_size: Her batch'te gönderilecek mesaj sayısı
            cooldown_hours: Aynı kullanıcıya tekrar göndermeden önce bekleme süresi
            end_date: Bitiş tarihi (None=süresiz)
            description: Kampanya açıklaması
            
        Returns:
            str: Yeni kampanya ID'si
        """
        import uuid
        
        campaign_id = f"campaign_{str(uuid.uuid4())[:8]}"
        
        # Varsayılan değerleri ayarla
        if batch_size is None:
            batch_size = self.batch_size
        if cooldown_hours is None:
            cooldown_hours = self.cooldown_hours
            
        # Kampanya verilerini oluştur
        campaign = {
            'id': campaign_id,
            'name': name,
            'description': description or f"{name} kampanyası",
            'segment': segment,
            'start_date': datetime.now().isoformat(),
            'end_date': end_date.isoformat() if end_date else None,
            'target_count': target_count,
            'batch_size': batch_size,
            'cooldown_hours': cooldown_hours,
            'sent_count': 0,
            'completed': False,
            'paused': False,
            'is_active': True
        }
        
        # Kampanyayı kaydet
        self.campaigns[campaign_id] = campaign
        
        # Veritabanına kaydet
        try:
            if hasattr(self.db, 'add_campaign'):
                await self._run_async_db_method(self.db.add_campaign, campaign_id, campaign)
                logger.info(f"Yeni kampanya oluşturuldu ve kaydedildi: {campaign_id}")
        except Exception as e:
            logger.error(f"Yeni kampanya kaydedilirken hata: {str(e)}")
            
        return campaign_id
    
    async def pause_campaign(self, campaign_id):
        """
        Kampanyayı duraklatır.
        
        Args:
            campaign_id: Kampanya ID'si
        """
        if campaign_id in self.campaigns:
            self.campaigns[campaign_id]['paused'] = True
            await self._save_campaign_state(campaign_id)
            logger.info(f"Kampanya {campaign_id} duraklatıldı")
            
            # Aktif kampanya ise sıfırla
            if self.active_campaign == campaign_id:
                self.active_campaign = None
                
            return True
        
        return False
    
    async def resume_campaign(self, campaign_id):
        """
        Duraklatılmış kampanyaya devam eder.
        
        Args:
            campaign_id: Kampanya ID'si
        """
        if campaign_id in self.campaigns and not self.campaigns[campaign_id]['completed']:
            self.campaigns[campaign_id]['paused'] = False
            await self._save_campaign_state(campaign_id)
            logger.info(f"Kampanya {campaign_id} devam ettiriliyor")
            return True
        
        return False
    
    async def get_status(self) -> Dict[str, Any]:
        """
        Servisin mevcut durumunu döndürür.
        
        Returns:
            Dict: Servis durum bilgileri
        """
        status = await super().get_status()
        
        # Kampanya sayıları
        active = sum(1 for c in self.campaigns.values() 
                    if not c.get('completed') and not c.get('paused'))
        completed = sum(1 for c in self.campaigns.values() 
                       if c.get('completed', False))
        paused = sum(1 for c in self.campaigns.values() 
                    if c.get('paused', False) and not c.get('completed', False))
        
        status.update({
            'promo_sent': self.promo_sent,
            'campaign_count': len(self.campaigns),
            'active_campaigns': active,
            'completed_campaigns': completed,
            'paused_campaigns': paused,
            'current_campaign': self.active_campaign,
            'user_segments': {k: len(v) for k, v in self.user_segments.items()}
        })
        
        return status
    
    async def get_statistics(self) -> Dict[str, Any]:
        """
        Servis istatistiklerini döndürür.
        
        Returns:
            Dict: Servis istatistikleri
        """
        stats = {
            'total_sent': self.promo_sent,
            'campaigns': len(self.campaigns),
            'segments': {
                segment: len(users) for segment, users in self.user_segments.items()
            }
        }
        
        # En son kampanya istatistiklerini ekle
        if self.active_campaign:
            campaign = self.campaigns.get(self.active_campaign, {})
            stats['current_campaign'] = {
                'name': campaign.get('name', 'Unknown'),
                'sent': campaign.get('sent_count', 0),
                'target': campaign.get('target_count', 0),
                'segment': campaign.get('segment', 'general')
            }
            
        return stats
    
    async def _run_async_db_method(self, method, *args, **kwargs):
        """Veritabanı metodunu thread-safe biçimde çalıştırır."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, 
            lambda: method(*args, **kwargs)
        )

    async def _fetch_target_users_segment(self, segment_id=None):
        """
        Hedef kullanıcı segmentini getirir.
        Segment bazlı metot yoksa tüm aktif kullanıcıları döndürür.
        """
        try:
            # Segment bazlı kullanıcı listesi alma metodu var mı kontrol et
            if hasattr(self.db, 'get_users_by_segment'):
                try:
                    users = await self._run_async_db_method(self.db.get_users_by_segment, segment_id)
                    if users:
                        logger.info(f"Segment ID {segment_id} için {len(users)} kullanıcı bulundu")
                        return users
                except Exception as e:
                    logger.error(f"Segment kullanıcıları getirme hatası: {e}")
            else:
                logger.warning("Veritabanında segment bazlı kullanıcı alma metodu bulunamadı")
                
            # Alternatif 1: Tüm aktif kullanıcıları al
            if hasattr(self.db, 'get_active_users'):
                users = await self._run_async_db_method(self.db.get_active_users, limit=100)
                logger.info(f"Alternatif olarak {len(users)} aktif kullanıcı alındı")
                return users
                
            # Alternatif 2: Tüm kullanıcıları al
            if hasattr(self.db, 'get_all_users'):
                users = await self._run_async_db_method(self.db.get_all_users, limit=100)
                logger.info(f"Alternatif olarak {len(users)} kullanıcı alındı (tüm kullanıcılar)")
                return users
            
            # Hiçbir yöntem işe yaramadıysa
            logger.error("Kullanıcı alma yöntemleri bulunamadı")
            return []
        except Exception as e:
            logger.error(f"Hedef kullanıcı segmenti getirme hatası: {e}")
            return []

    async def _select_message_template(self, group_id, message_type="promotion"):
        """Şablon seçer ve formatlar."""
        try:
            templates = []
            
            if message_type == "promotion" and hasattr(self, 'promotion_templates'):
                templates = self.promotion_templates
            elif message_type == "invitation" and hasattr(self, 'invite_templates'):
                templates = self.invite_templates
            else:
                templates = self.general_templates
            
            if not templates:
                return "Merhaba! Grubumuz için: t.me/telegram_bot_group"
                
            # Şablon seç
            template = random.choice(templates)
            
            # Grup linkleri listesinden rastgele bir link seç
            if not hasattr(self, 'group_links') or not self.group_links:
                # Varsayılan grup linki
                group_link = "telegram_bot_group" 
            else:
                group_link = random.choice(self.group_links)
                
            # Boş karakter kontrolü ekle
            if not group_link or group_link.strip() == "":
                group_link = "telegram_bot_group"
                
            # Format işlemini doğru parametrelerle yap - {} yerine gerçek link yerleştirilecek
            formatted_message = template.format(group_link)
            
            return formatted_message
        except Exception as e:
            logger.error(f"Şablon seçme hatası: {str(e)}")
            # Hata olduğunda basit bir mesaj dönder
            return "Grubumuzu ziyaret edin!"

    async def send_promotion(self, group_id, message_text):
        """
        Promosyon mesajını gönderir ve tekrarları önler.
        """
        try:
            # Son gönderim zamanını kontrol et
            now = datetime.now()
            if group_id in self.last_sent_times:
                last_sent = self.last_sent_times[group_id]
                elapsed = (now - last_sent).total_seconds()
                
                # Aynı gruba kısa sürede tekrar göndermeme kontrolü
                if elapsed < self.min_send_interval:
                    logger.info(f"Bu gruba ({group_id}) son {elapsed:.0f} saniye içinde zaten mesaj gönderildi. Atlanıyor.")
                    return False
            
            # Mesajı gönder
            message = await self.client.send_message(group_id, message_text)
            
            # Son gönderim zamanını güncelle
            self.last_sent_times[group_id] = now
            
            return True
        except Exception as e:
            logger.error(f"Promosyon gönderme hatası: {str(e)}")
            return False

    async def _process_group(self, group):
        try:
            # Grup ID ve başlık bilgilerini al
            group_id = group.get('group_id') or group.get('id')
            group_title = group.get('title', '')
            
            # Grup ID kontrolü
            if not group_id:
                logger.warning(f"Geçersiz grup ID: {group}")
                return False
                
            # Mesaj şablonu seç
            message = await self._select_message_template(group_id, message_type="promotion")
            
            # Şablonda hala {} varsa uyarı ver ve düzelt
            if "{}" in message:
                logger.warning(f"Format uygulanmamış şablon tespit edildi: {message}")
                # Acil düzeltme - varsayılan grup linki ekle
                message = message.replace("{}", "telegram_bot_group")
            
            # Mesajı gönder
            success = await self.send_promotion(group_id, message)
            
            return success
        except Exception as e:
            logger.error(f"Grup işleme hatası: {str(e)}")
            return False

    # Grup bağlantılarını belirli bir formatta tutun
    def _normalize_group_link(self, link):
        """Grup bağlantısını normalize eder."""
        if not link:
            return "telegram_bot_group"
            
        # @ veya t.me/ ile başlayan linkleri temizle
        if link.startswith("@"):
            return link[1:]
        elif "t.me/" in link:
            return link.split("t.me/")[-1]
        
        return link

# Alias tanımı
PromotionService = PromoService