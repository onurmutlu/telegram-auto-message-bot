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

from telethon import errors
from bot.utils.adaptive_rate_limiter import AdaptiveRateLimiter
from bot.services.base_service import BaseService

logger = logging.getLogger(__name__)

# Global cooldown değişkenleri - aşırı hız hatalarında tüm sistemi soğutur
GLOBAL_COOLDOWN_START: Optional[datetime] = None
GLOBAL_COOLDOWN_DURATION: Optional[float] = None

class InviteService(BaseService):
    """Davet servisi."""
    
    def __init__(self, client, config, db, stop_event=None, initial_period=None):
        """
        InviteService sınıfının başlatıcısı.
        """
        super().__init__('invite', client, config, db, stop_event)
        self.initial_period = initial_period if initial_period is not None else 3600
    
    #
    # YARDIMCI METODLAR
    #
    
    def _load_settings(self):
        """Ayarları çevre değişkenlerinden yükler"""
        # Batch ve cooldown ayarları için güvenli dönüşüm
        invite_batch = os.getenv("INVITE_BATCH_SIZE", "20")
        self.batch_size = int(invite_batch.split('#')[0].strip())
        
        invite_cooldown = os.getenv("INVITE_COOLDOWN_MINUTES", "10") 
        self.cooldown_minutes = int(invite_cooldown.split('#')[0].strip())
        
        # Diğer ayarlar...
        self.interval_minutes = int(os.getenv("INVITE_INTERVAL_MINUTES", "10"))
    
    def _parse_group_links(self) -> List[str]:
        """
        Grup linklerini çevre değişkenlerinden veya config'den alır.
        
        Şu kaynaklardan grup linklerini toplar:
        1. GROUP_LINKS çevre değişkeni
        2. Config nesnesi içindeki GROUP_LINKS
        3. Veritabanından get_group_links metodu varsa
        
        Returns:
            List[str]: Benzersiz grup linkleri listesi
        """
        group_links = []
        
        # Çevre değişkeninden al
        env_links = os.environ.get("GROUP_LINKS", "")
        if env_links:
            links = [link.strip() for link in env_links.split(",") if link.strip()]
            group_links.extend(links)
        
        # Config'den al
        if hasattr(self.config, 'GROUP_LINKS'):
            config_links = self.config.GROUP_LINKS
            if isinstance(config_links, list):
                group_links.extend(config_links)
            elif isinstance(config_links, str):
                links = [link.strip() for link in config_links.split(",") if link.strip()]
                group_links.extend(links)
        
        # Veritabanından al (eğer mevcutsa)
        if hasattr(self.db, 'get_group_links'):
            try:
                db_links = self.db.get_group_links()
                if db_links:
                    group_links.extend(db_links)
            except Exception as e:
                logger.warning(f"Veritabanından grup bağlantıları alınamadı: {e}")
                
        # Tekrarlanan linkleri temizle
        return list(dict.fromkeys(group_links))
    
    def _load_invite_templates(self) -> List[str]:
        """
        Davet şablonlarını yükler.
        
        Şablonları yükleme sırası:
        1. Config nesnesinden INVITE_TEMPLATES
        2. data/templates.json dosyasından "invites" anahtarı
        3. Bulunamazsa varsayılan şablonlar
        
        Returns:
            List[str]: Davet mesaj şablonları
        """
        try:
            # Önce config'den kontrol et
            if hasattr(self.config, 'INVITE_TEMPLATES'):
                templates = self.config.INVITE_TEMPLATES
                if templates:
                    logger.info(f"{len(templates)} davet şablonu konfigürasyondan yüklendi")
                    return templates
            
            # Dosyadan yüklemeyi dene - birden fazla muhtemel yoldan arama yap
            template_paths = [
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                            "data", "templates.json"),
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                            "data", "invites.json"),
                "data/templates.json",
                "data/invites.json"
            ]
            
            for path in template_paths:
                if os.path.exists(path):
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        # Farklı format destekleri
                        if isinstance(data, dict):
                            if "invites" in data:
                                templates = data["invites"]
                                if templates:
                                    logger.info(f"{len(templates)} davet şablonu {path} dosyasından yüklendi")
                                    return templates
                            elif "templates" in data:
                                templates = data["templates"]
                                if templates:
                                    logger.info(f"{len(templates)} davet şablonu {path} dosyasından yüklendi")
                                    return templates
                        elif isinstance(data, list):
                            if data:
                                logger.info(f"{len(data)} davet şablonu {path} dosyasından yüklendi")
                                return data
                            
        except Exception as e:
            logger.error(f"Davet şablonları yüklenemedi: {str(e)}")
        
        # Varsayılan davet şablonları
        default_templates = [
            "Merhaba! Grubuma katılmak ister misin?",
            "Selam! Telegram gruplarımıza bekliyoruz!",
            "Merhaba, sohbet gruplarımıza göz atmak ister misin?",
            "Selam {name}! Gruplarımıza davetlisin!",
            "Merhaba, yeni sohbet arkadaşları arıyorsan gruplarımıza bekleriz."
        ]
        logger.info(f"{len(default_templates)} varsayılan davet şablonu kullanılıyor")
        return default_templates
    
    def _get_fallback_users(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Veritabanı `get_users_for_invite` metodu eksikse alternatif çözüm sunar.
        
        Args:
            limit: Maksimum kullanıcı sayısı
            
        Returns:
            List[Dict[str, Any]]: Kullanıcı bilgileri listesi
        """
        try:
            # Veritabanından kullanıcıları farklı bir yolla çek
            cursor = self.db.conn.cursor()
            
            # Önce şema anlama
            cursor.execute("PRAGMA table_info(users)")
            columns = [col[1] for col in cursor.fetchall()]
            
            # Sorgu oluştur - mevcut sütunlara göre dinamik olarak oluştur
            id_column = "user_id" if "user_id" in columns else "id"
            
            # SQLite sorgusu - last_invited ve is_bot sütunlarını kontrol et
            query = f"""
            SELECT {id_column}, username, first_name 
            FROM users 
            """
            
            # is_bot sütunu varsa filtrele
            if "is_bot" in columns:
                query += "WHERE is_bot = 0 "
                
                # last_invited sütunu varsa ve is_bot varsa
                if "last_invited" in columns:
                    query += "AND (last_invited IS NULL OR last_invited < datetime('now', '-1 day')) "
            # Sadece last_invited sütunu varsa
            elif "last_invited" in columns:
                query += "WHERE (last_invited IS NULL OR last_invited < datetime('now', '-1 day')) "
            
            # Sıralama ve limit
            query += """
            ORDER BY RANDOM()
            LIMIT ?
            """
            
            cursor.execute(query, (limit,))
            rows = cursor.fetchall()
            
            # Format sonuçları
            result = []
            for row in rows:
                result.append({
                    "user_id": row[0],
                    "username": row[1] if len(row) > 1 else None,
                    "first_name": row[2] if len(row) > 2 else "Kullanıcı"
                })
                
            return result
            
        except Exception as e:
            logger.error(f"Fallback user query hatası: {str(e)}")
            return []
    
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
    
    #
    # ANA SERVİS METODLARI
    #
    
    async def run(self) -> None:
        """
        Ana servis döngüsü - belirli aralıklarla davet gönderir.
        
        Bu metot, servis durdurulana kadar çalışır ve belirli aralıklarla
        _process_invite_batch metodunu çağırarak kullanıcılara davet gönderir.
        """
        logger.info("Davet servisi çalışıyor...")
        
        try:
            while self.running and not self.stop_event.is_set():
                try:
                    # Sadece aktif ise davet gönder
                    if self.running:
                        # Gönderim zamanı geldiyse batch'i gönder
                        await self._process_invite_batch()
                        
                        # Başarı mesajı
                        logger.info(f"💌 Davet gönderim döngüsü tamamlandı. Toplam: {self.sent_count}")
                    
                    # Her batch arasında bekle
                    await asyncio.sleep(self.interval_minutes * 60)
                    
                except asyncio.CancelledError:
                    logger.info("Davet servisi görevi iptal edildi")
                    break
                except errors.FloodWaitError as e:
                    # FloodWait hatasında uzun süre bekle
                    logger.warning(f"⚠️ FloodWait hatası: {e.seconds} saniye bekleniyor (döngü)")
                    await asyncio.sleep(e.seconds + random.randint(10, 30))
                except Exception as e:
                    # Diğer hatalarda kısa bekle ve devam et
                    self.error_count += 1
                    logger.error(f"Davet döngüsü hatası ({self.error_count}): {str(e)}")
                    await asyncio.sleep(60)  # 1 dakika bekle ve tekrar dene
        
        except asyncio.CancelledError:
            logger.info("Davet servisi ana görevi iptal edildi")
        except Exception as e:
            logger.critical(f"Kritik davet servis hatası: {str(e)}", exc_info=True)
    
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
    
    async def _process_invite_batch(self) -> int:
        """
        Bir batch kullanıcıya davet gönderir.
        
        Veritabanından kullanıcıları alır, filtreleyerek her birine
        davet mesajı gönderir ve başarı/başarısızlık istatistikleri tutar.
        
        Returns:
            int: Başarıyla davet gönderilen kullanıcı sayısı
        """
        global GLOBAL_COOLDOWN_START, GLOBAL_COOLDOWN_DURATION
        
        # Eğer global cooldown aktifse bekle
        if GLOBAL_COOLDOWN_START and GLOBAL_COOLDOWN_DURATION:
            elapsed = (datetime.now() - GLOBAL_COOLDOWN_START).total_seconds()
            if elapsed < GLOBAL_COOLDOWN_DURATION:
                remaining = GLOBAL_COOLDOWN_DURATION - elapsed
                logger.warning(f"⚠️ Global cooldown aktif: {remaining:.0f} saniye kaldı")
                await asyncio.sleep(min(60, remaining))
                return 0
            else:
                # Cooldown süresi doldu
                GLOBAL_COOLDOWN_START = None
                GLOBAL_COOLDOWN_DURATION = None
                logger.info("Global cooldown süresi doldu, normal operasyona dönülüyor")

        try:
            # Kullanıcıları çek (dakika cinsinden cooldown)
            users = []
            if hasattr(self.db, 'get_users_for_invite'):
                users = self.db.get_users_for_invite(self.batch_size, self.cooldown_minutes)
            else:
                # Fallback - eğer dakika cinsinden metot yoksa
                users = self._get_fallback_users(self.batch_size)
            
            if not users:
                logger.info("Davet edilecek kullanıcı bulunamadı")
                return 0
                
            logger.info(f"🔄 {len(users)} kullanıcıya davet gönderilecek")
            
            successful = 0
            failed = 0
            
            for user in users:
                try:
                    # Durdurma kontrolü
                    if not self.running or self.stop_event.is_set():
                        logger.info("Davet işlemi durduruldu")
                        break
                    
                    # Dict formatında kullanıcı verisi kullan
                    user_id = user.get("user_id")
                    username = user.get("username")
                    first_name = user.get("first_name", "Kullanıcı")
                    
                    # Rate limiting - izin kontrol et
                    wait_time = self.rate_limiter.get_wait_time()
                    if wait_time > 0:
                        logger.info(f"⏱️ Rate limit nedeniyle {wait_time:.1f} saniye bekleniyor")
                        await asyncio.sleep(wait_time)
                        
                        # Tekrar kontrol et
                        if self.rate_limiter.get_wait_time() > 0:
                            logger.warning("Bekleme sonrası hala rate limit aktif, işlem iptal ediliyor")
                            break
                    
                    # Kullanıcı ID'si yoksa atla
                    if not user_id:
                        logger.warning("Kullanıcı ID'si bulunamadı, atlanıyor")
                        continue
                        
                    user_display = f"@{username}" if username else f"{first_name} ({user_id})"
                    
                    # Kullanıcıya DM göndermeyi dene
                    success = await self._send_invite_to_user(user_id, first_name)
                    
                    if success:
                        # Başarılı gönderim sonrası rate limiter güncellemesi
                        try:
                            if hasattr(self.rate_limiter, 'increase_rate'):
                                self.rate_limiter.increase_rate(1.05)  # Küçük artışlar
                            # Başarıyı logla
                            logger.info(f"✓ {user_display} kullanıcısına davet gönderildi")
                        except Exception as e:
                            logger.debug(f"Rate limiter güncelleme hatası (önemsiz): {str(e)}")
                        
                        successful += 1
                        
                        # Kullanıcıyı davet edildi olarak işaretle (metot yoksa koruma ekle)
                        if hasattr(self.db, 'mark_user_invited'):
                            self.db.mark_user_invited(user_id)
                        else:
                            logger.warning("Veritabanında 'mark_user_invited' metodu bulunamadı!")
                    else:
                        logger.warning(f"✗ {user_display} kullanıcısına davet gönderilemedi")
                        failed += 1
                    
                    # Rate limiter güncelleme
                    self.rate_limiter.mark_used()
                    
                    # Her davet arasında daha kısa bekle - rastgele süreler
                    await asyncio.sleep(max(0.5, 1.5 * random.random()))
                
                except (KeyError, TypeError) as e:
                    logger.warning(f"Kullanıcı veri formatı hatası: {str(e)} - {type(user)}")
                    continue
                except Exception as e:
                    logger.error(f"Kullanıcı işleme hatası: {str(e)}", exc_info=True)
                    failed += 1
                    continue
            
            # Sonuçları güncelle
            self.sent_count += successful
            self.last_invite_time = datetime.now()
            
            # Oran iyiyse rate limit'i artır
            if successful > 0 and failed == 0:
                if hasattr(self.rate_limiter, 'increase_rate'):
                    new_rate = self.rate_limiter.increase_rate(1.1)  # %10 arttır
                    logger.debug(f"Rate limit yükseltildi: {new_rate:.2f} mesaj/dk")
            
            logger.info(f"📊 Davet gönderimi tamamlandı: {successful} başarılı, {failed} başarısız")
            return successful
            
        except errors.FloodWaitError as e:
            # Global cooldown ayarla
            wait_seconds = e.seconds
            GLOBAL_COOLDOWN_START = datetime.now()
            GLOBAL_COOLDOWN_DURATION = max(wait_seconds * 3, 3600)  # En az 1 saat, normal olarak 3x bekle
            
            # Hız limitini düşür
            if hasattr(self.rate_limiter, 'reduce_rate'):
                new_rate = self.rate_limiter.reduce_rate(0.5)  # %50 azalt
                logger.warning(f"⚠️ Rate limit düşürüldü: {new_rate:.2f} mesaj/dk")
                
            logger.warning(f"⚠️ FloodWaitError - Global cooldown aktif: {GLOBAL_COOLDOWN_DURATION} saniye ({wait_seconds}s x 3)")
            return 0
        except Exception as e:
            logger.error(f"Davet batch işleme hatası: {str(e)}", exc_info=True)
            return 0
    
    async def _send_invite_to_user(self, user_id, first_name):
        """Belirli bir kullanıcıya davet mesajı gönderir"""
        try:
            # Kullanıcıya ulaşmayı dene
            user = await self.client.get_entity(user_id)
            if not user:
                return False
                
            # Random bir davet mesajı seç
            invite_template = random.choice(self.invite_templates)
            
            # Kişiselleştirilmiş mesaj
            personalized_message = invite_template.replace("{name}", first_name or "değerli kullanıcı")
            
            # Grup linklerini ekle
            group_links_text = ""
            if self.group_links:
                formatted_links = []
                for link in self.group_links:
                    # t.me/{} formatını doğru işle
                    formatted_link = link
                    if "{}" in link:
                        # Varsayılan grup adını veya grup ID'sini kullan
                        group_name = "grupumuz"  # Buraya gerçek bir grup adı alabilirsiniz
                        formatted_link = link.replace("{}", group_name)
                    formatted_links.append(formatted_link)
                    
                group_links_text = "\n\n" + "\n".join([f"• {link}" for link in formatted_links])
            
            # Mesajı gönder
            logger.debug(f"Davet mesajı gönderiliyor: {user_id} - Mesaj: {personalized_message + group_links_text}")
            await self.client.send_message(
                user,
                personalized_message + group_links_text,
                link_preview=False
            )
            
            # Davet edildiğini işaretle
            if hasattr(self.db, 'mark_user_invited'):
                self.db.mark_user_invited(user_id)
            
            # İstatistikleri güncelle
            self.invites_sent += 1
            self.last_activity = datetime.now()
            
            return True
            
        except errors.FloodWaitError as e:
            wait_time = e.seconds
            logger.warning(f"⚠️ FloodWaitError: {wait_time}s bekleniyor ({user_id})")
            await asyncio.sleep(wait_time)
            return False
        except Exception as e:
            logger.error(f"Kullanıcıya davet gönderme hatası ({user_id}): {str(e)}")
            return False
