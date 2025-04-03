"""
# ============================================================================ #
# Dosya: invite_handler.py
# Yol: /Users/siyahkare/code/telegram-bot/bot/handlers/invite_handler.py
# İşlev: Telegram bot için davet yönetimi.
#
# Build: 2025-04-01-00:36:09
# Versiyon: v3.4.0
# ============================================================================ #
#
# Bu modül, Telegram botunun davet işlemlerini yönetir.
# Temel özellikleri:
# - Bekleyen davetleri alma
# - Kullanıcılara davet mesajları gönderme
# - Hata yönetimi ve loglama
#
# ============================================================================ #
"""

import asyncio
import random
from colorama import Fore, Style
import logging

logger = logging.getLogger(__name__)

class InviteHandler:
    """
    Telegram bot için davet işleme sınıfı.

    Bu sınıf, bekleyen davetleri alır ve ilgili kullanıcılara davet mesajları gönderir.
    """
    def __init__(self, bot):
        """
        InviteHandler sınıfının başlatıcı metodu.

        Args:
            bot: Bağlı olduğu bot nesnesi.
        """
        self.bot = bot

    async def process_invites(self):
        """
        Sistemdeki davetleri işler ve ilgili kullanıcılara davet mesajları gönderir.
        """
        while self.bot.is_running:
            if not self.bot.is_paused:
                try:
                    # Kapatılma sinyali kontrol et
                    if self.bot._shutdown_event.is_set():
                        break
                        
                    # Davet listesini al
                    invites = await self._get_pending_invites()
                    if not invites:
                        await asyncio.sleep(30)  # Davet yoksa 30 saniye bekle
                        continue
                        
                    print(f"{Fore.CYAN}📨 İşlenecek davet sayısı: {len(invites)}{Style.RESET_ALL}")
                    
                    # Her davet için işlem yap
                    for invite in invites:
                        # Kapatılma sinyali kontrol et
                        if not self.bot.is_running or self.bot.is_paused or self.bot._shutdown_event.is_set():
                            break
                            
                        success = await self._process_invite(invite)
                        if success:
                            print(f"{Fore.GREEN}✅ Davet gönderildi: {invite.user_id}{Style.RESET_ALL}")
                        
                        # Davetler arasında bekle
                        await self._interruptible_sleep(random.randint(5, 10))
                    
                    # Tur sonrası bekle (30 saniye)
                    print(f"{Fore.YELLOW}⏳ Sonraki davet kontrolü: 30 saniye{Style.RESET_ALL}")
                    await asyncio.sleep(30)
                    
                except asyncio.CancelledError:
                    logger.debug("Davet işleme iptal edildi")
                    break
                except Exception as e:
                    logger.error(f"Davet işleme hatası: {str(e)}")
                    await asyncio.sleep(30)
            else:
                # Duraklatıldıysa her saniye kontrol et
                await asyncio.sleep(1)