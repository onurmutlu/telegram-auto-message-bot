"""
Grup işlemlerini yöneten sınıf
"""
import asyncio
import random
import logging
from datetime import datetime
from colorama import Fore, Style

from telethon import errors

logger = logging.getLogger(__name__)

class GroupHandler:
    """Grup işlemleri yöneticisi"""
    
    def __init__(self, bot):
        """Bot nesnesini alır"""
        self.bot = bot
    
    async def process_group_messages(self):
        """Gruplara düzenli mesaj gönderir"""
        while self.bot.is_running:
            if not self.bot.is_paused:
                try:
                    # Kapatılma sinyali kontrol et
                    if self.bot._shutdown_event.is_set():
                        break
                    
                    # Her turda önce süresi dolmuş hataları temizle
                    cleared_errors = self.bot.db.clear_expired_error_groups()
                    if cleared_errors > 0:
                        logger.info(f"{cleared_errors} adet süresi dolmuş hata kaydı temizlendi")
                        # Hafızadaki hata listesini de güncelle
                        self.bot._load_error_groups()
                    
                    current_time = datetime.now().strftime("%H:%M:%S")
                    logger.info(f"🔄 Yeni tur başlıyor: {current_time}")
                    
                    # Grupları al 
                    groups = await self._get_groups()
                    logger.info(f"📊 Aktif Grup: {len(groups)} | ⚠️ Devre Dışı: {len(self.bot.error_groups)}")
                    
                    # Mesaj gönderimleri için sayaç
                    tur_mesaj_sayisi = 0
                    
                    # Her gruba mesaj gönder
                    for group in groups:
                        # Kapatılma sinyali kontrol et
                        if not self.bot.is_running or self.bot.is_paused or self.bot._shutdown_event.is_set():
                            break
                            
                        success = await self._send_message_to_group(group)
                        if success:
                            tur_mesaj_sayisi += 1
                            logger.info(f"✅ Mesaj gönderildi: {group.title}")
                        
                        # Mesajlar arasında bekle
                        await self._interruptible_sleep(random.randint(8, 15))
                    
                    # Tur istatistiklerini göster
                    logger.info(f"✉️ Turda: {tur_mesaj_sayisi} | 📈 Toplam: {self.bot.sent_count}")
                    
                    # Tur sonrası bekle (YENİ: 4 dakika - daha sık çalışsın)
                    wait_time = 4 * 60  # 4 dakika
                    logger.info(f"⏳ Bir sonraki tur için {wait_time//60} dakika bekleniyor...")
                    await self.bot.wait_with_countdown(wait_time)
                    
                except asyncio.CancelledError:
                    logger.info("Grup mesaj işleme iptal edildi")
                    break
                except Exception as e:
                    logger.error(f"Grup mesaj döngüsü hatası: {str(e)}")
                    await self._interruptible_sleep(60)
            else:
                # Duraklatıldıysa her saniye kontrol et
                await asyncio.sleep(1)
    
    async def _get_groups(self):
        """Aktif grupları getirir"""
        groups = []
        try:
            # Mevcut grupları ve hata veren grupları kaydet
            async for dialog in self.bot.client.iter_dialogs():
                # Sadece grupları al
                if dialog.is_group:
                    # Eğer hata verenler arasında değilse listeye ekle
                    if dialog.id not in self.bot.error_groups:
                        groups.append(dialog)
            
            logger.info(f"Toplam {len(groups)} aktif grup bulundu")
        except errors.FloodWaitError as e:
            # Flood wait hatası - çıktıyı tekrarlama
            key = f"get_groups_flood_{e.seconds}"
            if key not in self.bot.last_error_messages or self.bot.last_error_messages[key] < datetime.now().timestamp() - 30:
                logger.warning(f"Grupları getirirken flood wait hatası: {e.seconds}s bekleniyor")
                self.bot.last_error_messages[key] = datetime.now().timestamp()
                
            await asyncio.sleep(e.seconds)
            return []
        except Exception as e:
            logger.error(f"Grup getirme hatası: {str(e)}")
        
        return groups
    
    async def _send_message_to_group(self, group):
        """Gruba mesaj gönderir"""
        try:
            message = random.choice(self.bot.messages)
            
            # Konsol çıktısı
            print(f"{Fore.MAGENTA}📨 Gruba Mesaj: '{group.title}' grubuna mesaj gönderiliyor{Style.RESET_ALL}")
            
            # Mesajı gönder
            await self.bot.client.send_message(group.id, message)
            
            # İstatistikleri güncelle
            self.bot.sent_count += 1
            self.bot.processed_groups.add(group.id)
            self.bot.last_message_time = datetime.now()
            
            # Başarılı gönderim logu
            logger.info(f"Mesaj başarıyla gönderildi: {group.title} (ID:{group.id})")
            
            return True
            
        except errors.FloodWaitError as e:
            # Flood Wait hatası için özel işlem - tekrarlanan mesajları önle
            wait_time = e.seconds + random.randint(5, 15)
            
            error_key = f"flood_{group.id}"
            if error_key not in self.bot.error_counter:
                self.bot.error_counter[error_key] = 0
            
            self.bot.error_counter[error_key] += 1
            
            # İlk hata veya her 5 hatada bir göster
            if self.bot.error_counter[error_key] == 1 or self.bot.error_counter[error_key] % 5 == 0:
                logger.warning(f"Flood wait hatası: {wait_time}s bekleniyor ({group.title})")
            
            await asyncio.sleep(wait_time)
            return False
            
        except (errors.ChatWriteForbiddenError, errors.UserBannedInChannelError) as e:
            # Erişim engelleri için kalıcı olarak devre dışı bırak
            error_reason = f"Erişim engeli: {str(e)}"
            self._mark_error_group(group, error_reason)
            
            # Veritabanına da kaydet
            self.bot.db.add_error_group(group.id, group.title, error_reason, retry_hours=8)
            
            logger.error(f"Grup erişim hatası: {group.title} (ID:{group.id}) - {error_reason}")
            return False
            
        except Exception as e:
            # Diğer hatalar
            if "The channel specified is private" in str(e):
                error_reason = f"Erişim engeli: {str(e)}"
                self._mark_error_group(group, error_reason)
                self.bot.db.add_error_group(group.id, group.title, error_reason, retry_hours=8)
            else:
                logger.error(f"Grup mesaj hatası: {group.title} (ID:{group.id}) - {str(e)}")
            
            await asyncio.sleep(5)
            return False
    
    def _mark_error_group(self, group, reason: str):
        """Hata veren grubu işaretler"""
        self.bot.error_groups.add(group.id)
        self.bot.error_reasons[group.id] = reason
        logger.warning(f"⚠️ Grup devre dışı bırakıldı - {group.title}: {reason}")
    
    async def _interruptible_sleep(self, seconds):
        """Kesintiye uğrayabilen bekleme"""
        step = 0.5  # Daha sık kontroller için
        for _ in range(int(seconds / step)):
            if not self.bot.is_running or self.bot._shutdown_event.is_set():
                break
            await asyncio.sleep(step)