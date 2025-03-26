"""
Mesaj işleyicileri modülü
"""
import logging
import random
import time
from datetime import datetime

from colorama import Fore, Style, init
# Initialize colorama
init(autoreset=True)

from telethon import events

logger = logging.getLogger(__name__)

def setup_message_handlers(bot):
    """
    Telethon mesaj işleyicilerini ayarlar
    
    Args:
        bot: Bot nesnesi
    """
    # Hata sayaçlarını başlat
    if not hasattr(bot, 'error_counter'):
        bot.error_counter = {}
        
    # Kullanıcı aktivite takibi için set
    if not hasattr(bot, 'displayed_users'):
        bot.displayed_users = set()
        
    @bot.client.on(events.NewMessage(incoming=True))
    async def message_handler(event):
        try:
            # Kapatılıyor mu kontrol et
            if not bot.is_running or bot._shutdown_event.is_set():
                return
                
            # Özel mesaj mı?
            if event.is_private:
                await handle_private_message(bot, event)
            # Grup mesajı mı?
            else:
                # Yanıt mı?
                if (event.is_reply):
                    await handle_group_reply(bot, event)
                # Normal mesaj mı?
                else:
                    await track_active_users(bot, event)
                    
        except Exception as e:
            error_key = f"message_handler_{str(e)[:20]}"
            
            # Tekrarlanan hataları filtreleme
            if error_key not in bot.error_counter:
                bot.error_counter[error_key] = 0
                
            bot.error_counter[error_key] += 1
            
            # İlk hata veya her 5 hatada bir göster
            if bot.error_counter[error_key] <= 1 or bot.error_counter[error_key] % 5 == 0:
                logger.error(f"Mesaj işleme hatası: {str(e)}")

async def handle_private_message(bot, event):
    """Özel mesajları işler"""
    try:
        # Kapatılıyor mu kontrol et
        if not bot.is_running or bot._shutdown_event.is_set():
            return
            
        user = await event.get_sender()
        if user is None:
            return
            
        user_id = user.id
        
        # Bot veya yönetici mi kontrol et
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
        if bot.db.is_invited(user_id):
            # Yönlendirme mesajı gönder
            try:
                redirect = random.choice(bot.redirect_messages)
                await event.reply(redirect)
                logger.info(f"↩️ Kullanıcı gruba yönlendirildi: {username or user_id}")
            except Exception as e:
                log_filtered_error(bot, f"redirect_error_{str(e)[:20]}", 
                                   f"Yönlendirme mesajı hatası: {str(e)}")
            return
        
        # Davet mesajı gönder
        try:
            # Bot üzerinden davet mesajı oluştur
            if hasattr(bot, 'create_invite_message'):
                invite_message = bot.create_invite_message()
            # User handler varsa oradan oluştur
            elif hasattr(bot, 'user_handler') and hasattr(bot.user_handler, '_create_invite_message'):
                invite_message = bot.user_handler._create_invite_message()
            else:
                # Hiçbiri yoksa basit bir mesaj oluştur
                group_links = "\n".join([f"• t.me/{link}" for link in bot.group_links])
                invite_message = f"Merhaba! Lütfen grubumuza katılın: {group_links}"
                
            # Mesajı gönder
            await event.reply(invite_message)
            
            # Kullanıcıyı işaretle
            bot.db.mark_as_invited(user_id)
            logger.info(f"✅ Grup daveti gönderildi: {username or user_id}")
            
        except Exception as e:
            log_filtered_error(bot, f"invite_error_{str(e)[:20]}", 
                               f"Davet gönderme hatası: {str(e)}")
            
    except Exception as e:
        log_filtered_error(bot, f"pm_handler_{str(e)[:20]}", 
                          f"Özel mesaj yanıtlama hatası: {str(e)}")

async def handle_group_reply(bot, event):
    """Grup yanıtlarını işler"""
    try:
        # Kapatılıyor mu kontrol et
        if not bot.is_running or bot._shutdown_event.is_set():
            return
            
        # Yanıtlanan mesajı al
        replied_msg = await event.get_reply_message()
        
        # Yanıtlanan mesaj bizim mesajımız mı?
        if replied_msg and replied_msg.sender_id == (await bot.client.get_me()).id:
            # Flörtöz yanıt gönder
            if hasattr(bot, 'flirty_responses') and bot.flirty_responses:
                flirty_response = random.choice(bot.flirty_responses)
                await event.reply(flirty_response)
                logger.info(f"💬 Flörtöz yanıt gönderildi: {event.chat.title}")
            else:
                logger.debug("Flörtöz yanıt listesi bulunamadı")
            
    except Exception as e:
        log_filtered_error(bot, f"group_reply_{str(e)[:20]}", 
                          f"Grup yanıt hatası: {str(e)}")

async def track_active_users(bot, event):
    """Aktif kullanıcıları takip eder"""
    try:
        # Kapatılıyor mu kontrol et
        if not bot.is_running or bot._shutdown_event.is_set():
            return
            
        # Göndereni al
        user = await event.get_sender()
        if not user:
            return
            
        user_id = getattr(user, 'id', None)
        if not user_id:
            return
            
        username = getattr(user, 'username', None)
        user_info = f"@{username}" if username else f"ID:{user_id}"
        
        # Bot veya yönetici mi kontrol et
        is_bot = hasattr(user, 'bot') and user.bot
        has_bot_in_name = username and "bot" in username.lower()  
        is_admin = hasattr(user, 'admin_rights') and user.admin_rights
        is_creator = hasattr(user, 'creator') and user.creator
        
        if is_bot or has_bot_in_name or is_admin or is_creator:
            return
        
        # Tutarlı kullanıcı kimliği için key
        user_key = user_id  # user_id daima eşsizdir, user_info daha az güvenilir
        
        # Kullanıcı daha önce gösterildi mi?
        if user_key in bot.displayed_users:
            # Loglama seviyesini düşür
            if bot.debug_mode:
                if hasattr(bot, 'terminal_format') and 'user_activity_exists' in bot.terminal_format:
                    print(bot.terminal_format['user_activity_exists'].format(user_info))
                else:
                    print(f"{Fore.BLUE}🔄 Tekrar aktivite: {user_info}{Style.RESET_ALL}")
            return
            
        # Önceden veritabanında kontrol
        is_in_db = False
        try:
            with bot.db.connection:
                cursor = bot.db.connection.execute(
                    "SELECT user_id FROM users WHERE user_id = ?", 
                    (user_id,)
                )
                is_in_db = cursor.fetchone() is not None
        except Exception as e:
            log_filtered_error(bot, f"db_check_{str(e)[:20]}", 
                              f"Kullanıcı veritabanı kontrolü hatası: {str(e)}")
        
        # Yeni kullanıcıyı göster ve listeye ekle
        bot.displayed_users.add(user_key)
        
        # Yeni kullanıcı ya da debug modda göster
        if not is_in_db:
            # Veritabanı kontrolü - try catch ile koruma
            try:
                was_invited = bot.db.is_invited(user_id)
                was_recently_invited = bot.db.was_recently_invited(user_id, 4)
                
                invite_status = ""
                if was_invited:
                    invite_status = " (✓ Davet edildi)"
                elif was_recently_invited:
                    invite_status = " (⏱️ Son 4 saatte davet edildi)" 
                
                # Konsol çıktısı
                if hasattr(bot, 'terminal_format') and 'user_activity_new' in bot.terminal_format:
                    print(bot.terminal_format['user_activity_new'].format(
                        f"{user_info}{invite_status}"
                    ))
                else:
                    print(f"{Fore.CYAN}👁️ Yeni kullanıcı aktivitesi: {user_info}{invite_status}{Style.RESET_ALL}")
                
                # Kullanıcıyı veritabanına ekle - try catch ile koruma
                try:
                    bot.db.add_user(user_id, username)
                except Exception as e:
                    # Veritabanı hatalarını sessizce ele al
                    if 'UNIQUE constraint failed' not in str(e):
                        logger.debug(f"Kullanıcı ekleme hatası (önemsiz): {str(e)}")
            except Exception as e:
                # Davet kontrolünde hata - kritik değil
                logger.debug(f"Kullanıcı davet kontrolü hatası (önemsiz): {str(e)}")
            
    except Exception as e:
        log_filtered_error(bot, f"track_user_{str(e)[:20]}", 
                          f"Kullanıcı takip hatası: {str(e)}")

def log_filtered_error(bot, error_key, error_message):
    """Tekrarlanan hataları filtreleyerek logla"""
    try:
        # Hata sayaçlarını kontrol et
        if not hasattr(bot, 'error_counter'):
            bot.error_counter = {}
            
        if error_key not in bot.error_counter:
            bot.error_counter[error_key] = 0
            
        bot.error_counter[error_key] += 1
        
        # İlk hata veya her 5 hatada bir göster
        if bot.error_counter[error_key] <= 1 or bot.error_counter[error_key] % 5 == 0:
            logger.error(error_message)
            
    except Exception:
        # Son çare - filtreleme yapılamazsa direkt logla
        logger.error(error_message)