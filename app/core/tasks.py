"""
# ============================================================================ #
# Dosya: tasks.py
# Yol: /Users/siyahkare/code/telegram-bot/app/tasks.py
# İşlev: Telegram Bot Görev Yönetimi
#
# Build: 2025-04-01-04:15:00
# Versiyon: v3.4.0
# ============================================================================ #
#
# Bu modül, Telegram bot uygulamasının görev yönetimini sağlar:
# - Periyodik görevlerin (temizleme, durum kontrolü) yönetimi
# - Konsol komutlarını dinleme ve işleme
# - Grup mesajları gönderme ve kişisel davetler işleme
# - Hata yönetimi ve loglama
# - Asenkron işlem desteği
#
# Sorumluluklar:
# - Botun sürekli çalışmasını sağlamak
# - Belirli aralıklarla yapılması gereken işleri otomatikleştirmek
# - Kullanıcıdan gelen komutları yorumlamak ve uygulamak
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
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
from app.utils.rate_limiter import RateLimiter 
from celery import shared_task
from sqlalchemy import select
from database.models import Group
from database.database import get_db
from app.telegram_bot import TelegramBot

logger = logging.getLogger(__name__)

class BotTasks:
    """
    Telegram bot için periyodik görevler ve komut dinleyici.
    
    Bu sınıf, botun sürekli çalışmasını ve belirli aralıklarla
    yapılması gereken işleri yönetir. Ayrıca, konsoldan gelen
    komutları dinler ve işler.
    """
    
    def __init__(self, bot):
        """
        BotTasks sınıfını başlatır.
        
        Args:
            bot: Ana TelegramBot nesnesi.
        """
        self.bot = bot
        self.active_tasks = []
        task_limit = 100  # Define a default task limit
        self.task_limiter = RateLimiter(max_requests=task_limit, time_window=60)
        
    async def start_tasks(self):
        """
        Tüm görevleri başlatır.
        
        Bu metot, tüm periyodik görevleri ve komut dinleyiciyi başlatır.
        """
        tasks = [
            self.manage_error_groups(),
            self.periodic_cleanup(),
            self.command_listener(),
            self.process_group_messages(),
            self.process_personal_invites()
        ]
        
        # Görevleri kaydet
        self.active_tasks = [asyncio.create_task(task) for task in tasks]
        
        # Görevleri başlat
        await asyncio.gather(*self.active_tasks, return_exceptions=True)

    async def command_listener(self):
        """
        Konsoldan komut dinler.
        
        Bu metot, konsoldan girilen komutları dinler ve ilgili
        işlemleri gerçekleştirir.
        """
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
        """
        Asenkron I/O için giriş alma.
        
        Bu metot, asenkron bir şekilde kullanıcıdan giriş almayı sağlar.
        
        Args:
            prompt: Kullanıcıya gösterilecek mesaj.
        
        Returns:
            Kullanıcının girdiği metin.
        """
        # Standart input'un asenkron versiyonu
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: input(prompt))
    
    async def process_group_messages(self):
        """
        Grup mesajlarını işler.
        
        Bu metot, botun aktif olduğu gruplara mesaj gönderme işlemini yönetir.
        """
        await self.bot.group_handler.process_group_messages()

    async def process_personal_invites(self):
        """
        Kişisel davetleri işler.
        
        Bu metot, botun yeni kullanıcılara kişisel davet gönderme işlemini yönetir.
        """
        await self.bot.user_handler.process_personal_invites()
    
    async def periodic_cleanup(self):
        """
        Periyodik temizleme işlemleri yapar.
        
        Bu metot, belirli aralıklarla botun durumunu kontrol eder,
        hata sayaçlarını temizler ve süresi dolmuş hata kayıtlarını siler.
        """
        logger.info("Periyodik temizleme görevi başlatıldı")
        
        while self.bot.is_running and not self.bot._shutdown_event.is_set():
            try:
                # Her saat başı
                if datetime.now().minute == 0:
                    # Hata sayaçlarını temizle
                    self.bot.error_counter.clear()
                    logger.info("Hata sayaçları temizlendi")
                    
                    # Süresi dolmuş hata gruplarını temizle
                    cleared_errors = self.bot.db.clear_expired_error_groups()
                    if cleared_errors:
                        logger.info(f"{cleared_errors} adet süresi dolmuş hata kaydı temizlendi")
                        # Hata listesini güncelle
                        self.bot._load_error_groups()
                
                # Her 10 dakikada bir 
                if datetime.now().minute % 10 == 0:
                    # Rate limit durumunu resetle
                    current_time = datetime.now()
                    if self.bot.pm_state['hour_start'] and (current_time - self.bot.pm_state['hour_start']).total_seconds() >= 3600:
                        self.bot.pm_state['hourly_count'] = 0
                        self.bot.pm_state['hour_start'] = current_time
                        self.bot.pm_state['burst_count'] = 0
                        logger.info("Saatlik mesaj limitleri sıfırlandı")
                
                # Her dakika
                # FloodWait durumunu kontrol et
                if self.bot.flood_wait_active and self.bot.flood_wait_end_time:
                    if datetime.now() > self.bot.flood_wait_end_time:
                        self.bot.flood_wait_active = False
                        logger.info("FloodWait süresi doldu, normal işleme devam ediliyor")
                
                # Duraklatma durumunu kontrol et
                if self.bot.is_paused:
                    await self.bot.check_paused()
                    continue
                
                # Her 1 dakika
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                logger.info("Periyodik temizleme iptal edildi")
                break
            except Exception as e:
                logger.error(f"Periyodik temizleme hatası: {str(e)}")
                await asyncio.sleep(60)
        
        logger.info("Periyodik temizleme görevi sonlandı")
                
    async def manage_error_groups(self):
        """
        Başlangıçta grup hata kayıtlarını yönetir.
        
        Bu metot, bot başladığında veritabanındaki hata kayıtlarını
        okur ve kullanıcıya bu kayıtları nasıl yöneteceğine dair
        seçenekler sunar.
        """
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
            selection = await self._async_input("\nSeçiminiz (1-2): ") or "1"
            
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
        """
        Aktif grupları getirir.
        
        Bu metot, botun erişebildiği tüm aktif grupların listesini getirir.
        
        Returns:
            Aktif grupların listesi.
        """
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
            await asyncio.sleep(e.seconds + 5)  # Biraz daha bekle
        except Exception as e:
            logger.error(f"Grup getirme hatası: {str(e)}")
        
        return groups
    
    async def _send_message_to_group(self, group) -> bool:
        """
        Gruba mesaj gönderir.
        
        Bu metot, belirtilen gruba rastgele bir mesaj gönderir.
        
        Args:
            group: Mesaj gönderilecek grup nesnesi.
        
        Returns:
            Mesaj başarıyla gönderildiyse True, aksi halde False.
        """
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

@shared_task(bind=True, name='discover_groups')
def discover_groups(self):
    """Grup keşfi görevi"""
    try:
        db = next(get_db())
        bot = TelegramBot()
        
        # Aktif grupları al
        groups = db.execute(
            select(Group).where(Group.is_active == True)
        ).scalars().all()
        
        for group in groups:
            try:
                # Grup bilgilerini güncelle
                group_info = bot.get_group_info(group.group_id)
                if group_info:
                    group.name = group_info.name
                    group.member_count = group_info.member_count
                    group.last_message = group_info.last_message
                    db.commit()
            except Exception as e:
                logger.error(f"Grup {group.group_id} güncellenirken hata: {str(e)}")
                group.error_count += 1
                group.last_error = str(e)
                db.commit()
                
    except Exception as e:
        logger.error(f"Grup keşfi sırasında hata: {str(e)}")
        raise self.retry(exc=e, countdown=300)  # 5 dakika sonra tekrar dene

@shared_task(bind=True, name='send_messages')
def send_messages(self):
    """Mesaj gönderme görevi"""
    try:
        db = next(get_db())
        bot = TelegramBot()
        
        # Hedef grupları al
        groups = db.execute(
            select(Group).where(
                Group.is_active == True,
                Group.is_target == True,
                Group.permanent_error == False
            )
        ).scalars().all()
        
        for group in groups:
            try:
                # Mesaj gönder
                success = bot.send_message(group.group_id, "Test mesajı")
                if success:
                    group.message_count += 1
                    group.error_count = 0
                    db.commit()
            except Exception as e:
                logger.error(f"Grup {group.group_id} mesaj gönderilirken hata: {str(e)}")
                group.error_count += 1
                group.last_error = str(e)
                if group.error_count >= 3:
                    group.permanent_error = True
                db.commit()
                
    except Exception as e:
        logger.error(f"Mesaj gönderme sırasında hata: {str(e)}")
        raise self.retry(exc=e, countdown=300)

@shared_task(bind=True, name='update_stats')
def update_stats(self):
    """İstatistik güncelleme görevi"""
    try:
        db = next(get_db())
        
        # Genel istatistikleri hesapla
        total_groups = db.execute(
            select(Group)
        ).scalars().all()
        
        active_groups = sum(1 for g in total_groups if g.is_active)
        target_groups = sum(1 for g in total_groups if g.is_target)
        error_groups = sum(1 for g in total_groups if g.permanent_error)
        
        logger.info(f"""
        Toplam Grup: {len(total_groups)}
        Aktif Grup: {active_groups}
        Hedef Grup: {target_groups}
        Hatalı Grup: {error_groups}
        """)
        
    except Exception as e:
        logger.error(f"İstatistik güncelleme sırasında hata: {str(e)}")
        raise self.retry(exc=e, countdown=300)