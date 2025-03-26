"""
Bot görevleri için sınıf
"""
import asyncio
import sys
import random
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from colorama import Fore, Style
from tabulate import tabulate
from telethon import errors

logger = logging.getLogger(__name__)

class BotTasks:
    """Bot için periyodik görevler ve komut dinleyici"""
    
    def __init__(self, bot):
        """Bot referansını alarak başlat"""
        self.bot = bot
        
    async def command_listener(self):
        """Konsoldan komut dinler"""
        logger.info("Komut dinleyici başlatıldı")
        
        # Bot kullanımı için yardım mesajını göster
        self.bot._print_help()
        
        while self.bot.is_running and not self.bot._shutdown_event.is_set():
            try:
                # Asenkron I/O için güvenli giriş alma
                command = await self._async_input(">>> ")
                
                # Boş giriş kontrolü
                if not command:
                    continue
                    
                # Komut işleme
                if command.lower() == 'q':
                    print(f"{Fore.YELLOW}⚠️ Çıkış komutu alındı, bot kapatılıyor...{Style.RESET_ALL}")
                    self.bot.shutdown()
                    break
                    
                elif command.lower() == 'p':
                    self.bot.toggle_pause()
                    
                elif command.lower() == 's':
                    self.bot.show_status()
                    
                elif command.lower() == 'c':
                    self.bot.clear_console()
                    
                elif command.lower() == 'h':
                    self.bot._print_help()
                    
                else:
                    print(f"{Fore.RED}❌ Bilinmeyen komut: {command}{Style.RESET_ALL}")
                    self.bot._print_help()
                    
            except asyncio.CancelledError:
                logger.info("Komut dinleyici iptal edildi")
                break
            except Exception as e:
                logger.error(f"Komut işleme hatası: {str(e)}")
                await asyncio.sleep(1)
        
        logger.info("Komut dinleyici sonlandı")
    
    async def _async_input(self, prompt):
        """Asenkron I/O için giriş alma"""
        # Standart input'un asenkron versiyonu
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: input(prompt))
    
    async def process_group_messages(self):
        """Gruplara düzenli mesaj gönderir"""
        logger.info("Grup mesaj gönderme görevi başlatıldı")
        
        while self.bot.is_running and not self.bot._shutdown_event.is_set():
            try:
                # Duraklatma kontrolü - kritik nokta
                if self.bot.is_paused:
                    await self.bot.check_paused()
                    continue
                
                # Her turda önce süresi dolmuş hataları temizle
                cleared_errors = self.bot.db.clear_expired_error_groups()
                if cleared_errors > 0:
                    logger.info(f"{cleared_errors} adet süresi dolmuş hata kaydı temizlendi")
                    # Hafızadaki hata listesini de güncelle
                    self.bot._load_error_groups()
                
                current_time = datetime.now().strftime("%H:%M:%S")
                logger.info(f"🔄 Yeni tur başlıyor: {current_time}")
                
                # Duraklatma kontrolü
                if self.bot.is_paused or self.bot._shutdown_event.is_set():
                    continue
                
                # Grupları al - DİNAMİK GRUP LİSTESİ
                groups = await self._get_groups()
                logger.info(f"📊 Aktif Grup: {len(groups)} | ⚠️ Devre Dışı: {len(self.bot.error_groups)}")
                
                # Mesaj gönderimleri için sayaç
                tur_mesaj_sayisi = 0
                
                # Her gruba mesaj gönder
                for group in groups:
                    # Her döngüde duraklatma/kapatma kontrolü
                    if not self.bot.is_running or self.bot._shutdown_event.is_set():
                        logger.info("Grup mesaj görevi: Kapatma sinyali alındı")
                        break
                        
                    if self.bot.is_paused:
                        logger.info("Grup mesaj görevi: Duraklatma sinyali alındı")
                        await self.bot.check_paused()
                        continue
                    
                    # Mesaj göndermeyi dene
                    success = await self._send_message_to_group(group)
                    if success:
                        tur_mesaj_sayisi += 1
                        logger.info(f"✅ Mesaj gönderildi: {group.title}")
                    
                    # Mesajlar arasında bekle - kesintiye uğrayabilir
                    await self.bot.interruptible_sleep(random.randint(8, 15))
                
                # Tur istatistiklerini göster
                logger.info(f"✉️ Turda: {tur_mesaj_sayisi} | 📈 Toplam: {self.bot.sent_count}")
                
                # Duraklatma kontrolü
                if self.bot.is_paused:
                    await self.bot.check_paused()
                    continue
                
                # Tur sonrası bekle - kesintiye uğrayabilir
                wait_time = 8 * 60  # 8 dakika
                logger.info(f"⏳ Bir sonraki tur için {wait_time//60} dakika bekleniyor...")
                await self.bot.interruptible_sleep(wait_time)
                
            except asyncio.CancelledError:
                logger.info("Grup mesaj görevi iptal edildi")
                break
            except Exception as e:
                logger.error(f"Grup mesaj döngüsü hatası: {str(e)}", exc_info=True)
                # Hata durumunda bekle - kesintiye uğrayabilir
                await self.bot.interruptible_sleep(60)
        
        logger.info("Grup mesaj görevi sonlandı")
    
    async def process_personal_invites(self):
        """Özel davetleri işler - daha sık çalışacak şekilde optimize edildi"""
        logger.info("Özel davet gönderme görevi başlatıldı")
        
        while self.bot.is_running and not self.bot._shutdown_event.is_set():
            try:
                # Duraklatma kontrolü
                if self.bot.is_paused:
                    await self.bot.check_paused()
                    continue
                
                # Davet aralığını dakika cinsinden al (daha sık davet gönderimi için)
                interval_minutes = self.bot.pm_delays['davet_interval']
                
                # Daha kısa bekleme süresi - 1 saniyelik adımlarla kontrol et
                for _ in range(interval_minutes * 60):
                    if not self.bot.is_running or self.bot._shutdown_event.is_set():
                        logger.info("Davet işleme görevi: Kapatma sinyali alındı")
                        return
                    
                    if self.bot.is_paused:
                        await self.bot.check_paused()
                        break
                    
                    await asyncio.sleep(1)
                
                # Durum kontrolü
                if not self.bot.is_running or self.bot._shutdown_event.is_set():
                    break
                
                if self.bot.is_paused:
                    await self.bot.check_paused()
                    continue
                
                # Davet edilecek kullanıcıları al
                users_to_invite = self.bot.db.get_users_to_invite(limit=5)
                if not users_to_invite:
                    logger.info("📪 Davet edilecek kullanıcı bulunamadı")
                    continue
                
                logger.info(f"📩 {len(users_to_invite)} kullanıcıya davet gönderiliyor...")
                
                # Her kullanıcıya davet gönder
                for user_id, username in users_to_invite:
                    # Her davet öncesi duraklatma/kapatma kontrolü
                    if not self.bot.is_running or self.bot._shutdown_event.is_set():
                        logger.info("Davet işleme görevi: Kapatma sinyali alındı")
                        break
                    
                    if self.bot.is_paused:
                        await self.bot.check_paused()
                        continue
                    
                    # Saatlik limiti kontrol et
                    if self.bot.pm_state['hourly_count'] >= self.bot.pm_delays['hourly_limit']:
                        logger.warning("⚠️ Saatlik mesaj limiti doldu!")
                        break
                    
                    # Davet mesajı gönder
                    await self.bot.invite_user(user_id, username)
                    
                    # Davetler arasında bekle - kesintiye uğrayabilir
                    await self.bot.interruptible_sleep(random.randint(30, 60))  # Daha kısa bekleme
                
            except asyncio.CancelledError:
                logger.info("Davet işleme görevi iptal edildi")
                break
            except Exception as e:
                logger.error(f"Özel davet hatası: {str(e)}")
                # Hatada bekle - kesintiye uğrayabilir  
                await self.bot.interruptible_sleep(60)
        
        logger.info("Davet işleme görevi sonlandı")
    
    async def periodic_cleanup(self):
        """Periyodik temizleme işlemleri yapar"""
        logger.info("Periyodik temizleme görevi başlatıldı")
        
        while self.bot.is_running and not self.bot._shutdown_event.is_set():
            try:
                # Her 10 dakikada bir çalış
                await self.bot.interruptible_sleep(600)
                
                # Duraklatma kontrolü
                if self.bot.is_paused:
                    await self.bot.check_paused()
                    continue
                
                # Süresi dolmuş hataları temizle  
                cleared_errors = self.bot.db.clear_expired_error_groups()
                if cleared_errors > 0:
                    logger.info(f"{cleared_errors} adet süresi dolmuş hata kaydı temizlendi")
                    # Hafızadaki hata listesini de güncelle
                    self.bot._load_error_groups()
                
                # Aktivite listesini belirli bir boyutta tut
                if len(self.bot.displayed_users) > 500:
                    logger.info(f"Aktivite takip listesi temizleniyor ({len(self.bot.displayed_users)} -> 100)")
                    # En son eklenen 100 kullanıcıyı tut
                    self.bot.displayed_users = set(list(self.bot.displayed_users)[-100:])
                
            except asyncio.CancelledError:
                logger.info("Periyodik temizleme görevi iptal edildi")
                break
            except Exception as e:
                logger.error(f"Periyodik temizleme hatası: {str(e)}")
        
        logger.info("Periyodik temizleme görevi sonlandı")
                
    async def manage_error_groups(self):
        """Başlangıçta grup hata kayıtlarını yönetir"""
        error_groups = self.bot.db.get_error_groups()
        if not error_groups:
            logger.info("Hata veren grup kaydı bulunmadı")
            return
        
        # Konsola hata gruplarını göster
        print(f"\n{Fore.YELLOW}⚠️ {len(error_groups)} adet hata veren grup kaydı bulundu:{Style.RESET_ALL}")
        
        error_table = []
        for group_id, group_title, error_reason, error_time, retry_after in error_groups:
            error_table.append([group_id, group_title, error_reason, retry_after])
        
        print(tabulate(error_table, headers=["Grup ID", "Grup Adı", "Hata", "Yeniden Deneme"], tablefmt="grid"))
        
        # Kullanıcıya sor
        print(f"\n{Fore.CYAN}Hata kayıtlarını ne yapmak istersiniz?{Style.RESET_ALL}")
        print(f"{Fore.GREEN}1){Style.RESET_ALL} Kayıtları koru (varsayılan)")
        print(f"{Fore.GREEN}2){Style.RESET_ALL} Tümünü temizle (yeniden deneme)")
        
        try:
            selection = await self.bot.tasks._async_input("\nSeçiminiz (1-2): ") or "1"
            
            if selection == "2":
                cleared = self.bot.db.clear_all_error_groups()
                self.bot.error_groups.clear()
                self.bot.error_reasons.clear()
                logger.info(f"Tüm hata kayıtları temizlendi ({cleared} kayıt)")
                print(f"{Fore.GREEN}✅ {cleared} adet hata kaydı temizlendi{Style.RESET_ALL}")
            else:
                logger.info("Hata kayıtları korundu")
                print(f"{Fore.CYAN}ℹ️ Hata kayıtları korundu{Style.RESET_ALL}")
        except Exception as e:
            logger.error(f"Hata kayıtları yönetim hatası: {str(e)}")
    
    async def _get_groups(self) -> List:
        """Aktif grupları getirir - her seferinde yeni liste oluşturur"""
        groups = []
        try:
            # Mevcut grupları ve hata veren grupları kaydet
            async for dialog in self.bot.client.iter_dialogs():
                # Kapanış kontrolü
                if not self.bot.is_running or self.bot._shutdown_event.is_set():
                    logger.info("Grup getirme sırasında kapatma sinyali alındı")
                    return groups
                    
                # Sadece grupları al
                if dialog.is_group:
                    # Eğer hata verenler arasında değilse listeye ekle
                    if dialog.id not in self.bot.error_groups:
                        groups.append(dialog)
                    else:
                        logger.debug(
                            f"Grup atlandı (hata kayıtlı): {dialog.title} (ID:{dialog.id})",
                            extra={
                                'group_id': dialog.id,
                                'group_title': dialog.title,
                                'error_reason': self.bot.error_reasons.get(dialog.id, "Bilinmeyen hata")
                            }
                        )
            
            logger.info(f"Toplam {len(groups)} aktif grup bulundu")
        except errors.FloodWaitError as e:
            self.bot.error_handler.handle_flood_wait(
                "FloodWaitError", 
                f"Grup listeleme için {e.seconds} saniye bekleniyor",
                {'wait_time': e.seconds}
            )
            await asyncio.sleep(e.seconds + 5)  # Biraz daha fazla bekle
        except Exception as e:
            logger.error(f"Grup getirme hatası: {str(e)}")
        
        return groups
    
    async def _send_message_to_group(self, group) -> bool:
        """Gruba mesaj gönderir"""
        try:
            # Kapatma kontrolü
            if self.bot._shutdown_event.is_set() or not self.bot.is_running:
                return False
                
            message = random.choice(self.bot.messages)
            
            # Mesaj gönderimi öncesi log
            logger.debug(
                f"Mesaj gönderiliyor: Grup={group.title} (ID:{group.id})",
                extra={
                    'group_id': group.id,
                    'group_title': group.title,
                    'message': message[:50] + ('...' if len(message) > 50 else '')
                }
            )
            
            # Konsol çıktısı
            print(f"{Fore.MAGENTA}📨 Gruba Mesaj: '{group.title}' grubuna mesaj gönderiliyor{Style.RESET_ALL}")
            
            # Mesajı gönder
            await self.bot.client.send_message(group.id, message)
            
            # İstatistikleri güncelle
            self.bot.sent_count += 1
            self.bot.processed_groups.add(group.id)
            self.bot.last_message_time = datetime.now()
            
            # Başarılı gönderim logu
            logger.info(
                f"Mesaj başarıyla gönderildi: {group.title} (ID:{group.id})",
                extra={
                    'group_id': group.id, 
                    'group_title': group.title,
                    'message_id': self.bot.sent_count,
                    'timestamp': self.bot.last_message_time.strftime('%H:%M:%S')
                }
            )
            
            return True
            
        except errors.FloodWaitError as e:
            # Flood Wait hatası için özel işlem
            wait_time = e.seconds + random.randint(5, 15)  # Ekstra bekleme ekle
            logger.warning(
                f"Flood wait hatası: {wait_time} saniye bekleniyor ({group.title} - ID:{group.id})",
                extra={
                    'error_type': 'FloodWaitError',
                    'group_id': group.id,
                    'group_title': group.title,
                    'wait_time': wait_time
                }
            )
            await self.bot.interruptible_sleep(wait_time)
            return False
            
        except (errors.ChatWriteForbiddenError, errors.UserBannedInChannelError) as e:
            # Erişim engelleri için kalıcı olarak devre dışı bırak
            error_reason = f"Erişim engeli: {str(e)}"
            self.bot.mark_error_group(group, error_reason)
            
            # Veritabanına da kaydet - 8 saat sonra yeniden dene
            self.bot.db.add_error_group(group.id, group.title, error_reason, retry_hours=8)
            
            logger.error(
                f"Grup erişim hatası: {group.title} (ID:{group.id}) - {error_reason}",
                extra={
                    'error_type': e.__class__.__name__,
                    'group_id': group.id,
                    'group_title': group.title,
                    'error_message': str(e),
                    'action': 'devre_dışı_bırakıldı',
                    'retry_after': '8 saat'
                }
            )
            return False
            
        except Exception as e:
            # Diğer hatalar için de hata grubuna ekle
            if "The channel specified is private" in str(e):
                error_reason = f"Erişim engeli: {str(e)}"
                self.bot.mark_error_group(group, error_reason)
                self.bot.db.add_error_group(group.id, group.title, error_reason, retry_hours=8)
                logger.error(f"Grup erişim hatası: {group.title} (ID:{group.id}) - {error_reason}")
            else:
                # Geçici hata olabilir
                logger.error(
                    f"Grup mesaj hatası: {group.title} (ID:{group.id}) - {str(e)}",
                    extra={
                        'error_type': e.__class__.__name__,
                        'group_id': group.id,
                        'group_title': group.title,
                        'error_message': str(e)
                    }
                )
            
            if "Too many requests" in str(e):
                await self.bot.interruptible_sleep(60)  # Rate limiting için uzun süre bekle
            else:
                await self.bot.interruptible_sleep(5)  # Diğer hatalar için kısa bekle
            return False