"""
# ============================================================================ #
# Dosya: dm_service.py
# Yol: /Users/siyahkare/code/telegram-bot/bot/services/dm_service.py
# İşlev: Telegram bot için direkt mesaj (DM) ve davet servisi.
#
# Amaç: Botun özel mesajları işlemesini ve kullanıcılara grup davetleri göndermesini sağlar.
#
# Özellikler:
# - Gelen özel mesajları dinleme
# - Kullanıcılara otomatik davet mesajları gönderme
# - Hız sınırlama (rate limiting) uygulama
# - Çevre değişkenlerinden grup linklerini alma
# - Hata yönetimi ve loglama
#
# Build: 2025-04-01-00:07:55
# Versiyon: v3.4.0
# ============================================================================ #
#
# Bu modül, Telegram botunun özel mesajları işlemesini ve kullanıcılara
# grup davetleri göndermesini sağlar. Temel özellikleri:
# - Gelen özel mesajları dinleme
# - Kullanıcılara otomatik davet mesajları gönderme
# - Rate limiting (hız sınırlama) uygulama
# - Çevre değişkenlerinden grup linklerini alma
# - Hata yönetimi ve loglama
#
# ============================================================================ #
"""
import os
import sys
import json
from colorama import Fore, Style, init

# Initialize colorama
init(autoreset=True)
import logging
import random
import asyncio
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set, Tuple

from telethon import TelegramClient, events
# Hata importlarını düzeltin
from telethon.errors import (
    FloodWaitError, 
    UserNotMutualContactError, 
    UserPrivacyRestrictedError
)
# Tüm hatalar için errors modülünü ayrıca import edin
import telethon.errors as errors

from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.tl.functions.channels import JoinChannelRequest

# Rate limiter'ı doğrudan import et
from ..utils.rate_limiter import AdaptiveRateLimiter

logger = logging.getLogger(__name__)

class GroupHandler:
    def __init__(self, bot):
        self.bot = bot
        self.admin_groups = bot.config.admin_groups
        self.target_groups = bot.config.target_groups

class DirectMessageService:
    """
    Direkt mesaj servisi.
    Bu sınıf, botun direkt mesajlar aracılığıyla kullanıcılara
    grup davetleri göndermesini sağlar. Temel özellikleri:
    - Gelen özel mesajları dinleme
    - Kullanıcılara otomatik davet mesajları gönderme
    - Rate limiting (hız sınırlama) uygulama
    - Çevre değişkenlerinden grup linklerini alma
    - Hata yönetimi ve loglama

    ============================================================================ #
    """
    def __init__(self, client, config, db, stop_event=None):
        """
        DirectMessageService sınıfının başlatıcı metodu.
        """
        self.client = client
        self.config = config
        self.db = db
        self.stop_event = stop_event if stop_event else threading.Event()
        self.logger = logger  # Global logger'ı sınıf özelliği yap
        self.running = True
        self.responded_users = set()
        self.invites_sent = 0
        self.last_activity = datetime.now()
        self.super_users = [s.strip() for s in os.getenv("SUPER_USERS", "").split(',') if s.strip()]
        
        # Adaptive rate limiter
        from ..utils.rate_limiter import AdaptiveRateLimiter
        self.rate_limiter = AdaptiveRateLimiter(initial_rate=5, initial_period=60)
        
        # Mesaj şablonları
        self.flirty_messages = self.config.flirty_messages  # Doğrudan config'den al
        self.invite_templates = self.config.invite_templates
        self.response_templates = self.config.response_templates  # Eksik olan özellik eklendi
        
        # Grup linkleri
        self.group_links = [link.strip() for link in os.getenv("GROUP_LINKS", "").split(',') if link.strip()]
        logger.info(f"Yüklenen grup linkleri: {len(self.group_links)} adet")
        
        # Hata grupları
        self.error_groups = set()
        
        # Debug
        self.debug = os.getenv("DEBUG", False)
        
        logger.info("DM servisi başlatıldı")

        # Grup linklerini yükle ve log'la
        self.group_links = self._parse_group_links()
        logger.info(f"Yüklenen grup linkleri: {len(self.group_links)} adet")
        for idx, link in enumerate(self.group_links):
            logger.debug(f"Link {idx+1}: {link}")

    def get_status(self):
        """
        Servisin durumunu döndürür.
        """
        return {
            'running': self.running,
            'processed_dms': self.processed_dms,
            'invites_sent': self.invites_sent,
            'last_activity': self.last_activity.strftime("%Y-%m-%d %H:%M:%S")
        }

    def _parse_group_links(self):
        """Grup bağlantılarını çevre değişkenlerinden veya yapılandırmadan ayrıştırır."""
        import os
        
        # Önce GROUP_LINKS çevre değişkenini kontrol et
        env_links = os.environ.get("GROUP_LINKS", "")
        
        # ADMIN_GROUPS değişkenini de kontrol et (bu durumda asıl linkler burada)
        admin_links = os.environ.get("ADMIN_GROUPS", "")
        
        logger.debug(f"Çevre değişkeninden okunan GROUP_LINKS: '{env_links}'")
        logger.debug(f"Çevre değişkeninden okunan ADMIN_GROUPS: '{admin_links}'")
        
        # Önce GROUP_LINKS'i dene, boşsa ADMIN_GROUPS'u kullan
        links_str = env_links if env_links else admin_links
        
        if links_str:
            # Virgülle ayrılmış bağlantıları ayır ve boşlukları temizle
            links = [link.strip() for link in links_str.split(",") if link.strip()]
            logger.debug(f"Çevre değişkenlerinden {len(links)} link bulundu")
            return links
        
        # Çevre değişkenleri yoksa, yapılandırmadaki bağlantıları kullan
        if hasattr(self.config, 'GROUP_LINKS') and self.config.GROUP_LINKS:
            logger.debug(f"config.GROUP_LINKS'ten {len(self.config.GROUP_LINKS)} link bulundu")
            return self.config.GROUP_LINKS
        elif hasattr(self.config, 'ADMIN_GROUPS') and self.config.ADMIN_GROUPS:  # ADMIN_GROUPS'u da kontrol et
            logger.debug(f"config.ADMIN_GROUPS'tan {len(self.config.ADMIN_GROUPS)} link bulundu")
            return self.config.ADMIN_GROUPS
        
        logger.warning("⚠️ Hiçbir yerde grup linki bulunamadı!")
        
        # Varsayılan örnek linkler
        default_links = [
            "https://t.me/omegleme",
            "https://t.me/sosyalcip",
            "https://t.me/sohbet"
        ]
        logger.info(f"Varsayılan {len(default_links)} link kullanılıyor")
        return default_links

    def _choose_invite_template(self):
        """
        Rastgele bir davet şablonu seçer.
        
        Returns:
            str: Seçilen davet şablonu
        """
        if not self.invite_templates:
            return "Merhaba! Grubumuza katılmak ister misin?"  # Varsayılan şablon
        
        # Eğer invite_templates bir dict ise
        if isinstance(self.invite_templates, dict):
            return random.choice(list(self.invite_templates.values()))
        
        # Eğer invite_templates bir liste ise
        return random.choice(self.invite_templates)

    def _choose_flirty_message(self):
        """
        Rastgele bir flirty mesaj seçer.
        
        Returns:
            str: Seçilen flirty mesaj
        """
        if not self.flirty_messages:
            return "Selam! Nasılsın?"  # Varsayılan mesaj
        
        return random.choice(self.flirty_messages)

    async def _send_invite(self, message):
        """Kullanıcıya davet mesajı gönderir."""
        # Geçerlilik kontrolü
        if not message or not hasattr(message, 'sender_id') or message.sender_id is None:
            self.logger.warning("Geçersiz mesaj: sender_id bulunamadı")
            return
        
        try:
            # Debug için grupları logla
            links = self._parse_group_links()
            logger.debug(f"Ham grup linkleri: {links}")
            
            # Formatlı grup linklerini al
            formatted_links = self._get_formatted_group_links()
            logger.debug(f"Formatlı grup linkleri: {formatted_links}")
            
            # Hız sınırlaması kontrolü
            if not self.rate_limiter.is_allowed():
                logger.warning("Hız sınırlamasına takıldı, davet gönderilemedi")
                return

            # Davet mesajını oluştur
            invite_message = self._choose_invite_template()
            
            # Grup linkleri metin bloğu
            group_links_str = ""

            if len(formatted_links) == 1:
                # Tek grup varsa, sadece onu ekle
                group_links_str = f"\n\n{formatted_links[0]}"
            elif len(formatted_links) > 1:
                # Birden fazla grup varsa, listele
                group_links_str = "\n\nGruplarımız:\n"
                group_links_str += "\n".join([f"• {link}" for link in formatted_links])

            # Süper kullanıcıları ekle
            super_users_str = ""
            if self.super_users and any(self.super_users):  # Liste boş değilse ve içinde boş olmayan elemanlar varsa
                super_users_str = "\n\nADMIN onaylı arkadaşlarıma menü için yazabilirsin:\n"
                super_users_formatted = []
                for user in self.super_users:
                    if user and user.strip():  # Kullanıcı adı boş değilse
                        # @ işareti ekle (eğer yoksa)
                        user_name = user.strip()
                        if not user_name.startswith('@'):
                            user_name = f"@{user_name}"
                        super_users_formatted.append(f"• {user_name}")
                
                if super_users_formatted:
                    super_users_str += "\n".join(super_users_formatted)
                else:
                    super_users_str = ""  # Hiç geçerli süper kullanıcı yoksa boş bırak

            full_message = f"{invite_message}{group_links_str}{super_users_str}"

            # Mesajı gönder
            await message.reply(full_message)
            self.invites_sent += 1
            self.last_activity = datetime.now()
            logger.info(f"Davet gönderildi: {message.sender_id}")

            # Hız sınırlamasını uygula
            self.rate_limiter.mark_used()

        except errors.FloodWaitError as e:
            logger.warning(f"FloodWaitError: {e.seconds} saniye bekleniyor")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            logger.error(f"Davet gönderme hatası: {str(e)}")

    async def run(self):
        """
        Servisi başlatır ve gelen direkt mesajları dinler.
        """
        # Önce kendi ID'mizi al
        me = await self.client.get_me()
        my_id = me.id
        logger.info(f"Bot ID: {my_id}")
        
        @self.client.on(events.NewMessage(incoming=True))
        async def handler(event):
            """Yeni gelen direkt mesajları işler."""
            # Güvenlik kontrolleri
            if not event:
                return
                
            # Sadece özel mesajları işle, grup mesajlarını loglama
            if not event.is_private:
                return
                
            # Bundan sonraki güvenlik kontrolleri...
            if not hasattr(event, 'message') or not event.message:
                logger.warning("Event'in mesaj özelliği yok!")
                return
                
            if not hasattr(event, 'sender_id') or event.sender_id is None:
                try:
                    # Sender_id olmadığında mesaj içinden almayı dene
                    sender = await event.get_sender()
                    if sender and hasattr(sender, 'id'):
                        sender_id = sender.id
                    else:
                        logger.warning("Gönderen bulunamadı")
                        return
                except Exception as e:
                    logger.error(f"Göndereni alırken hata: {str(e)}")
                    return
            else:
                sender_id = event.sender_id

            if not self.running:
                return
            
            # None kontrolü ekle
            if not event or not hasattr(event, 'sender_id') or event.sender_id is None:
                logger.warning("Hatalı mesaj alındı: sender_id bulunamadı")
                return
                
            # Mesajın DM olup olmadığını kontrol et
            # Grup mesajlarını değil, sadece özel mesajları işle
            is_private = event.is_private
            if not is_private:
                return
                
            # Kendi mesajlarını yanıtlama
            if event.sender_id == my_id:
                return
                
            # Debug için log
            logger.info(f"🔔 DM alındı - Kullanıcı: {event.sender_id}")
            
            # Mesajı işlemeye başla
            self.processed_dms += 1
            self.last_activity = datetime.now()

            try:
                # Daha önce yanıt verilmiş kullanıcıları kontrol et
                if event.sender_id in self.responded_users:
                    logger.debug(f"Bu kullanıcıya ({event.sender_id}) daha önce yanıt verilmiş")
                    return
                    
                # Kullanıcıyı yanıtlananlar listesine ekle
                self.responded_users.add(event.sender_id)
                    
                # Hız sınırlaması kontrolü
                if not self.rate_limiter.is_allowed():
                    logger.warning("⚠️ Hız sınırlaması - DM yanıtı geciktirildi")
                
                # İkinci yanıt için hız sınırlaması kontrolü
                if not self.rate_limiter.is_allowed():
                    logger.warning("⚠️ Davet gönderme sınırlandı - 60 saniye bekleniyor")
                    await asyncio.sleep(60)
                
                logger.info(f"📨 Davet mesajı gönderiliyor: {event.sender_id}")
                await self._send_invite(event)
                
                # Veritabanına ekle
                user = await event.get_sender()
                if user and hasattr(self.db, 'add_or_update_user'):
                    user_data = {
                        'user_id': user.id,
                        'username': user.username,
                        'first_name': user.first_name,
                        'last_name': user.last_name
                    }
                    self.db.add_or_update_user(user_data)

            except errors.FloodWaitError as e:
                logger.warning(f"⏱️ FloodWaitError: {e.seconds} saniye bekleniyor")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                logger.error(f"❌ Direkt mesaj işleme hatası: {str(e)}")

        logger.info("✅ Direkt Mesaj Servisi çalışıyor - DM'leri dinliyor...")
        
        # Servisin ana döngüsü
        while self.running:
            if self.stop_event and self.stop_event.is_set():
                self.running = False
                logger.info("⛔ Durdurma sinyali alındı, servis durduruluyor...")
                break
            await asyncio.sleep(1)

    async def process_dm_users(self):
        """Direkt mesaj işleme döngüsü."""
        logger.info("DM işleme servisi başlatıldı")
        
        # Rate limiter ayarlarını güncelleyin - daha düşük başlangıç hızı
        self.rate_limiter = AdaptiveRateLimiter(
            initial_rate=2,      # Dakikada sadece 2 mesaj
            initial_period=60,   # 60 saniye periyot
            error_backoff=2.0,   # Hata durumunda hızı yarıya düşür
            max_jitter=3.0       # Rastgele 0-3 saniye ekleme
        )
        
        # Ana döngü
        while not self.stop_event.is_set():
            try:
                # Çalışma durumunu kontrol et
                if not self.running:
                    await asyncio.sleep(5)
                    continue
                    
                logger.info(f"🔄 DM işleme döngüsü başladı (Toplam: {self.invites_sent})")
                
                # Kullanıcıları toplu halde işle - her seferde daha az kullanıcı
                sent_count = await self._process_user_batch(limit=3)  # 5 yerine 3 kullanıcı
                
                # Son aktiviteyi güncelle
                self.last_activity = datetime.now()
                
                # Bir sonraki döngüye kadar bekle - daha uzun süre
                wait_seconds = 10 * 60  # 10 dakika (5 dakika yerine)
                self.logger.debug(f"⏳ {wait_seconds // 60} dakika sonra tekrar çalışacak")
                await asyncio.sleep(wait_seconds)
                
            except Exception as e:
                self.logger.error(f"DM işleme hatası: {str(e)}", exc_info=True)
                # Hatadan sonra biraz bekle
                await asyncio.sleep(120)  # Daha uzun bekleme

    async def _process_user_batch(self, limit=5):
        """
        Belirtilen limit kadar kullanıcıya DM gönderir.
        
        Args:
            limit: Bir seferde işlenecek maksimum kullanıcı sayısı
            
        Returns:
            int: Davet gönderilen kullanıcı sayısı
        """
        from colorama import Fore, Style
        sent_count = 0
        try:
            # Veritabanından davet edilecek kullanıcıları al
            if not hasattr(self.db, 'get_users_to_invite'):
                logger.error("Veritabanı nesnesinde get_users_to_invite metodu bulunamadı!")
                return 0
                
            # Senkron metodu await etmeyelim
            users_to_invite = self.db.get_users_to_invite(limit=limit, min_hours_between_invites=48, max_invites=5)
            
            if not users_to_invite:
                logger.debug("Davet edilecek kullanıcı bulunamadı.")
                return 0
                
            logger.info(f"{len(users_to_invite)} kullanıcıya davet gönderilecek")
            
            for user_id, username in users_to_invite:
                # Kullanıcıya daha önce mesaj gönderildi mi kontrol et
                if user_id in self.responded_users:
                    logger.debug(f"Bu kullanıcıya ({user_id}) daha önce yanıt verildi, geçiliyor")
                    continue
                    
                # Hız sınırlaması kontrolü
                if not self.rate_limiter.is_allowed():
                    wait_time = self.rate_limiter.get_wait_time()
                    logger.warning(f"Hız sınırlaması nedeniyle {wait_time:.2f} saniye bekleniyor")
                    print(f"{Fore.YELLOW}⏱️ Hız sınırı - {wait_time:.2f} saniye bekleniyor{Style.RESET_ALL}")
                    await asyncio.sleep(wait_time)
                
                try:
                    # Kullanıcı varlığını doğrula
                    user = None
                    try:
                        if username:
                            user = await self.client.get_entity(username)
                        else:
                            user = await self.client.get_entity(int(user_id))  # user_id'nin int olduğundan emin ol
                    except Exception as e:
                        logger.warning(f"Kullanıcı bulunamadı: {user_id} / @{username} - {str(e)}")
                        continue
                    
                    # RateLimiter ile kontrol edilmiş, güvenli bekleme süresi
                    wait_before_message = random.randint(5, 15)  # Daha uzun bekle
                    logger.debug(f"İlk mesaj öncesi {wait_before_message}s bekleniyor...")
                    await asyncio.sleep(wait_before_message)
                    
                    try:
                        # Önce flirty mesaj gönder
                        flirty_message = self._choose_flirty_message()
                        await self.client.send_message(user, flirty_message)
                        self.rate_limiter.mark_used()
                        
                        # Daha uzun bekle (5-10 saniye)
                        wait_between = random.randint(8, 15)
                        logger.debug(f"Mesajlar arası {wait_between}s bekleniyor...")
                        await asyncio.sleep(wait_between)
                        
                        # Ardından davet mesajı gönder
                        invite_message = self._choose_invite_template()
                        
                        # Grup linkleri
                        formatted_links = self._get_formatted_group_links()
                        group_links_str = "\n\nGruplarımız:\n"
                        group_links_str += "\n".join([f"• {link}" for link in formatted_links])
                        
                        # Süper kullanıcılar
                        super_users_str = ""
                        if self.super_users:
                            super_users_str = "\n\nADMIN onaylı arkadaşlarıma menü için yazabilirsin:\n"
                            super_users_str += "\n".join([f"• @{user}" for user in self.super_users if user])
                        
                        # Tam davet mesajı
                        full_message = f"{invite_message}{group_links_str}{super_users_str}"
                        
                        # Davet gönder
                        await self.client.send_message(user, full_message)
                        self.rate_limiter.mark_used()
                        
                        # Kullanıcıyı davet edildi olarak işaretle
                        if hasattr(self.db, 'mark_user_invited'):
                            self.db.mark_user_invited(user_id)
                            
                        # İstatistik güncelle
                        self.responded_users.add(user_id)
                        self.invites_sent += 1
                        sent_count += 1
                        
                        logger.info(f"✅ Davet gönderildi: {username or user_id}")
                        print(f"{Fore.GREEN}✅ Davet gönderildi: {username or user_id}{Style.RESET_ALL}")
                        
                        # Her kullanıcı arasında bekle (daha uzun)
                        batch_wait = random.randint(15, 25)
                        logger.debug(f"Kullanıcılar arası {batch_wait}s bekleniyor...")
                        await asyncio.sleep(batch_wait)
                    
                    except errors.FloodWaitError as e:
                        wait_time = e.seconds
                        logger.warning(f"⚠️ FloodWaitError: {wait_time} saniye bekleniyor")
                        print(f"{Fore.RED}⚠️ FloodWaitError: {wait_time} saniye bekleniyor{Style.RESET_ALL}")
                        self.rate_limiter.register_error(e)  # Hata kaydet
                        await asyncio.sleep(wait_time)
                        break
                    
                    except Exception as e:
                        error_msg = str(e)
                        logger.error(f"Kullanıcıya davet gönderirken hata: {user_id} - {error_msg}")
                        print(f"{Fore.RED}❌ Kullanıcıya davet gönderilirken hata: {user_id} - {error_msg}{Style.RESET_ALL}")
                        
                        if "Too many requests" in error_msg:
                            # Too many requests hatası - özel işle
                            self.rate_limiter.register_error(e)
                            wait_time = random.randint(180, 300)  # 3-5 dakika bekle
                            logger.warning(f"Too many requests hatası: {wait_time} saniye bekleniyor")
                            print(f"{Fore.RED}⚠️ Too many requests hatası - {wait_time} saniye bekleniyor{Style.RESET_ALL}")
                            await asyncio.sleep(wait_time)
                            break  # Bu batch'i sonlandır
                        else:
                            # Diğer hatalar için bekleme süresi ekle
                            await asyncio.sleep(5)
                            continue
                            
                except Exception as user_error:
                    logger.error(f"Kullanıcı işleme hatası: {user_id} - {str(user_error)}")
                    await asyncio.sleep(3)
        
        except Exception as e:
            logger.error(f"Kullanıcı toplu işleme hatası: {str(e)}")
            print(f"{Fore.RED}❌ Kullanıcı toplu işleme hatası: {str(e)}{Style.RESET_ALL}")
            
        return sent_count

    async def collect_group_members(self):
        """Grup üyelerini toplayıp veritabanına kaydeder."""
        print(f"{Fore.CYAN}╔══════════════════════════════════════════════════╗{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║               GRUP ÜYELERİ TOPLAMA               ║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}╚══════════════════════════════════════════════════╝{Style.RESET_ALL}")
        
        logger.info("🔍 Grup üyeleri toplanıyor...")
        
        try:
            # Tekrarları önlemek için set kullan
            target_groups_set = set()
            
            # Önce çevre değişkeninden dene
            env_targets = os.environ.get("TARGET_GROUPS", "")
            if env_targets:
                for g in env_targets.split(','):
                    if g and g.strip():
                        target_groups_set.add(g.strip())
            
            # Config'den dene
            if hasattr(self.config, 'TARGET_GROUPS') and self.config.TARGET_GROUPS:
                for g in self.config.TARGET_GROUPS:
                    if g and g.strip():
                        target_groups_set.add(g.strip())
                
            # Admin gruplarını da ekle
            admin_groups = os.environ.get("ADMIN_GROUPS", "")
            if admin_groups:
                for g in admin_groups.split(','):
                    if g and g.strip():
                        target_groups_set.add(g.strip())
            
            # Set'i listeye çevir
            target_groups = list(target_groups_set)
            
            if not target_groups:
                logger.warning("⚠️ Hiç hedef grup bulunamadı! TARGET_GROUPS çevre değişkenini kontrol edin.")
                return 0
            
            # Renkli tablo başlığı
            print(f"\n{Fore.YELLOW}┌─{'─' * 50}┐{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}│ {'HEDEF GRUPLAR':^48} │{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}├─{'─' * 50}┤{Style.RESET_ALL}")
            
            # Hedef grupları listele
            for i, group in enumerate(target_groups):
                print(f"{Fore.YELLOW}│ {i+1:2}. {group:<42} │{Style.RESET_ALL}")
            
            print(f"{Fore.YELLOW}└─{'─' * 50}┘{Style.RESET_ALL}")
            
            total_members = 0
            successful_groups = 0
            
            # İlerleme çubuğu başlangıcı
            group_count = len(target_groups)
            print(f"\n{Fore.CYAN}[ÜYE TOPLAMA İLERLEMESİ]{Style.RESET_ALL}")
            
            for idx, group_id in enumerate(target_groups):
                try:
                    # Grubu getir
                    try:
                        group = await self.client.get_entity(group_id)
                        print(f"{Fore.GREEN}✓ {group.title}{Style.RESET_ALL}")
                    except ValueError:
                        print(f"{Fore.RED}✗ Grup bulunamadı: {group_id}{Style.RESET_ALL}")
                        continue
                    
                    # İlerleme göster
                    progress = int((idx + 1) / group_count * 30)
                    print(f"\r{Fore.CYAN}[{'█' * progress}{' ' * (30-progress)}] {(idx+1)/group_count*100:.1f}%{Style.RESET_ALL}", end="")
                    
                    # Grup istatistiklerini veritabanında kaydet/güncelle
                    if hasattr(self.db, 'update_group_stats'):
                        self.db.update_group_stats(group.id, group.title)
                    
                    # !! DÜZELTME: get_participants() doğru şekilde kullan !!
                    try:
                        # Toplu işlem yaklaşımı
                        # await kullanarak tüm üyeleri bir kerede getir
                        all_members = await self.client.get_participants(group)
                        
                        print(f"\n{Fore.GREEN}► '{group.title}' grubundan {len(all_members)} üye bulundu{Style.RESET_ALL}")
                        
                        # Üyeleri veritabanına ekle - toplu işlem
                        batch_size = 50
                        batch_count = (len(all_members) + batch_size - 1) // batch_size
                        
                        for i in range(0, len(all_members), batch_size):
                            batch = all_members[i:i+batch_size]
                            batch_members_added = 0
                            
                            for member in batch:
                                if member.bot or member.deleted:
                                    continue  # Botları ve silinmiş hesapları atla
                                    
                                if hasattr(self.db, 'add_or_update_user'):
                                    # Kaynak grup bilgisini de ekle
                                    user_data = {
                                        'user_id': member.id,
                                        'username': member.username,
                                        'first_name': member.first_name,
                                        'last_name': member.last_name,
                                        'source_group': str(group.title)
                                    }
                                    self.db.add_or_update_user(user_data)
                                    total_members += 1
                                    batch_members_added += 1
                            
                            # İlerleme göster
                            batch_progress = (i + len(batch)) / len(all_members)
                            batch_bar = int(batch_progress * 20)
                            current_batch = i // batch_size + 1
                            print(f"\r  Batch {current_batch}/{batch_count}: [{'█' * batch_bar}{' ' * (20-batch_bar)}] {batch_members_added} üye ekendi", end="")
                            
                            # Her batch sonrası biraz bekle
                            await asyncio.sleep(1)
                        
                        print()  # Yeni satır
                        successful_groups += 1
                        
                    except errors.FloodWaitError as e:
                        wait_time = e.seconds
                        logger.warning(f"⏳ FloodWaitError: {wait_time} saniye bekleniyor")
                        print(f"\n{Fore.RED}⚠️ Hız sınırı aşıldı - {wait_time} saniye bekleniyor{Style.RESET_ALL}")
                        await asyncio.sleep(wait_time)
                        
                    except Exception as e:
                        logger.error(f"Grup üyelerini getirme hatası: {group.title} - {str(e)}")
                        print(f"\n{Fore.RED}✗ Üye toplama hatası: {group.title} - {str(e)}{Style.RESET_ALL}")
                    
                    # Her grup arasında bekle
                    await asyncio.sleep(10)
                    
                except Exception as e:
                    logger.error(f"Grup işleme hatası: {group_id} - {str(e)}")
                    print(f"\n{Fore.RED}✗ Genel hata: {group_id} - {str(e)}{Style.RESET_ALL}")
                    continue
            
            # Özet tablosu
            print(f"\n{Fore.CYAN}╔══════════════════════════════════════════════════╗{Style.RESET_ALL}")
            print(f"{Fore.CYAN}║                   TOPLAMA ÖZETI                  ║{Style.RESET_ALL}")
            print(f"{Fore.CYAN}╠══════════════════════════════════════════════════╣{Style.RESET_ALL}")
            print(f"{Fore.CYAN}║ Taranan Gruplar: {successful_groups:3}/{len(target_groups):<3}                         ║{Style.RESET_ALL}")
            print(f"{Fore.CYAN}║ Toplanan Üyeler: {total_members:<6}                         ║{Style.RESET_ALL}")
            print(f"{Fore.CYAN}╚══════════════════════════════════════════════════╝{Style.RESET_ALL}")
            
            logger.info(f"📊 Toplam {total_members} üye veritabanına eklendi/güncellendi")
            return total_members
            
        except Exception as e:
            logger.error(f"Üye toplama hatası: {str(e)}")
            print(f"{Fore.RED}✗✗✗ Üye toplama sürecinde kritik hata: {str(e)}{Style.RESET_ALL}")
            return 0

    def _get_formatted_group_links(self):
        """
        Grup linklerini isimlerle birlikte formatlayan ve tıklanabilir bağlantılar oluşturan metot.
        """
        links = self._parse_group_links()
        if not links:
            logger.warning("Formatlanacak grup linki bulunamadı!")
            return []
            
        formatted_links = []
        
        for link in links:
            if not link or not isinstance(link, str):
                continue
                
            # Link temizleme
            clean_link = link.strip()
            
            # İsim belirleme
            display_name = None
            
            # Anahtar kelimelere göre isim belirleme
            if "omegle" in clean_link.lower():
                display_name = "Omegle Sohbet"
            elif "sosyal" in clean_link.lower():
                display_name = "Sosyal Muhabbet"
            elif "sohbet" in clean_link.lower() and "ask" not in clean_link.lower():
                display_name = "Arkadaşlık Grubu"
            elif "ask" in clean_link.lower() or "aşk" in clean_link.lower():
                display_name = "Aşkım Sohbet"
            elif "duygu" in clean_link.lower():
                display_name = "Duygusal Sohbet"
            else:
                # İsim bulunamadıysa, linkten çıkarmaya çalış
                if "t.me/" in clean_link:
                    display_name = clean_link.split("t.me/")[1].capitalize()
                elif "@" in clean_link:
                    display_name = clean_link.replace("@", "").capitalize()
                else:
                    display_name = "Telegram Grubu"
                    
            # Link formatını düzelt - tıklanabilir hale getir
            formatted_link = clean_link
            
            # Eğer link t.me formatında değilse ve @ içermiyorsa, @ ekle
            if "t.me/" not in clean_link and not clean_link.startswith("@"):
                # Sadece grup adı verilmişse @ işareti ekle
                formatted_link = f"@{clean_link}"
                
            # Sonuç formatlı linki ekle
            formatted_links.append(f"{display_name}: {formatted_link}")
                
        return formatted_links

    def debug_links(self):
        """Grup linklerini debug amaçlı gösterir."""
        print("\n===== DM SERVİSİ BAĞLANTI KONTROLÜ =====")
        
        # Çevre değişkenlerinden alınan linkler
        links = self._parse_group_links()
        print(f"\nHam grup linkleri ({len(links)}):")
        for i, link in enumerate(links):
            print(f"  {i+1}. {link}")
        
        # Formatlı linkler
        formatted_links = self._get_formatted_group_links()
        print(f"\nFormatlı grup linkleri ({len(formatted_links)}):")
        for i, link in enumerate(formatted_links):
            print(f"  {i+1}. {link}")
        
        # Örnek tam mesaj
        print("\nÖrnek davet mesajı:")
        invite_template = self._choose_invite_template()
        
        group_links_str = "\n\nGruplarımız:\n"
        group_links_str += "\n".join([f"• {link}" for link in formatted_links])
        
        super_users_str = ""
        if self.super_users:
            super_users_str = "\n\nADMIN onaylı arkadaşlarım:\n"
            super_users_str += "\n".join([f"• @{user}" for user in self.super_users if user])
        
        full_message = f"{invite_template}{group_links_str}{super_users_str}"
        print(f"\n{full_message}\n")
        print("=======================================")