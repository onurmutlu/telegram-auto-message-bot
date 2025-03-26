"""
Kullanıcı işlemlerini yöneten sınıf
"""
import asyncio
import random
import logging
from datetime import datetime
from typing import Optional
from colorama import Fore, Style

from telethon import errors

logger = logging.getLogger(__name__)

class UserHandler:
    """Kullanıcı işlemleri yöneticisi"""
    
    def __init__(self, bot):
        """Bot nesnesini alır"""
        self.bot = bot
        
        # Rate limiting için parametreler
        self.pm_delays = {
            'min_delay': 45,      # Min bekleme süresi (saniye) - daha sık gönderim
            'max_delay': 120,     # Max bekleme süresi (saniye)
            'burst_limit': 5,     # Art arda gönderim limiti - artırıldı
            'burst_delay': 300,   # Burst limit sonrası bekleme (5 dk) - azaltıldı
            'hourly_limit': 15    # Saatlik maksimum mesaj - artırıldı
        }
        
        # Rate limiting için durum takibi
        self.pm_state = {
            'burst_count': 0,
            'hourly_count': 0,
            'hour_start': datetime.now(),
            'last_pm_time': None,
            'consecutive_errors': 0
        }
    
    async def process_personal_invites(self):
        """Özel davetleri işler - daha sık çalışacak"""
        while self.bot.is_running:
            if not self.bot.is_paused:
                try:
                    # Kapatma sinyali kontrol et
                    if self.bot._shutdown_event.is_set():
                        break
                    
                    # Her 5 dakikada bir çalış (60 → 5 dakika'ya düşürdük)
                    # Küçük adımlarla bekle
                    for _ in range(30):  # 30 saniye bekle
                        if not self.bot.is_running or self.bot._shutdown_event.is_set():
                            break
                        await asyncio.sleep(1)
                    
                    # Kapatma sinyalini tekrar kontrol et
                    if not self.bot.is_running or self.bot._shutdown_event.is_set():
                        break
                    
                    # Davet edilecek kullanıcıları al
                    users_to_invite = self.bot.db.get_users_to_invite(limit=5)
                    if not users_to_invite:
                        logger.info("📪 Davet edilecek kullanıcı bulunamadı")
                        continue
                        
                    logger.info(f"📩 {len(users_to_invite)} kullanıcıya davet gönderiliyor...")
                    
                    # Her kullanıcıya davet gönder
                    for user_id, username in users_to_invite:
                        # Kapatma sinyali kontrol et
                        if not self.bot.is_running or self.bot._shutdown_event.is_set():
                            break
                            
                        # Rate limiting ve diğer kontrolleri yap
                        if self.pm_state['hourly_count'] >= self.pm_delays['hourly_limit']:
                            logger.warning("⚠️ Saatlik mesaj limiti doldu!")
                            break
                            
                        # Özel mesaj gönder
                        invite_message = self._create_invite_message()
                        if await self._send_personal_message(user_id, invite_message):
                            self.bot.db.mark_as_invited(user_id)
                            logger.info(f"✅ Davet gönderildi: {username or user_id}")
                        
                        # Davetler arasında bekle - bölünmüş bekleme
                        await self._interruptible_sleep(random.randint(30, 60))  # Daha kısa bekleme
                        
                except asyncio.CancelledError:
                    logger.info("Davet işleme görevi iptal edildi")
                    break
                except Exception as e:
                    error_key = f"invite_error_{str(e)[:20]}"
                    
                    # Tekrarlanan hataları filtreleme
                    if error_key not in self.bot.error_counter:
                        self.bot.error_counter[error_key] = 0
                    
                    self.bot.error_counter[error_key] += 1
                    
                    # İlk hata veya her 5 hatada bir göster
                    if self.bot.error_counter[error_key] == 1 or self.bot.error_counter[error_key] % 5 == 0:
                        logger.error(f"Özel davet hatası: {str(e)}")
                    
                    await self._interruptible_sleep(30)
            else:
                await asyncio.sleep(1)
    
    def _create_invite_message(self):
        """Davet mesajı oluşturur"""
        # Rastgele davet mesajı ve outro seç
        random_invite = random.choice(self.bot.invite_messages)
        outro = random.choice(self.bot.invite_outros)
        
        # Grup bağlantılarını oluştur
        group_links = "\n".join([f"• t.me/{link}" for link in self.bot.group_links])
        
        # Mesajı formatla
        return f"{random_invite.format(self.bot.group_links[0])}{outro}{group_links}"
    
    async def _send_personal_message(self, user_id: int, message: str) -> bool:
        """Kullanıcıya özel mesaj gönderir"""
        try:
            # Akıllı gecikme uygula
            await self._smart_delay()
            
            # Mesaj gönder
            await self.bot.client.send_message(user_id, message)
            
            # İstatistikleri güncelle
            self.pm_state['burst_count'] += 1
            self.pm_state['hourly_count'] += 1
            self.pm_state['consecutive_errors'] = 0
            self.pm_state['last_pm_time'] = datetime.now()
            
            return True
            
        except errors.FloodWaitError as e:
            # Tekrarlanan hataları önle
            error_key = f"pm_flood_{e.seconds}"
            if error_key not in self.bot.error_counter:
                self.bot.error_counter[error_key] = 0
                
            self.bot.error_counter[error_key] += 1
            
            # İlk hata veya her 5 hatada bir göster
            if self.bot.error_counter[error_key] == 1 or self.bot.error_counter[error_key] % 5 == 0:
                logger.warning(f"⚠️ Flood wait: {e.seconds} saniye bekleniyor")
                
            await asyncio.sleep(e.seconds)
            self.pm_state['consecutive_errors'] += 1
        except Exception as e:
            logger.error(f"Özel mesaj hatası: {str(e)}")
            self.pm_state['consecutive_errors'] += 1
            await asyncio.sleep(30)
            
        return False
    
    async def _smart_delay(self) -> None:
        """Gelişmiş akıllı gecikme sistemi"""
        try:
            current_time = datetime.now()
            
            # Saatlik limit sıfırlama
            if (current_time - self.pm_state['hour_start']).total_seconds() >= 3600:
                self.pm_state['hourly_count'] = 0
                self.pm_state['hour_start'] = current_time
            
            # Ardışık hata oranına göre gecikme artışı
            if self.pm_state['consecutive_errors'] > 0:
                # Her ardışık hata için gecikmeyi iki kat artır (exp backoff)
                error_delay = min(300, 5 * (2 ** self.pm_state['consecutive_errors']))
                logger.info(f"⚠️ {self.pm_state['consecutive_errors']} ardışık hata nedeniyle {error_delay} saniye ek bekleme")
                await asyncio.sleep(error_delay)
            
            # Burst kontrolü
            if self.pm_state['burst_count'] >= self.pm_delays['burst_limit']:
                logger.info(f"⏳ Art arda gönderim limiti aşıldı: {self.pm_delays['burst_delay']} saniye bekleniyor")
                await asyncio.sleep(self.pm_delays['burst_delay'])
                self.pm_state['burst_count'] = 0
            
            # Son mesajdan bu yana geçen süre
            if self.pm_state['last_pm_time']:
                time_since_last = (current_time - self.pm_state['last_pm_time']).total_seconds()
                min_delay = self.pm_delays['min_delay']
                
                # Henüz minimum süre geçmemişse bekle
                if time_since_last < min_delay:
                    wait_time = min_delay - time_since_last
                    await asyncio.sleep(wait_time)
            
            # Doğal görünmesi için rastgele gecikme
            human_delay = random.randint(3, 8)  # Azaltıldı
            await asyncio.sleep(human_delay)
            
        except Exception as e:
            logger.error(f"Akıllı gecikme hesaplama hatası: {str(e)}")
            await asyncio.sleep(60)
    
    async def _invite_user(self, user_id: int, username: Optional[str]) -> bool:
        """Kullanıcıya özel davet mesajı gönderir"""
        try:
            # Kullanıcı bilgisini log
            user_info = f"@{username}" if username else f"ID:{user_id}"
            
            # Daha önce davet edilmiş mi?
            if self.bot.db.is_invited(user_id) or self.bot.db.was_recently_invited(user_id, 4):
                print(self.bot.terminal_format['user_already_invited'].format(user_info))
                logger.debug(f"Zaten davet edilmiş kullanıcı atlandı: {user_info}")
                return False
            
            # Davet mesajını oluştur ve gönder
            message = self._create_invite_message()
            await self.bot.client.send_message(user_id, message)
            
            # Veritabanını güncelle
            self.bot.db.update_last_invited(user_id)
            
            # Başarılı işlem logu
            logger.info(f"Davet başarıyla gönderildi: {user_info}")
            
            # Konsol çıktısı
            print(self.bot.terminal_format['user_invite_success'].format(user_info))
            
            return True
            
        except errors.FloodWaitError as e:
            # Tekrarlanan hataları önle
            error_key = f"invite_flood_{user_id}"
            if error_key not in self.bot.error_counter:
                self.bot.error_counter[error_key] = 0
                
            self.bot.error_counter[error_key] += 1
            
            # İlk hata veya her 5 hatada bir göster
            if self.bot.error_counter[error_key] == 1 or self.bot.error_counter[error_key] % 5 == 0:
                print(self.bot.terminal_format['user_invite_fail'].format(user_info, f"FloodWait: {e.seconds}s"))
            
            await asyncio.sleep(e.seconds)
            return False
            
        except (errors.UserIsBlockedError, errors.UserIdInvalidError, errors.PeerIdInvalidError) as e:
            # Konsol çıktısı
            print(self.bot.terminal_format['user_invite_fail'].format(user_info, f"Kalıcı hata: {e.__class__.__name__}"))
            
            # Kullanıcıyı veritabanında işaretle
            self.bot.db.mark_user_blocked(user_id)
            return False
            
        except Exception as e:
            # Diğer hatalar
            print(self.bot.terminal_format['user_invite_fail'].format(user_info, f"Hata: {e.__class__.__name__}"))
            await asyncio.sleep(30)
            return False
    
    async def _interruptible_sleep(self, seconds):
        """Kesintiye uğrayabilen bekleme"""
        step = 0.5  # Daha sık kontroller
        for _ in range(int(seconds / step)):
            if not self.bot.is_running or self.bot._shutdown_event.is_set():
                break
            await asyncio.sleep(step)