"""
# ============================================================================ #
# Dosya: handlers.py
# Yol: /Users/siyahkare/code/telegram-bot/bot/handlers/handlers.py
# İşlev: Telegram bot için işleyici (handler) yönetimi ve olay yönlendirme.
#
# Amaç: Bu modül, Telegram botunun gelen mesajlarını, komutlarını ve olaylarını
# dinleyip ilgili alt işleyicilere yönlendirme görevini üstlenir. Merkezi bir 
# yönlendirme sistemi olarak, tüm bot etkileşimlerinin doğru işleyicilere 
# aktarılmasını sağlar.
#
# Temel Özellikler:
# - Gelen mesajları türüne göre farklı işleyicilere yönlendirme
# - Özel mesajları işleme ve otomatik yanıtlama
# - Grup mesajlarını analiz etme ve gerektiğinde yanıtlama
# - Kullanıcı komutlarını işleme ve yönlendirme
# - Aktif kullanıcıları takip etme ve veritabanına kaydetme
# - Hata yönetimi ve akıllı rate-limiting
# - ServiceManager ile uyumlu yaşam döngüsü yönetimi
#
# Build: 2025-04-08-23:30:00
# Versiyon: v3.5.0
# ============================================================================ #
#
# Değişiklik Geçmişi:
# v3.5.0 (2025-04-08) - ServiceManager ile uyumlu hale getirildi
#                      - Yaşam döngüsü metotları eklendi (initialize, start, stop, run)
#                      - Olay işleme akışı optimize edildi
#                      - Ayrıntılı dokümantasyon eklendi
#                      - Yeni mesaj türleri desteği eklendi
#                      - Hata yönetimi geliştirildi
# v3.4.0 (2025-04-01) - İlk kapsamlı versiyon
# v3.3.0 (2025-03-15) - İlk sürüm
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

import logging
import asyncio
import random
from datetime import datetime
from typing import Dict, Any, List, Optional, Set, Union
from telethon import events, errors
from colorama import Fore, Style

from bot.handlers.group_handler import GroupHandler
from bot.handlers.message_handler import MessageHandler
from bot.handlers.user_handler import UserHandler
from bot.handlers.invite_handler import InviteHandler

logger = logging.getLogger(__name__)

class MessageHandlers:
    """
    Telegram mesaj işleyicileri ve yönlendirme merkezi.
    
    Bu sınıf, Telegram'dan gelen tüm olayları dinler ve
    ilgili handler sınıflarına/metotlara yönlendirir. ServiceManager
    ile entegre çalışarak servis yaşam döngüsünü yönetir.
    
    Attributes:
        bot: Ana bot nesnesi
        group_handler: Grup mesajlarını işleyen handler
        message_handler: Genel mesajları işleyen handler
        user_handler: Kullanıcı komutlarını işleyen handler
        invite_handler: Davet işlemlerini yöneten handler
        displayed_users: Görüntülenen kullanıcıları takip eden set
        last_user_logs: Son kullanıcı loglarını tutan sözlük
        is_running: Servisin çalışma durumunu belirten bayrak
        stop_event: Durdurma sinyali için kullanılan Event nesnesi
        stats: İstatistik verileri tutan sözlük
    """
    
    def __init__(self, bot, stop_event=None):
        """
        MessageHandlers sınıfını başlatır.
        
        Args:
            bot: Ana bot nesnesi
            stop_event: Durdurma sinyali için Event nesnesi (opsiyonel)
        """
        self.bot = bot
        self.group_handler = GroupHandler(bot)
        self.message_handler = MessageHandler(bot)
        self.user_handler = UserHandler(bot)
        self.invite_handler = InviteHandler(bot)
        
        # Kullanıcı aktivite kayıtları
        self.displayed_users = set()
        self.last_user_logs = {}
        
        # Servis durumu
        self.is_running = False
        self.is_paused = False
        self.stop_event = stop_event or asyncio.Event()
        
        # İstatistikler
        self.stats = {
            "total_messages": 0,
            "private_messages": 0,
            "group_messages": 0,
            "replies": 0,
            "new_users": 0,
            "errors": 0,
            "start_time": None,
            "last_activity": None
        }
        
        logger.info("MessageHandlers başlatıldı")
    
    async def initialize(self) -> bool:
        """
        Handler servisini başlatmak için gerekli hazırlıkları yapar.
        
        Returns:
            bool: Başarılı ise True
        """
        try:
            # Alt handler'ları başlat
            handlers_initialized = True
            
            for handler_name, handler in [
                ("group_handler", self.group_handler),
                ("message_handler", self.message_handler),
                ("user_handler", self.user_handler),
                ("invite_handler", self.invite_handler)
            ]:
                if hasattr(handler, 'initialize'):
                    success = await handler.initialize()
                    if not success:
                        logger.error(f"{handler_name} başlatılamadı")
                        handlers_initialized = False
            
            # İstatistikleri sıfırla
            self.stats["start_time"] = datetime.now()
            self.stats["last_activity"] = datetime.now()
            
            logger.info("MessageHandlers başarıyla initialize edildi")
            return handlers_initialized
            
        except Exception as e:
            logger.error(f"MessageHandlers initialize hatası: {str(e)}", exc_info=True)
            return False
    
    async def start(self) -> bool:
        """
        Handler servisini başlatır ve Telethon event handler'larını kaydeder.
        
        Returns:
            bool: Başarılı ise True
        """
        try:
            self.is_running = True
            self.is_paused = False
            
            # Alt handler'ları başlat
            for handler_name, handler in [
                ("group_handler", self.group_handler),
                ("message_handler", self.message_handler),
                ("user_handler", self.user_handler),
                ("invite_handler", self.invite_handler)
            ]:
                if hasattr(handler, 'start'):
                    try:
                        await handler.start()
                        logger.debug(f"{handler_name} başlatıldı")
                    except Exception as handler_error:
                        logger.error(f"{handler_name} start hatası: {str(handler_error)}")
            
            # Event handler'ları ayarla
            self.setup_handlers()
            
            logger.info("MessageHandlers başarıyla başlatıldı ve event handler'lar ayarlandı")
            return True
            
        except Exception as e:
            logger.error(f"MessageHandlers start hatası: {str(e)}", exc_info=True)
            return False
    
    async def stop(self) -> None:
        """
        Handler servisini durdurur ve kaynakları temizler.
        """
        logger.info("MessageHandlers durduruluyor...")
        self.is_running = False
        self.stop_event.set()
        
        # Alt handler'ları durdur
        for handler_name, handler in [
            ("group_handler", self.group_handler),
            ("message_handler", self.message_handler),
            ("user_handler", self.user_handler),
            ("invite_handler", self.invite_handler)
        ]:
            if hasattr(handler, 'stop'):
                try:
                    await handler.stop()
                    logger.debug(f"{handler_name} durduruldu")
                except Exception as handler_error:
                    logger.error(f"{handler_name} stop hatası: {str(handler_error)}")
        
        logger.info("MessageHandlers durduruldu")
    
    async def run(self) -> None:
        """
        Ana servis döngüsü - periodic bakım işlemleri yapar.
        
        Bu metot, servis durdurulana kadar çalışır ve periyodik olarak
        temizleme ve bakım işlemleri gerçekleştirir.
        """
        logger.info("MessageHandlers ana döngüsü başlatıldı")
        
        try:
            while not self.stop_event.is_set() and self.is_running:
                if not self.is_paused:
                    try:
                        # Periyodik temizleme işlemleri
                        await self._cleanup_displayed_users()
                        
                        # İstatistik güncelleme
                        self._update_stats()
                    except Exception as e:
                        logger.error(f"Periyodik görev hatası: {str(e)}")
                
                # Sık kontrol etmemek için 30 dakika bekle
                try:
                    await asyncio.wait_for(self.stop_event.wait(), timeout=1800)
                    if self.stop_event.is_set():
                        break
                except asyncio.TimeoutError:
                    pass  # Timeout beklenen bir durum, devam et
                
        except asyncio.CancelledError:
            logger.info("MessageHandlers ana görevi iptal edildi")
        except Exception as e:
            logger.error(f"MessageHandlers ana döngü hatası: {str(e)}", exc_info=True)

    async def pause(self) -> None:
        """
        Handler servisini geçici olarak duraklatır.
        """
        if not self.is_paused:
            self.is_paused = True
            logger.info("MessageHandlers duraklatıldı")
            
            # Alt handler'ları duraklat
            for handler_name, handler in [
                ("group_handler", self.group_handler),
                ("message_handler", self.message_handler),
                ("user_handler", self.user_handler),
                ("invite_handler", self.invite_handler)
            ]:
                if hasattr(handler, 'pause'):
                    try:
                        await handler.pause()
                    except Exception as handler_error:
                        logger.error(f"{handler_name} pause hatası: {str(handler_error)}")

    async def resume(self) -> None:
        """
        Duraklatılmış handler servisini devam ettirir.
        """
        if self.is_paused:
            self.is_paused = False
            logger.info("MessageHandlers devam ettiriliyor")
            
            # Alt handler'ları devam ettir
            for handler_name, handler in [
                ("group_handler", self.group_handler),
                ("message_handler", self.message_handler),
                ("user_handler", self.user_handler),
                ("invite_handler", self.invite_handler)
            ]:
                if hasattr(handler, 'resume'):
                    try:
                        await handler.resume()
                    except Exception as handler_error:
                        logger.error(f"{handler_name} resume hatası: {str(handler_error)}")

    def handle_message(self, message) -> None:
        """
        Gelen mesajları ilgili handler'a yönlendirir.
        
        Args:
            message: İşlenecek mesaj nesnesi
        """
        if not self.is_running or self.is_paused:
            return
            
        try:
            # Mesaj türüne göre ilgili handler'a yönlendirme yap
            self.message_handler.process_message(message)
            self.stats["total_messages"] += 1
            self.stats["last_activity"] = datetime.now()
        except Exception as e:
            logger.error(f"Mesaj işleme hatası: {str(e)}")
            self.stats["errors"] += 1

    def handle_group_message(self, message) -> None:
        """
        Grup mesajlarını ilgili handler'a yönlendirir.
        
        Args:
            message: İşlenecek grup mesaj nesnesi
        """
        if not self.is_running or self.is_paused:
            return
            
        try:
            self.group_handler.process_group_message(message)
            self.stats["group_messages"] += 1
            self.stats["last_activity"] = datetime.now()
        except Exception as e:
            logger.error(f"Grup mesajı işleme hatası: {str(e)}")
            self.stats["errors"] += 1

    def handle_user_command(self, message) -> None:
        """
        Kullanıcı komutlarını ilgili handler'a yönlendirir.
        
        Args:
            message: İşlenecek komut mesajı
        """
        if not self.is_running or self.is_paused:
            return
            
        try:
            self.user_handler.process_user_command(message)
            self.stats["total_messages"] += 1
            self.stats["last_activity"] = datetime.now()
        except Exception as e:
            logger.error(f"Kullanıcı komutu işleme hatası: {str(e)}")
            self.stats["errors"] += 1
        
    def setup_handlers(self) -> None:
        """
        Telethon mesaj işleyicilerini ayarlar ve kaydeder.
        """
        # Eğer handler'lar zaten kurulmuşsa tekrar kurma
        if hasattr(self, '_handlers_setup') and self._handlers_setup:
            return
            
        @self.bot.client.on(events.NewMessage(incoming=True))
        async def message_handler(event):
            """Gelen mesajları işler"""
            if not self.is_running or self.is_paused:
                return
                
            try:
                # Özel mesaj mı?
                if event.is_private:
                    await self.handle_private_message(event)
                # Grup mesajı mı?
                else:
                    # Yanıt mı?
                    if event.is_reply:
                        await self.handle_group_reply(event)
                    # Normal mesaj mı?
                    else:
                        await self.track_active_users(event)
            except Exception as e:
                self.stats["errors"] += 1
                self.bot.error_handler.log_error(
                    "Mesaj işleme hatası",
                    str(e),
                    {'event_type': 'message', 'chat_id': getattr(event, 'chat_id', None)}
                )
        
        @self.bot.client.on(events.ChatAction())
        async def chat_action_handler(event):
            """Grup üyelik değişimlerini izler (katılma/ayrılma)"""
            if not self.is_running or self.is_paused:
                return
                
            try:
                # Yeni üye katıldı mı?
                if event.user_joined or event.user_added:
                    await self._handle_user_joined(event)
                # Üye ayrıldı mı?
                elif event.user_left or event.user_kicked:
                    await self._handle_user_left(event)
            except Exception as e:
                self.stats["errors"] += 1
                self.bot.error_handler.log_error(
                    "Chat action hatası",
                    str(e),
                    {'event_type': 'chat_action', 'chat_id': getattr(event, 'chat_id', None)}
                )
                
        @self.bot.client.on(events.CallbackQuery())
        async def callback_query_handler(event):
            """Buton tıklamalarını işler"""
            if not self.is_running or self.is_paused:
                return
                
            try:
                await self._handle_callback_query(event)
            except Exception as e:
                self.stats["errors"] += 1
                self.bot.error_handler.log_error(
                    "Callback query hatası",
                    str(e),
                    {'event_type': 'callback_query'}
                )
                
        # Handler'ların kurulduğunu işaretle
        self._handlers_setup = True
        logger.info("Telethon event handler'ları başarıyla ayarlandı")
    
    async def handle_private_message(self, event) -> None:
        """
        Özel mesajları yanıtlar ve işler.
        
        Args:
            event: Telethon mesaj olayı
        """
        try:
            user = await event.get_sender()
            if user is None:
                logger.debug("Özel mesaj için kullanıcı bilgisi alınamadı")
                return
                
            user_id = user.id
            
            # Bot veya yönetici mi kontrol et - güvenli kontroller
            is_bot = hasattr(user, 'bot') and user.bot
            username = getattr(user, 'username', "")
            
            # Kullanıcı adında "Bot" kelimesi geçiyorsa bot olarak işaretle
            has_bot_in_name = username and "bot" in username.lower()
            
            is_admin = hasattr(user, 'admin_rights') and user.admin_rights
            is_creator = hasattr(user, 'creator') and user.creator
            
            if is_bot or has_bot_in_name or is_admin or is_creator:
                logger.info(f"❌ Özel mesaj atlandı: {username or user_id} (Bot/Yönetici)")
                return
                
            # Mesaj içeriği
            message_text = getattr(event.message, 'text', "")
            
            # Komut kontrolü
            if message_text.startswith('/'):
                await self._handle_command(event, user_id, username, message_text)
                return
            
            # Daha önce davet edilmiş mi?
            is_invited = await self._run_db_method('is_invited', user_id)
            
            if is_invited:
                # Yönlendirme mesajı gönder
                redirect = random.choice(self.bot.redirect_messages)
                await event.reply(redirect)
                logger.info(f"↩️ Kullanıcı gruba yönlendirildi: {username or user_id}")
                return
            
            # Davet mesajı gönder
            invite_message = self._create_invite_message()
            await event.reply(invite_message)
            
            # Kullanıcıyı işaretle
            await self._run_db_method('mark_as_invited', user_id)
            
            logger.info(f"✅ Grup daveti gönderildi: {username or user_id}")
            self.stats["private_messages"] += 1
            
        except errors.FloodWaitError as e:
            # Özel işlem
            wait_time = e.seconds + random.randint(5, 15)
            self.bot.error_handler.handle_flood_wait(
                "FloodWaitError",
                f"Özel mesaj yanıtı için {wait_time} saniye bekleniyor",
                {'wait_time': wait_time, 'operation': 'private_message'}
            )
            await asyncio.sleep(wait_time)
        except Exception as e:
            self.stats["errors"] += 1
            self.bot.error_handler.log_error("Özel mesaj hatası", str(e))
    
    async def handle_group_reply(self, event) -> None:
        """
        Grup yanıtlarını işler ve cevaplar.
        
        Args:
            event: Telethon reply olayı
        """
        try:
            # Throttling kontrolü
            should_wait, wait_time = self.bot.error_handler.should_throttle("GetUsersRequest")
            if should_wait:
                logger.debug(f"GetUsersRequest için {wait_time}s bekliyor (throttling)")
                return
                
            # Yanıtlanan mesajı al
            replied_msg = await event.get_reply_message()
            
            # Yanıtlanan mesaj bizim mesajımız mı?
            if replied_msg and replied_msg.sender_id == (await self.bot.client.get_me()).id:
                # İçerik analizi
                message_text = event.message.text.lower() if hasattr(event.message, 'text') else ""
                
                # Yanıt tipini belirle
                if any(word in message_text for word in ["teşekkür", "sağol", "thank", "iyisin"]):
                    response = random.choice(self.bot.friendly_responses)
                elif any(word in message_text for word in ["nasıl", "yardım", "nerden", "nerede", "help"]):
                    response = random.choice(self.bot.help_responses)
                else:
                    # Varsayılan olarak flörtöz yanıt
                    response = random.choice(self.bot.flirty_responses)
                
                # Yanıtı gönder
                await event.reply(response)
                logger.info(f"💬 Bot yanıtı gönderildi: {event.chat.title}")
                self.stats["replies"] += 1
                
        except errors.FloodWaitError as e:
            # Özel işlem
            wait_time = e.seconds + random.randint(5, 15)
            self.bot.error_handler.handle_flood_wait(
                "FloodWaitError",
                f"Grup yanıtı için {wait_time} saniye bekleniyor",
                {'wait_time': wait_time, 'operation': 'group_reply'}
            )
            await asyncio.sleep(wait_time)
        except Exception as e:
            error_msg = str(e)
            self.stats["errors"] += 1
            self.bot.error_handler.log_error("Grup yanıt hatası", error_msg)
            
            # Eğer 'wait' kelimesi varsa ve GetUsersRequest ile ilgiliyse özel işle
            if "wait" in error_msg.lower() and "GetUsersRequest" in error_msg:
                explanation = self.bot.error_handler.explain_error(error_msg)
                logger.info(f"ℹ️ Bilgi: {explanation}")
    
    async def track_active_users(self, event) -> None:
        """
        Aktif kullanıcıları takip eder ve tekrar eden aktiviteleri filtreler.
        
        Bu metot, gruplarda aktif kullanıcıları tespit eder, veritabanına
        kaydeder ve botun davet potansiyelini artıracak kullanıcıları belirler.
        
        Args:
            event: Telethon mesaj olayı
        """
        try:
            # Throttling kontrolü
            should_wait, wait_time = self.bot.error_handler.should_throttle("GetUsersRequest")
            if should_wait:
                logger.debug(f"GetUsersRequest için {wait_time}s bekliyor (throttling)")
                return
                
            user = await event.get_sender()
            if not user:
                logger.debug("Kullanıcı bilgisi alınamadı")
                return
                
            user_id = getattr(user, 'id', None)
            if not user_id:
                logger.debug("Kullanıcı ID'si alınamadı")
                return
                
            username = getattr(user, 'username', None)
            first_name = getattr(user, 'first_name', None)
            last_name = getattr(user, 'last_name', None)
            
            user_info = f"@{username}" if username else f"ID:{user_id}"
            full_name = " ".join(filter(None, [first_name, last_name]))
            if full_name:
                user_info = f"{user_info} ({full_name})"
            
            # Bot veya yönetici mi kontrol et - güvenli kontrollerle
            is_bot = hasattr(user, 'bot') and user.bot
            
            # Kullanıcı adında "Bot" kelimesi geçiyorsa bot olarak işaretle
            has_bot_in_name = username and "bot" in username.lower()
            
            is_admin = hasattr(user, 'admin_rights') and user.admin_rights
            is_creator = hasattr(user, 'creator') and user.creator
            
            if is_bot or has_bot_in_name or is_admin or is_creator:
                logger.debug(f"Bot/Admin kullanıcısı atlandı: {user_info}")
                return
            
            # Grup bilgisini al
            chat_id = event.chat_id
            chat_title = getattr(event.chat, 'title', str(chat_id))
            
            # Önce veritabanında kullanıcı kaydı var mı kontrol et
            is_in_db = await self._check_user_in_db(user_id)
                
            # Bu kullanıcı için son görüntüleme zamanını kontrol et
            current_time = asyncio.get_event_loop().time()
            last_displayed = self.last_user_logs.get(user_info, 0)
            
            # En az 4 saat (14400 saniye) geçmedikçe aynı kullanıcıyı tekrar gösterme
            recently_displayed = current_time - last_displayed < 14400
                
            # Kullanıcı daha önce görüntülendi mi?
            if user_info in self.displayed_users and recently_displayed:
                # Loglama seviyesini düşür - debug modunda veya veritabanında yoksa göster
                if self.bot.debug_mode and not is_in_db:
                    print(self.bot.terminal_format['user_activity_exists'].format(user_info))
                    # Açıklama ekle
                    print(f"{Fore.BLUE}ℹ️ 'Tekrar aktivite' kullanıcının farklı gruplarda veya aynı grupta tekrar mesaj gönderdiği anlamına gelir.{Style.RESET_ALL}")
                return
                
            # Kullanıcı önceden veritabanında yoksa veya hiç gösterilmemişse göster
            if not is_in_db or not recently_displayed:
                # Kullanıcıyı göster ve listeye ekle
                self.displayed_users.add(user_info)
                self.last_user_logs[user_info] = current_time
                
                # Veritabanı kontrolü
                was_invited = await self._run_db_method('is_invited', user_id)
                was_recently_invited = await self._run_db_method('was_recently_invited', user_id, 4)
                
                invite_status = ""
                if was_invited:
                    invite_status = " (✓ Davet edildi)"
                elif was_recently_invited:
                    invite_status = " (⏱️ Son 4 saatte davet edildi)" 
                
                # Konsol çıktısı
                if not is_in_db:
                    # Yeni kullanıcı
                    print(self.bot.terminal_format['user_activity_new'].format(
                        f"{user_info}{invite_status}"
                    ))
                    # Açıklama ekle (bir kez)
                    if "user_activity_explained" not in self.bot.__dict__:
                        print(f"{Fore.CYAN}ℹ️ 'Yeni kullanıcı aktivitesi' veritabanında olmayan bir kullanıcıyı belirtir.{Style.RESET_ALL}")
                        self.bot.user_activity_explained = True
                    
                    self.stats["new_users"] += 1
                else:
                    # Veritabanında olan ama uzun süre görülmeyen kullanıcı
                    print(self.bot.terminal_format['user_activity_reappear'].format(
                        f"{user_info}{invite_status}"
                    ))
                
                # Kullanıcı henüz veritabanında yoksa ekle
                if not is_in_db:
                    # Genişletilmiş kullanıcı verisi ile ekle
                    await self._add_user_to_db(
                        user_id=user_id,
                        username=username,
                        first_name=first_name,
                        last_name=last_name,
                        source_group=chat_title
                    )
                else:
                    # Sadece aktivite kaydı güncelle
                    await self._run_db_method('update_user_activity', user_id)
                
        except errors.FloodWaitError as e:
            wait_time = e.seconds + random.randint(5, 15)
            self.bot.error_handler.handle_flood_wait(
                "FloodWaitError", 
                f"Kullanıcı takip için {wait_time}s bekleniyor",
                {'wait_time': wait_time, 'operation': 'track_users'}
            )
            await asyncio.sleep(wait_time)
        except Exception as e:
            error_msg = str(e)
            self.stats["errors"] += 1
            self.bot.error_handler.log_error("Kullanıcı takip hatası", error_msg)
            
            # Açıklama ekle
            if "wait" in error_msg.lower() and "GetUsersRequest" in error_msg:
                explanation = self.bot.error_handler.explain_error(error_msg)
                logger.info(f"ℹ️ Bilgi: {explanation}")
    
    #
    # YENİ HANDLER METODLARI
    #
    
    async def _handle_user_joined(self, event) -> None:
        """
        Gruba yeni katılan kullanıcıları karşılar.
        
        Args:
            event: Telethon chat action olayı
        """
        try:
            # Kullanıcı bilgisini al
            user_id = event.user_id
            user = await self.bot.client.get_entity(user_id)
            
            if not user:
                return
                
            # Bot ise işleme
            if getattr(user, 'bot', False):
                return
                
            # Grup bilgisi
            chat = await event.get_chat()
            chat_title = getattr(chat, 'title', str(event.chat_id))
            
            # Kullanıcıyı veritabanına ekle/güncelle
            username = getattr(user, 'username', None)
            first_name = getattr(user, 'first_name', None)
            last_name = getattr(user, 'last_name', None)
            
            await self._add_user_to_db(
                user_id=user_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                source_group=chat_title
            )
            
            logger.info(f"👋 Yeni kullanıcı gruba katıldı: {username or user_id} -> {chat_title}")
            
            # Hoş geldin mesajı - konuma bağlı olarak
            if hasattr(self.bot, 'welcome_new_users') and self.bot.welcome_new_users:
                welcome_message = random.choice(self.bot.welcome_messages)
                welcome_message = welcome_message.format(name=first_name or "Merhaba")
                
                await self.bot.client.send_message(
                    event.chat_id,
                    welcome_message,
                    reply_to=event.action_message.id
                )
                logger.info(f"👋 Hoş geldin mesajı gönderildi: {chat_title}")
                
        except errors.FloodWaitError as e:
            wait_time = e.seconds + random.randint(5, 15)
            await asyncio.sleep(wait_time)
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Kullanıcı katılım hatası: {str(e)}")
    
    async def _handle_user_left(self, event) -> None:
        """
        Gruptan ayrılan kullanıcıları işler.
        
        Args:
            event: Telethon chat action olayı
        """
        try:
            # Kullanıcı bilgisini al
            user_id = event.user_id
            
            # Veritabanında güncelle
            if hasattr(self.bot.db, 'mark_user_left_group'):
                await self._run_db_method('mark_user_left_group', user_id, event.chat_id)
            
            logger.info(f"👋 Kullanıcı gruptan ayrıldı: {user_id}")
            
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Kullanıcı ayrılma hatası: {str(e)}")
    
    async def _handle_callback_query(self, event) -> None:
        """
        InlineButton tıklamalarını işler.
        
        Args:
            event: Telethon callback query olayı
        """
        try:
            # Veriyi al
            data = event.data.decode('utf-8') if hasattr(event, 'data') else None
            if not data:
                return
                
            # Tıklayan kullanıcı bilgisi
            sender = await event.get_sender()
            user_id = getattr(sender, 'id', None)
            username = getattr(sender, 'username', None)
            
            logger.info(f"🔘 Callback: {data} - Kullanıcı: {username or user_id}")
            
            # Veri tipine göre işle
            if data.startswith('join_'):
                group_id = data.split('_')[1]
                await self._handle_join_button(event, user_id, group_id)
            elif data.startswith('info_'):
                info_type = data.split('_')[1]
                await self._handle_info_button(event, user_id, info_type)
            else:
                # Bilinmeyen veri
                await event.answer("İşlem anlaşılamadı")
            
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Callback query hatası: {str(e)}")
    
    async def _handle_command(self, event, user_id: int, username: Optional[str], cmd: str) -> None:
        """
        Kullanıcı komutlarını işler.
        
        Args:
            event: Telethon mesaj olayı
            user_id: Kullanıcı ID
            username: Kullanıcı adı (opsiyonel)
            cmd: Komut metni
        """
        cmd_parts = cmd.split()
        command = cmd_parts[0].lower()
        
        try:
            # Temel komutlar
            if command == '/start':
                # Karşılama mesajı
                welcome = random.choice(self.bot.welcome_messages)
                first_name = getattr(event.sender, 'first_name', "Değerli kullanıcı")
                welcome = welcome.format(name=first_name)
                
                await event.reply(welcome)
                
                # Kullanıcı henüz davet edilmediyse davet mesajı gönder
                is_invited = await self._run_db_method('is_invited', user_id)
                if not is_invited:
                    invite_message = self._create_invite_message()
                    await self.bot.client.send_message(user_id, invite_message)
                    await self._run_db_method('mark_as_invited', user_id)
                
                logger.info(f"🤖 /start komutu: {username or user_id}")
                
            elif command == '/help':
                await event.reply(self.bot.help_message)
                logger.info(f"🤖 /help komutu: {username or user_id}")
                
            elif command == '/groups':
                group_list = "\n".join([f"• {g}" for g in self.bot.config.TARGET_GROUPS])
                await event.reply(f"📋 Gruplarımız:\n\n{group_list}")
                logger.info(f"🤖 /groups komutu: {username or user_id}")
            
            # Diğer komutları user_handler'a ilet
            else:
                await self.user_handler.process_command(event, command, cmd_parts[1:])
                
        except errors.FloodWaitError as e:
            wait_time = e.seconds + random.randint(5, 15)
            await asyncio.sleep(wait_time)
            
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Komut işleme hatası: {str(e)}")
    
    async def _handle_join_button(self, event, user_id: int, group_id: str) -> None:
        """
        Gruba katılım butonlarını işler.
        
        Args:
            event: Telethon callback query olayı
            user_id: Kullanıcı ID
            group_id: Grup ID veya username
        """
        try:
            # Butona tıklandığını bildir
            await event.answer("Gruba yönlendiriliyorsunuz...")
            
            # Grup linki oluştur ve mesaj gönder
            group_username = group_id if group_id.startswith('@') else f"@{group_id}"
            link_message = f"🔗 Gruba katılmak için tıklayın: {group_username}"
            
            await self.bot.client.send_message(user_id, link_message)
            logger.info(f"🔘 Join button: {user_id} -> {group_id}")
            
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Join button hatası: {str(e)}")
    
    async def _handle_info_button(self, event, user_id: int, info_type: str) -> None:
        """
        Bilgi butonlarını işler.
        
        Args:
            event: Telethon callback query olayı
            user_id: Kullanıcı ID
            info_type: Bilgi tipi
        """
        try:
            # Butona tıklandığını bildir
            await event.answer(f"{info_type.capitalize()} bilgisi gönderiliyor...")
            
            if info_type == "rules":
                await self.bot.client.send_message(user_id, self.bot.rules_message)
            elif info_type == "about":
                await self.bot.client.send_message(user_id, self.bot.about_message)
            else:
                await self.bot.client.send_message(user_id, "Bu bilgi henüz mevcut değil.")
                
            logger.info(f"🔘 Info button: {user_id} -> {info_type}")
            
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Info button hatası: {str(e)}")
    
    #
    # YARDIMCI METOTLAR
    #

    async def _check_user_in_db(self, user_id: int) -> bool:
        """
        Kullanıcının veritabanında olup olmadığını kontrol eder.
        
        Args:
            user_id: Kontrolü yapılacak kullanıcı ID
            
        Returns:
            bool: Kullanıcı veritabanında varsa True
        """
        try:
            # UserService entegrasyonu
            if hasattr(self.bot, 'user_service'):
                user_info = await self.bot.user_service.get_user_info(user_id)
                return user_info is not None
            
            # Doğrudan veritabanı bağlantısı
            elif hasattr(self.bot.db, 'connection'):
                with self.bot.db.connection:
                    cursor = self.bot.db.connection.execute(
                        "SELECT user_id FROM users WHERE user_id = ?", 
                        (user_id,)
                    )
                    return cursor.fetchone() is not None
            
            # Alternatif metodlar
            elif hasattr(self.bot.db, 'check_user_exists'):
                return self.bot.db.check_user_exists(user_id)
                
            return False
            
        except Exception as e:
            logger.error(f"Kullanıcı DB kontrolü hatası: {str(e)}")
            return False
            
    async def _add_user_to_db(self, user_id: int, username: Optional[str] = None, 
                     first_name: Optional[str] = None, last_name: Optional[str] = None,
                     source_group: Optional[str] = None) -> bool:
        """
        Kullanıcıyı veritabanına ekler.
        
        Args:
            user_id: Kullanıcı ID
            username: Kullanıcı adı (opsiyonel)
            first_name: İlk adı (opsiyonel)
            last_name: Soyadı (opsiyonel)
            source_group: Kullanıcının geldiği grup (opsiyonel)
            
        Returns:
            bool: İşlem başarılı ise True
        """
        try:
            # UserService entegrasyonu
            if hasattr(self.bot, 'user_service'):
                return await self.bot.user_service.add_user(
                    user_id=user_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    source_group=source_group
                )
            
            # Doğrudan veritabanı methodları
            elif hasattr(self.bot.db, 'add_user'):
                if asyncio.iscoroutinefunction(self.bot.db.add_user):
                    return await self.bot.db.add_user(user_id, username, first_name, last_name, source_group)
                else:
                    return self.bot.db.add_user(user_id, username, first_name, last_name, source_group)
                    
            # Basit durum - sadece temel bilgileri ekle
            elif hasattr(self.bot.db, 'add_user_basic'):
                return self.bot.db.add_user_basic(user_id, username)
                
            return False
            
        except Exception as e:
            logger.error(f"Kullanıcı DB ekleme hatası: {str(e)}")
            return False
    
    async def _run_db_method(self, method_name: str, *args, **kwargs) -> Any:
        """
        Veritabanı methodunu asenkron olarak çalıştırır.
        
        Args:
            method_name: Çağrılacak method adı
            *args: Pozisyonel argumentler
            **kwargs: Keyword argumentler
            
        Returns:
            Any: Method sonucu
        """
        try:
            # UserService yoluyla çalıştır
            if hasattr(self.bot, 'user_service') and hasattr(self.bot.user_service, method_name):
                method = getattr(self.bot.user_service, method_name)
                if asyncio.iscoroutinefunction(method):
                    return await method(*args, **kwargs)
                else:
                    return method(*args, **kwargs)
            
            # Doğrudan veritabanından çalıştır
            elif hasattr(self.bot.db, method_name):
                method = getattr(self.bot.db, method_name)
                if asyncio.iscoroutinefunction(method):
                    return await method(*args, **kwargs)
                else:
                    return method(*args, **kwargs)
            
            return None
            
        except Exception as e:
            logger.error(f"DB metod çalıştırma hatası ({method_name}): {str(e)}")
            return None
    
    async def _cleanup_displayed_users(self) -> None:
        """
        Görüntülenen kullanıcı önbelleğini temizler.
        """
        try:
            # 24 saatten daha eski kayıtları temizle
            current_time = asyncio.get_event_loop().time()
            expired_users = []
            
            # 24 saat öncesinden daha eski kayıtları temizle
            for user_info, timestamp in list(self.last_user_logs.items()):
                if current_time - timestamp > 86400:  # 24 saat
                    expired_users.append(user_info)
            
            # Temizleme işlemi
            for user_info in expired_users:
                if user_info in self.last_user_logs:
                    del self.last_user_logs[user_info]
                if user_info in self.displayed_users:
                    self.displayed_users.remove(user_info)
            
            logger.debug(f"Kullanıcı önbelleği temizlendi: {len(expired_users)} kayıt silindi")
            
        except Exception as e:
            logger.error(f"Kullanıcı önbelleği temizleme hatası: {str(e)}")

    def _create_invite_message(self) -> str:
        """
        Davet mesajını oluşturur.
        
        Returns:
            str: Oluşturulan davet mesajı
        """
        try:
            if hasattr(self.bot, 'create_invite_message') and callable(self.bot.create_invite_message):
                return self.bot.create_invite_message()
            
            # Bot nesnesi davet mesajı oluşturamıyorsa, kendi mantığımızla oluşturalım
            greeting = random.choice([
                "Merhaba! 👋",
                "Selam! 😊",
                "Hoş geldiniz! 🌟",
                "Merhabalar! ✨"
            ])
            
            intro = random.choice([
                "Bizimle iletişimde olduğun için teşekkürler.",
                "Bizimle bağlantı kurduğun için teşekkürler.",
                "Mesajın için teşekkür ederim."
            ])
            
            groups = "\n".join([f"👉 {group}" for group in self.bot.config.TARGET_GROUPS])
            
            invite = random.choice([
                "Seni gruplarımıza davet etmekten mutluluk duyarız:",
                "Aşağıdaki gruplara katılabilirsin:",
                "Seni aramızda görmek isteriz:"
            ])
            
            outro = random.choice([
                "Görüşmek üzere!",
                "Seni gruplarda görmek dileğiyle!",
                "Katılımını bekliyoruz!"
            ])
            
            return f"{greeting} {intro}\n\n{invite}\n\n{groups}\n\n{outro}"
            
        except Exception as e:
            logger.error(f"Davet mesajı oluşturma hatası: {str(e)}")
            return "Merhaba! Telegram gruplarımıza katılabilirsiniz."

    def _update_stats(self) -> None:
        """
        İstatistik verilerini günceller.
        """
        uptime_seconds = (datetime.now() - self.stats["start_time"]).total_seconds() if self.stats["start_time"] else 0
        self.stats["uptime_hours"] = uptime_seconds / 3600
        
        # Ortalama mesaj hızı (saat başına)
        if uptime_seconds > 3600:
            self.stats["messages_per_hour"] = self.stats["total_messages"] / self.stats["uptime_hours"]
        else:
            self.stats["messages_per_hour"] = self.stats["total_messages"]

    def get_status(self) -> Dict[str, Any]:
        """
        Servis durumunu içeren bir sözlük döndürür.
        
        Returns:
            Dict[str, Any]: Servis durum bilgileri
        """
        return {
            "running": self.is_running,
            "paused": self.is_paused,
            "total_messages": self.stats["total_messages"],
            "private_messages": self.stats["private_messages"],
            "group_messages": self.stats["group_messages"],
            "new_users": self.stats["new_users"],
            "errors": self.stats["errors"],
            "last_activity": self.stats["last_activity"].strftime("%H:%M:%S") if self.stats["last_activity"] else "Hiç"
        }
        
    def get_statistics(self) -> Dict[str, Any]:
        """
        Detaylı istatistik verilerini döndürür.
        
        Returns:
            Dict[str, Any]: İstatistik verilerini içeren sözlük
        """
        self._update_stats()
        
        return {
            "running": self.is_running,
            "paused": self.is_paused,
            "start_time": self.stats["start_time"].strftime("%Y-%m-%d %H:%M:%S") if self.stats["start_time"] else None,
            "uptime_hours": round(self.stats["uptime_hours"], 2) if "uptime_hours" in self.stats else 0,
            "total_messages": self.stats["total_messages"],
            "private_messages": self.stats["private_messages"],
            "group_messages": self.stats["group_messages"],
            "new_users": self.stats["new_users"],
            "replies": self.stats["replies"],
            "errors": self.stats["errors"],
            "messages_per_hour": round(self.stats.get("messages_per_hour", 0), 2),
            "cached_users": len(self.displayed_users),
            "last_activity": self.stats["last_activity"].strftime("%Y-%m-%d %H:%M:%S") if self.stats["last_activity"] else None
        }