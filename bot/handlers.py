"""
Telegram mesaj işleyicileri
"""
import logging
import asyncio
import random
from telethon import events, errors
from colorama import Fore, Style

logger = logging.getLogger(__name__)

class MessageHandlers:
    """Telegram mesaj işleyicileri"""
    
    def __init__(self, bot):
        """Bot nesnesine referans"""
        self.bot = bot
        # Kullanıcı aktivite izleme için
        self.displayed_users = set()
        self.last_user_logs = {}
        
    def setup_handlers(self):
        """Telethon mesaj işleyicilerini ayarlar"""
        @self.bot.client.on(events.NewMessage(incoming=True))
        async def message_handler(event):
            try:
                # Özel mesaj mı?
                if event.is_private:
                    await self.handle_private_message(event)
                # Grup mesajı mı?
                else:
                    # Yanıt mı?
                    if (event.is_reply):
                        await self.handle_group_reply(event)
                    # Normal mesaj mı?
                    else:
                        await self.track_active_users(event)
            except Exception as e:
                self.bot.error_handler.log_error(
                    "Mesaj işleme hatası",
                    str(e),
                    {'event_type': 'message', 'chat_id': event.chat_id}
                )
    
    async def handle_private_message(self, event) -> None:
        """Özel mesajları yanıtlar"""
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
            
            # Daha önce davet edilmiş mi?
            if self.bot.db.is_invited(user_id):
                # Yönlendirme mesajı gönder
                redirect = random.choice(self.bot.redirect_messages)
                await event.reply(redirect)
                logger.info(f"↩️ Kullanıcı gruba yönlendirildi: {username or user_id}")
                return
            
            # Davet mesajı gönder
            invite_message = self.bot.create_invite_message()
            await event.reply(invite_message)
            
            # Kullanıcıyı işaretle
            self.bot.db.mark_as_invited(user_id)
            logger.info(f"✅ Grup daveti gönderildi: {username or user_id}")
            
        except errors.FloodWaitError as e:
            # Özel işlem
            wait_time = e.seconds + random.randint(5, 15)
            self.bot.error_handler.log_error(
                "FloodWaitError",
                f"Özel mesaj yanıtı için {wait_time} saniye bekleniyor",
                {'wait_time': wait_time}
            )
            await asyncio.sleep(wait_time)
        except Exception as e:
            self.bot.error_handler.log_error("Özel mesaj hatası", str(e))
    
    async def handle_group_reply(self, event) -> None:
        """Grup yanıtlarını işler"""
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
                # Flörtöz yanıt gönder
                flirty_response = random.choice(self.bot.flirty_responses)
                await event.reply(flirty_response)
                logger.info(f"💬 Flörtöz yanıt gönderildi: {event.chat.title}")
                
        except errors.FloodWaitError as e:
            # Özel işlem
            wait_time = e.seconds + random.randint(5, 15)
            self.bot.error_handler.log_error(
                "FloodWaitError",
                f"Grup yanıtı için {wait_time} saniye bekleniyor (caused by GetUsersRequest)",
                {'wait_time': wait_time}
            )
        except Exception as e:
            error_msg = str(e)
            self.bot.error_handler.log_error("Grup yanıt hatası", error_msg)
            # Eğer 'wait' kelimesi varsa ve GetUsersRequest ile ilgiliyse özel işle
            if "wait" in error_msg.lower() and "GetUsersRequest" in error_msg:
                explanation = self.bot.error_handler.explain_error(error_msg)
                logger.info(f"ℹ️ Bilgi: {explanation}")
    
    async def track_active_users(self, event) -> None:
        """Aktif kullanıcıları takip eder ve tekrar eden aktiviteleri filtreler"""
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
            user_info = f"@{username}" if username else f"ID:{user_id}"
            
            # Bot veya yönetici mi kontrol et - güvenli kontrollerle
            is_bot = hasattr(user, 'bot') and user.bot
            
            # Kullanıcı adında "Bot" kelimesi geçiyorsa bot olarak işaretle
            has_bot_in_name = username and "bot" in username.lower()
            
            is_admin = hasattr(user, 'admin_rights') and user.admin_rights
            is_creator = hasattr(user, 'creator') and user.creator
            
            if is_bot or has_bot_in_name or is_admin or is_creator:
                logger.debug(f"Bot/Admin kullanıcısı atlandı: {user_info}")
                return
            
            # Önce veritabanında kullanıcı kaydı var mı kontrol et
            is_in_db = False
            try:
                # Kullanıcı databasede var mı diye kontrol et
                with self.bot.db.connection:
                    cursor = self.bot.db.connection.execute(
                        "SELECT user_id FROM users WHERE user_id = ?", 
                        (user_id,)
                    )
                    is_in_db = cursor.fetchone() is not None
            except Exception as e:
                self.bot.error_handler.log_error("Kullanıcı DB kontrolü", str(e))
                
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
                was_invited = self.bot.db.is_invited(user_id)
                was_recently_invited = self.bot.db.was_recently_invited(user_id, 4)
                
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
                else:
                    # Veritabanında olan ama uzun süre görülmeyen kullanıcı
                    print(self.bot.terminal_format['user_activity_reappear'].format(
                        f"{user_info}{invite_status}"
                    ))
                
                # Kullanıcı henüz veritabanında yoksa ekle
                if not is_in_db:
                    self.bot.db.add_user(user_id, username)
                
        except errors.FloodWaitError as e:
            wait_time = e.seconds + random.randint(5, 15)
            self.bot.error_handler.log_error(
                "FloodWaitError", 
                f"Kullanıcı takip için {wait_time}s bekleniyor",
                {'wait_time': wait_time}
            )
        except Exception as e:
            error_msg = str(e)
            self.bot.error_handler.log_error("Kullanıcı takip hatası", error_msg)
            
            # Açıklama ekle
            if "wait" in error_msg.lower() and "GetUsersRequest" in error_msg:
                explanation = self.bot.error_handler.explain_error(error_msg)
                logger.info(f"ℹ️ Bilgi: {explanation}")