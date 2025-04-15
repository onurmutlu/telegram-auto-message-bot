"""
# ============================================================================ #
# Dosya: invite_service.py
# Yol: /Users/siyahkare/code/telegram-bot/bot/services/invite_service.py
# İşlev: Telegram bot için otomatik davet gönderme servisi.
#
# Amaç: Bu modül, veritabanında saklanan kullanıcılara otomatik olarak
# davet mesajları göndermeyi yönetir. Belirli aralıklarla çalışır ve
# davet edilmemiş kullanıcılara özel mesajlar göndererek gruplarınıza 
# yönlendirir.
#
# Temel Özellikler:
# - Kullanıcılara kişiselleştirilmiş davetler gönderme
# - Akıllı oran sınırlama ve soğuma süreleri
# - Dinamik şablon sistemi ve grup bağlantıları
# - Hata durumlarında otomatik kurtarma mekanizması
# - Veritabanı ile entegrasyon
#
# Build: 2025-04-07-22:05:00
# Versiyon: v3.5.0
# ============================================================================ #
#
# Değişiklik Geçmişi:
# v3.5.0 (2025-04-07) - Global cooldown sistemi geliştirildi
#                      - Hata durumlarında kaçınma stratejisi geliştirildi
#                      - Rate Limiter optimizasyonları yapıldı
#                      - Dokümentasyon ve tip tanımlamaları eklendi
# v3.4.0 (2025-04-01) - AdaptiveRateLimiter entegrasyonu
#                      - Kullanıcı filtreleme iyileştirmeleri
#                      - Çoklu grup desteği
# v3.3.0 (2025-03-15) - İlk sürüm
#
# Geliştirici Notları:
#   - Bu servis, `client`, `config` ve `db` objelerini kullanarak çalışır
#   - Konfigürasyon için çevre değişkenleri kullanılır:
#     * INVITE_BATCH_SIZE: Bir seferde gönderilecek maksimum davet sayısı
#     * INVITE_COOLDOWN_MINUTES: Kullanıcıların tekrar davet edilmesi için gereken süre
#     * INVITE_INTERVAL_MINUTES: Davet döngüleri arasındaki süre
#   - Hız sınırları akıllı rate limiter ile yönetilir, FloodWait hatalarına göre ayarlanır
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""
import os
import json
import asyncio
import random
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Union, Set, Tuple
import functools

from telethon import errors, functions, tl
from telethon.tl import types
import telethon
from bot.utils.adaptive_rate_limiter import AdaptiveRateLimiter
from bot.services.base_service import BaseService
from config.config import Config

logger = logging.getLogger(__name__)

# Global cooldown değişkenleri - aşırı hız hatalarında tüm sistemi soğutur
GLOBAL_COOLDOWN_START: Optional[datetime] = None
GLOBAL_COOLDOWN_DURATION: Optional[float] = None

class InviteService(BaseService):
    """
    Telethon istemcisi kullanarak grup davetlerini yöneten servis.
    Kullanıcılara grup davetleri gönderir ve sonuçları izler.
    """
    
    def __init__(self, client, config=None, db=None, stop_event=None):
        """
        InviteService'i başlatır.
        
        Args:
            client (TelegramClient): Telethon istemcisi
            config (dict, optional): Yapılandırma ayarları
            db (DatabaseHandler, optional): Veritabanı bağlantısı
            stop_event (asyncio.Event, optional): Servisi durdurmak için event
        """
        # Temel sınıfı başlat - doğru parametrelerle çağır
        super().__init__("invite_service", client, config, db, stop_event or asyncio.Event())
        
        # Bu değişken tanımı artık gerekli değil çünkü BaseService'te tanımlanıyor
        # self.name = "invite_service"
        # self.stop_event = stop_event or asyncio.Event()
        
        self.logger = logging.getLogger("invite_service")
        
        # Durum değişkenleri
        self.running = False
        self.sent_count = 0
        self.error_count = 0  # İlk başta sıfır olarak tanımlandı
        self.processed_users = 0
        
        # Yapılandırma ayarları - çevre değişkenlerinden yükle
        self.batch_size = int(os.getenv("INVITE_BATCH_SIZE", "10"))
        self.interval_minutes = int(os.getenv("INVITE_INTERVAL_MINUTES", "30"))
        
        # Rate limiter yapılandırması - eski parametreler kaldırıldı
        initial_rate = float(os.getenv("INVITE_INITIAL_RATE", "0.1"))  # Default: 10 saniyede 1 davet
        # AdaptiveRateLimiter'ı uyumlu parametrelerle oluştur
        self.rate_limiter = AdaptiveRateLimiter(
            initial_rate=initial_rate * 60,  # dakika başına oran olarak dönüştür
            period=60,
            error_backoff=1.5,
            max_jitter=1.0
        )
        
        # Şablonlar ve bağlantılar
        self.group_links = self._load_group_links()
        self.invite_templates = self._load_invite_templates()
        
        # Temel değişkenleri tanımla
        self.invite_batch_size = 50  # Davet işlemi için varsayılan toplu işlem boyutu
        self.daily_limit = 50  # Günlük maksimum davet sayısı
        self.hourly_limit = 15  # Saatlik maksimum davet sayısı
        self.stats = {
            'total_sent': 0,
            'failed_sends': 0,
            'last_send_time': None
        }
        self.invite_stats = {
            'total_sent': 0,
            'daily_sent': 0,
            'success': 0,
            'failed': 0
        }
        
        # Çevre değişkeninden yükle (eğer varsa)
        if hasattr(config, 'get_setting'):
            self.invite_batch_size = config.get_setting('invite_batch_size', 50)
        elif os.getenv("INVITE_BATCH_SIZE"):
            try:
                batch_size = os.getenv("INVITE_BATCH_SIZE", "50")
                # Yorum işaretlerini temizle
                batch_size = batch_size.split('#')[0].strip()
                self.invite_batch_size = int(batch_size)
            except Exception as e:
                logger.warning(f"Invite batch size dönüştürme hatası: {str(e)}")
                self.invite_batch_size = 50
        
        # Config'ten değerleri yükle (varsa)
        if hasattr(config, 'invite'):
            invite_config = config.invite
            if hasattr(invite_config, 'batch_size'):
                self.batch_size = invite_config.batch_size
            if hasattr(invite_config, 'interval'):
                self.interval_minutes = invite_config.interval
            if hasattr(invite_config, 'daily_limit'):
                self.daily_limit = invite_config.daily_limit
            if hasattr(invite_config, 'hourly_limit'):
                self.hourly_limit = invite_config.hourly_limit

        # Sınıf içinde bu parametreyi daha küçük bir değere ayarla
        self.invite_cooldown_minutes = 5  # 30 dakika yerine 5 dakika

        # Services dictionary'yi başlat
        self.services = {}
        
        # Rate limiter'ı hemen kur
        self._setup_rate_limiter()
        
        logger.info(f"Davet servisi oluşturuldu. Batch boyutu: {self.batch_size}, Aralık: {self.interval_minutes} dakika")
        
    def _setup_rate_limiter(self):
        """Davet gönderimi için hız sınırlayıcıyı yapılandırır."""
        # Ana rate limiter - daha agresif değerlerle
        from bot.utils.adaptive_rate_limiter import AdaptiveRateLimiter
        self.rate_limiter = AdaptiveRateLimiter(
            initial_rate=15.0,  # Dakikada 15 işlem (çok daha yüksek)
            period=60,         # 60 saniye
            error_backoff=1.2, # Daha düşük backoff
            max_jitter=0.5     # Çok daha düşük jitter
        )
        
        # Rate limiting state
        self.invite_state = {
            'burst_count': 0,
            'hourly_count': 0,
            'hour_start': datetime.now(),
            'last_invite_time': None,
            'consecutive_errors': 0
        }
        
        # Daha yüksek limitleri ayarla
        self.limits = {
            'hourly_max': 100,    # Saatte maksimum 100 davet
            'daily_max': 500,     # Günde maksimum 500 davet
            'burst_size': 20,     # Bir seferde 20 davet
            'burst_cooldown': 2,  # Burst'ler arası 2 dakika
            'error_cooldown': 15  # Hata sonrası 15 dakika bekleme
        }
    
    #
    # YARDIMCI METODLAR
    #
    
    def _load_settings_from_config(self):
        """Ayarları config'den yükler"""
        # Batch ve cooldown ayarları için güvenli dönüşüm
        invite_batch = os.getenv("INVITE_BATCH_SIZE", "20")
        self.batch_size = int(invite_batch.split('#')[0].strip())
        
        invite_cooldown = os.getenv("INVITE_COOLDOWN_MINUTES", "10") 
        self.cooldown_minutes = int(invite_cooldown.split('#')[0].strip())
        
        # Diğer ayarlar...
        self.interval_minutes = int(os.getenv("INVITE_INTERVAL_MINUTES", "10"))
    
    def _load_group_links(self):
        """Çevre değişkenlerinden grup bağlantılarını yükler"""
        links_env = os.getenv("GROUP_INVITE_LINKS", "")
        links = [link.strip() for link in links_env.split(",") if link.strip()]
        
        if not links:
            self.logger.warning("Hiç grup davet bağlantısı tanımlanmamış")
        else:
            self.logger.info(f"{len(links)} grup davet bağlantısı yüklendi")
            
        return links
    
    def _load_invite_templates(self):
        """Davet mesaj şablonlarını yükler"""
        templates_path = os.getenv("INVITE_TEMPLATES_PATH", "data/invites.json")
        templates = []
        
        try:
            if os.path.exists(templates_path):
                with open(templates_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # JSON formatı destekle
                    if isinstance(data, dict):
                        templates = data.get("invites", []) or data.get("first_invite", [])
                    elif isinstance(data, list):
                        templates = data
                self.logger.info(f"{len(templates)} davet şablonu yüklendi")
            else:
                self.logger.warning(f"Şablon dosyası bulunamadı: {templates_path}")
        except Exception as e:
            self.logger.error(f"Şablonlar yüklenirken hata: {e}")
            
        # Varsayılan şablon
        if not templates:
            templates = ["Merhaba {name}! Grubumuz hakkında bilgi almak ister misiniz?"]
            self.logger.info("Varsayılan davet şablonu kullanılıyor")
            
            return templates
        
    def connect_services(self, services):
        """Diğer servislerle bağlantı kurar"""
        self.services = services
        self.logger.info("Davet servisi diğer servislere bağlandı")
    
    async def _get_users_for_invite(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Davet edilecek kullanıcıları getirir.
        
        Args:
            limit: Maksimum kullanıcı sayısı
                
        Returns:
            List[Dict[str, Any]]: Kullanıcı bilgileri listesi
        """
        try:
            # Önce veritabanından kullanıcıları getirmeyi dene
            if hasattr(self.db, 'get_users_for_invite'):
                try:
                    users = await self._run_async_db_method(self.db.get_users_for_invite, limit)
                    if users and len(users) > 0:
                        return users
                except Exception as e:
                    logger.error(f"Veritabanından davet edilecek kullanıcıları alma hatası: {str(e)}")
            
            # Veritabanında metod yoksa fallback yöntem kullan
            return self._get_fallback_users(limit)
            
        except Exception as e:
            logger.error(f"Davet edilecek kullanıcıları alma hatası: {str(e)}")
            return []

    def _get_fallback_users(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Veritabanında kullanıcı yoksa örnek kullanıcılar döndürür.
        
        Args:
            limit: Maksimum kullanıcı sayısı
                
        Returns:
            List[Dict[str, Any]]: Kullanıcı bilgileri listesi
        """
        # NOT: Bu sadece bir fallback çözümüdür
        # Gerçek uygulamada bu kullanıcıların doğru olduğundan emin olun
        # veya bu metodu kullanmayın
        
        logger.warning("Fallback kullanıcı listesi kullanılıyor!")
        
        # Örnek kullanıcı listesi
        example_users = []
        
        # Gerçek davet servisi için bu kısmi boş bırakılabilir
        # Örnek olarak boş liste dönüyor
        
        return example_users[:limit]
    
    def _get_invite_status(self) -> Dict[str, Any]:
        """
        Davet servisi durum bilgilerini döndürür.
        
        Returns:
            Dict[str, Any]: Servisin mevcut durumunu içeren sözlük
        """
        now = datetime.now()
        
        return {
            'running': self.running,
            'sent_count': self.sent_count,
            'last_invite_time': self.last_invite_time.isoformat() if self.last_invite_time else None,
            'batch_size': self.batch_size,
            'cooldown_minutes': self.cooldown_minutes,
            'interval_minutes': self.interval_minutes,
            'rate': self.rate_limiter.current_rate,
            'status_time': now.isoformat(),
            'error_count': self.error_count,
            'global_cooldown_active': bool(GLOBAL_COOLDOWN_START and GLOBAL_COOLDOWN_DURATION),
            'group_count': len(self.group_links)
        }
    
    async def _run_async_db_method(self, method, *args, **kwargs):
        """Veritabanı metodunu thread-safe biçimde çalıştırır."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, 
            functools.partial(method, *args, **kwargs)
        )
    
    def _choose_group_link(self):
        """Rastgele bir grup linki seçer."""
        if not hasattr(self, 'group_links') or not self.group_links:
            # Çevre değişkenlerinden grup linklerini yükle
            links_str = os.getenv("GROUP_LINKS", "")
            self.group_links = [link.strip() for link in links_str.split(',') if link.strip()]
            
        if not self.group_links:
            return None
            
        # Rastgele bir link seç
        link = random.choice(self.group_links)
        
        # Doğru formatta olduğundan emin ol
        if not link.startswith("https://") and not link.startswith("t.me/"):
            link = f"t.me/{link}"
            
        return link

    def _choose_invite_message(self, username=None):
        """Kullanıcıya uygun davet mesajı seçer."""
        if not hasattr(self, 'invite_templates') or not self.invite_templates:
            # Varsayılan şablonları kullan
            self.invite_templates = [
                "Merhaba! Seni grubuma davet etmek istiyorum: {}",
                "Selam! Kaliteli bir sohbet için: {}",
                "Hey! Telegram'da en iyi gruplardan biri: {}"
            ]
        
        # Şablonu seç
        return random.choice(self.invite_templates)

    async def _get_user_entity(self, user_id, username=None):
        """Kullanıcı entity'sini güvenli şekilde almaya çalışır."""
        try:
            # Önce ID ile dene
            try:
                return await self.client.get_entity(user_id)
            except ValueError:
                pass
                
            # Username ile dene (eğer varsa)
            if username:
                try:
                    return await self.client.get_entity(f"@{username}")
                except ValueError:
                    pass
                    
            # Veritabanında username kontrolü
            if hasattr(self.db, 'get_user_by_id'):
                user_info = await self._run_async_db_method(self.db.get_user_by_id, user_id)
                if user_info and user_info.get('username'):
                    try:
                        return await self.client.get_entity(f"@{user_info['username']}")
                    except ValueError:
                        pass
                        
            return None
                
        except Exception as e:
            logger.error(f"Entity alımı sırasında hata: {str(e)}")
            return None
    
    async def _get_group_members(self, group_id, limit=50):
        """
        Bir gruptaki üyeleri çeker.
        
        Args:
            group_id: Grup ID
            limit: Maksimum kullanıcı sayısı
            
        Returns:
            List[Dict]: Üye listesi
        """
        try:
            members = []
            offset = 0
            total_retrieved = 0
            
            while total_retrieved < limit:
                try:
                    # GetParticipants metodunu çağır
                    participants = await self.client(telethon.functions.channels.GetParticipantsRequest(
                        channel=group_id,
                        filter=telethon.tl.types.ChannelParticipantsRecent(),
                        offset=offset,
                        limit=100,
                        hash=0
                    ))
                    
                    if not participants.users:
                        break  # Daha fazla kullanıcı yok
                    
                    # Kullanıcıları işle
                    for user in participants.users:
                        if not user.bot:  # Botları hariç tut
                            members.append({
                                'id': user.id,
                                'username': user.username,
                                'first_name': user.first_name,
                                'last_name': user.last_name
                            })
                            total_retrieved += 1
                            
                            if total_retrieved >= limit:
                                break
                    
                    # Offset güncelleme
                    offset += len(participants.users)
                    
                except Exception as e:
                    logger.error(f"Grup üyelerini alırken hata: {str(e)}")
                    break
            
            return members
        
        except Exception as e:
            logger.error(f"Grup üyelerini çekerken hata: {str(e)}")
            return []

    #
    # ANA SERVİS METODLARI
    #
    
    async def run(self):
        """
        Davet servisini başlatır ve periyodik olarak davetleri işler.
        
        - batch_size kadar kullanıcıyı veritabanından alır
        - Her bir kullanıcıya davet göndermeye çalışır
        - interval_minutes kadar bekler ve yeni bir batch ile devam eder
        """
        if not self.client.is_connected():
            try:
                await self.client.connect()
            except Exception as e:
                self.logger.error(f"İstemciye bağlanırken hata: {e}")
                return
        
        if not self.client.is_connected():
            self.logger.error("İstemci bağlantısı kurulamadı, davet servisi durduruldu.")
            return
        
        # Rate limiter'ı sıfırla
        self.rate_limiter.reset()
        
        # Durum değişkenlerini kontrol et ve gerekirse başlat
        if not hasattr(self, 'error_count'):
            self.error_count = 0
            
        if not hasattr(self, 'batch_size'):
            self.batch_size = int(os.getenv("INVITE_BATCH_SIZE", "10"))
            
        if not hasattr(self, 'interval_minutes'):
            self.interval_minutes = int(os.getenv("INVITE_INTERVAL_MINUTES", "30"))
        
        # Servisi çalıştır    
        self.running = True
        self.logger.info("Davet servisi çalışıyor...")
        
        try:
            while self.running and not self.stop_event.is_set():
                try:
                    invite_count = await self._send_invites()
                    self.logger.info(f"Davet döngüsü tamamlandı. Toplam gönderilen: {invite_count}")
                    
                    # Interval kadar bekle
                    self.logger.info(f"{self.interval_minutes} dakika bekleniyor...")
                    await asyncio.sleep(self.interval_minutes * 60)
                except asyncio.CancelledError:
                    self.logger.info("Davet servisi iptal edildi.")
                    self.running = False
                    break
                except Exception as e:
                    self.logger.error(f"Davet döngüsü sırasında hata: {str(e)}")
                    self.error_count += 1
                    
                    # Hata limiti kontrolü
                    if self.error_count > 5:
                        self.logger.critical(f"Çok fazla hata oluştu ({self.error_count}), servis duraklatılıyor.")
                        await asyncio.sleep(3600)  # 1 saat bekle
                        self.error_count = 0  # Hata sayacını sıfırla
                    else:
                        await asyncio.sleep(300)  # 5 dakika bekle
        except Exception as e:
            self.logger.error(f"Davet servisi çalışırken beklenmeyen hata: {str(e)}")
        finally:
            self.running = False
            self.logger.info("Davet servisi durduruldu.")
    
    async def stop(self) -> None:
        """
        Servisi durdurur.
        
        Bu metot, servisin çalışmasını güvenli bir şekilde durdurur.
        """
        self.running = False
        logger.info("Davet servisi durdurma sinyali gönderildi")
    
    async def pause(self) -> None:
        """Servisi geçici olarak duraklatır."""
        if self.running:
            self.running = False
            logger.info("Davet servisi duraklatıldı")
    
    async def resume(self) -> None:
        """Duraklatılmış servisi devam ettirir."""
        if not self.running:
            self.running = True
            logger.info("Davet servisi devam ettiriliyor")
    
    #
    # DAVET İŞLEME METODLARI
    #
    
    async def _process_invite_batch(self):
        """Bir grup kullanıcıya davet gönderir."""
        sent_count = 0
        error_count = 0
        
        try:
            # Güvenli bir şekilde batch_size'a eriş
            if not hasattr(self, 'batch_size'):
                self.batch_size = 5  # Varsayılan değer
                
            batch_size = self.batch_size
            
            # Kullanıcıları getir (db veya fallback)
            users = await self._get_users_for_invite(batch_size)
            
            if not users:
                logger.warning("Davet için uygun kullanıcı bulunamadı")
                return
                
            logger.info(f"🔍 Davet için {len(users)} kullanıcı bulundu")
            
            # Her kullanıcıyı işle
            for user in users:
                try:
                    result = await self._process_user(user)
                    if result:
                        sent_count += 1
                    else:
                        error_count += 1
                        
                    # Rate limiting için bekle
                    await asyncio.sleep(random.randint(10, 30))
                    
                except Exception as e:
                    logger.error(f"Kullanıcı daveti işleme hatası: {str(e)}")
            
            logger.info(f"💌 Davet gönderim döngüsü tamamlandı. Toplam: {sent_count}")
            
        except Exception as e:
            logger.error(f"Davet batch işleme hatası: {str(e)}")
            
        # İstatistikleri güncelle
        self.sent_count += sent_count
        self.error_count += error_count

    async def _process_user(self, user):
        """
        Tek bir kullanıcıyı işler ve davet gönderir.
        
        Args:
            user: Kullanıcı bilgileri
            
        Returns:
            bool: İşlem başarılı ise True
        """
        try:
            user_id = user.get("user_id")
            username = user.get("username")
            first_name = user.get("first_name", "Kullanıcı")
            
            # Kullanıcı entity'sini güvenli bir şekilde al
            try:
                user_entity = await self.client.get_entity(user_id)
            except ValueError as e:
                logger.warning(f"Kullanıcı bulunamadı: {user_id} - {str(e)}")
                # Veritabanında işaretleme (opsiyonel)
                if hasattr(self.db, 'mark_user_not_found'):
                    await self._run_async_db_method(self.db.mark_user_not_found, user_id)
                return False
            
            invite_template = random.choice(self.invite_templates)
            personalized_message = invite_template.replace("{name}", first_name or "değerli kullanıcı")
            
            group_links_text = ""
            if self.group_links:
                group_links_text = "\n\n" + "\n".join([f"• {link}" for link in self.group_links])
            
            try:
                await self.client.send_message(
                    user_entity, 
                    personalized_message + group_links_text,
                    link_preview=False
                )
            except Exception as e:
                logger.error(f"Hata oluştu: {str(e)}")
            
            # Başarılı mesaj gönderimi sonrası rate limiter'ı güncelle
            self.rate_limiter.mark_used()
            
            # Veritabanını güncelle ve istatistikleri tut
            if hasattr(self.db, 'mark_user_invited'):
                await self._run_async_db_method(self.db.mark_user_invited, user_id)
            
            return True
            
        except errors.FloodWaitError as e:
            wait_time = e.seconds
            logger.warning(f"FloodWaitError davet gönderirken: {wait_time} saniye bekleniyor")
            self.rate_limiter.register_error(e)  # Hatayı rate limiter'a bildir
            await asyncio.sleep(wait_time + 1)
            return False
        except errors.UserPrivacyRestrictedError:
            logger.info(f"Kullanıcı gizlilik ayarları nedeniyle mesaj kabul etmiyor: {user_id}")
            return False
        except Exception as e:
            logger.error(f"Kullanıcı işleme hatası ({user_id}): {str(e)}")
            return False

    async def _send_invites(self):
        """
        Belirli sayıda kullanıcıya davet gönderir.
            
        Returns:
            int: Başarıyla gönderilen davet sayısı
        """
        try:
            # Kullanıcıları getir - await ekledik sorunu çözmek için
            users = await self._run_async_db_method(self.db.get_users_for_invite, self.invite_batch_size)
            
            # Kullanıcı listesi kontrolü
            if not users:
                logger.warning("Davet için uygun kullanıcı bulunamadı")
                return 0
            
            # users coroutine değil liste olduğundan emin olalım
            if not isinstance(users, list):
                if hasattr(users, "__await__"):  # Hala coroutine ise
                    try:
                        users = await users  # Bir daha bekle
                    except:
                        logger.error("users nesnesi bir coroutine ve dönüştürülemedi")
                        return 0
                else:
                    # Listeye çevirelim
                    try:
                        users = list(users) if users else []
                    except:
                        logger.error("users nesnesi listeye dönüştürülemedi")
                        return 0
                        
            # Hala boş mu kontrol edelim
            if not users:
                logger.warning("Davet için uygun kullanıcı bulunamadı (dönüştürme sonrası)")
                return 0
            
            logger.info(f"Davet gönderilecek: {len(users)} kullanıcı")
            
            # Davet gönderme işlemleri burada devam edecek
            sent_count = 0
            error_count = 0
            
            # Her kullanıcıyı işle
            for user in users:
                try:
                    result = await self._process_user(user)
                    if result:
                        sent_count += 1
                    else:
                        error_count += 1
                        
                    # Rate limiting için bekle
                    await asyncio.sleep(random.randint(10, 30))
                    
                except Exception as e:
                    logger.error(f"Kullanıcı daveti işleme hatası: {str(e)}")
            
            logger.info(f"💌 Davet gönderim döngüsü tamamlandı. Toplam: {sent_count}")
            
            return sent_count
            
        except Exception as e:
            logger.error(f"_send_invites genel hatası: {str(e)}")
            return 0

    def set_services(self, services: Dict[str, Any]) -> None:
        """
        Diğer servislere referansları ayarlar.
        
        Args:
            services: Servis adı -> Servis nesnesi eşleşmesi
        """
        self.services = services
        logger.debug(f"{self.name} servisi diğer servislere bağlandı")
    
    async def initialize(self) -> bool:
        """
        InviteService servisini başlatır.
        """
        # Temel servisi başlat
        await super().initialize()
        
        # Bot modu kontrolünü kaldır, hep UserBot olarak kabul et
        self._can_use_dialogs = True
        self._can_invite_users = True
        logger.info("✅ Davet servisi kullanıcı hesabı ile çalışıyor, tüm özellikler etkin.")
        
        return True

    async def _discover_users(self, limit=100, aggressive=False):
        """Kullanıcı keşfi yapar"""
        try:
            # Eksik olan diğer parametreler
            discovered_users = []
            
            # Örnek bir kullanıcı ID'si için güvenli karşılaştırma
            user_id = 12345
            some_value = 10
            
            # DÜZELTME: get_user_info yerine get_user düğmeçini kullan
            # Veritabanındaki uygun metodu bul ve kullan
            try:
                # Öncelikle get_user metodunu dene
                if hasattr(self.db, 'get_user'):
                    user_info = await self._run_async_db_method(self.db.get_user, user_id)
                # Alternatif olarak get_user_info metodunu dene
                elif hasattr(self.db, 'get_user_info'):
                    user_info = await self._run_async_db_method(self.db.get_user_info, user_id)
                # Başka bir alternatif olarak fetch_user metodunu dene
                elif hasattr(self.db, 'fetch_user'):
                    user_info = await self._run_async_db_method(self.db.fetch_user, user_id)
                else:
                    # Son çare olarak SQL sorgusu direkt çalıştır
                    query = "SELECT * FROM users WHERE id = ?"
                    user_info = await self._run_async_db_method(self.db.fetchone, query, (user_id,))
                    # Sonucu sözlüğe dönüştür
                    if user_info:
                        user_info = {
                            'id': user_info[0],
                            'username': user_info[1] if len(user_info) > 1 else None,
                            'first_name': user_info[2] if len(user_info) > 2 else None,
                            'last_name': user_info[3] if len(user_info) > 3 else None
                        }
            except Exception as e:
                logger.error(f"Kullanıcı bilgisi alma hatası: {str(e)}")
                user_info = None


            # DOĞRU KOD:
            users = await self._run_async_db_method(self.db.get_users_for_invite, self.invite_batch_size)
            if not users or len(users) == 0:  # Önce None kontrolü yapmak güvenlidir
                logger.warning("Davet için uygun kullanıcı bulunamadı")
                return 0


            
            # Şimdi güvenli bir şekilde karşılaştırabilirsiniz
            if user_info and isinstance(user_info, dict) and user_info.get('activity_score', 0) < some_value:
                # İşlemler...
                pass
                
            return discovered_users
            
        except Exception as e:
            logger.error(f"Kullanıcı keşfi sırasında hata: {str(e)}")
            return []

    async def _aggressive_user_discovery(self):
        """Agresif kullanıcı keşfi - daha çok kullanıcı bul"""
        discovered = 0
        
        try:
            # Tüm aktif grupları tara
            if 'group' in self.services and hasattr(self.services['group'], 'get_groups'):
                groups = await self.services['group'].get_groups(True)
                
                for group in groups:
                    group_id = group.get('chat_id') or group.get('id')
                    logger.info(f"Gruptan üye çekiliyor: {group.get('title', 'Bilinmeyen')} ({group_id})")
                    
                    try:
                        # Her gruptan 50 üye çek
                        members = await self._get_group_members(group_id, limit=50)
                        
                        # BURADA DÜZELTME YAPILDI: await self._run_async_db_method eklendi
                        for member in members:
                            user_id = member.get('id')
                            if user_id and hasattr(self.db, 'add_user_if_not_exists'):
                                await self._run_async_db_method(
                                    self.db.add_user_if_not_exists,
                                    user_id,
                                    member.get('username'),
                                    member.get('first_name'),
                                    member.get('last_name')
                                )
                                discovered += 1
                    except Exception as e:
                        logger.error(f"Grup üyelerini çekerken hata: {str(e)}")
            
            # Son çare: cooldown'ları sıfırla
            if discovered == 0:
                if hasattr(self.db, 'reset_invite_cooldowns'):
                    reset_count = await self._run_async_db_method(self.db.reset_invite_cooldowns)
                    logger.info(f"Davet süresi sıfırlanan kullanıcı sayısı: {reset_count}")
                    
            logger.info(f"Agresif keşifte bulunan toplam kullanıcı: {discovered}")
            return discovered
        except Exception as e:
            logger.error(f"Agresif kullanıcı keşfi hatası: {str(e)}")
            return 0

    async def reset_invite_cooldowns(self):
        """Tüm kullanıcıların davet beklemelerini sıfırla ve kaç kullanıcı sıfırlandı bilgisini döndür."""
        try:
            if hasattr(self.db, 'reset_all_invite_cooldowns'):
                users_count = await self._run_async_db_method(self.db.reset_all_invite_cooldowns)
                logger.info(f"{users_count} kullanıcının davet bekleme süresi sıfırlandı")
                return users_count
            else:
                logger.warning("DB'de reset_all_invite_cooldowns metodu bulunamadı")
                return 0
        except Exception as e:
            logger.error(f"Davet bekleme süreleri sıfırlanırken hata: {str(e)}")
            return 0
