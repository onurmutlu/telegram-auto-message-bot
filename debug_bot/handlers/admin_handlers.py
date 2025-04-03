# Premium kullanıcı yönetimi için komut ekleyin
from telegram.ext import CommandHandler, Filters, CallbackContext
from telegram import Update, ParseMode
from datetime import datetime
import logging

# Logger tanımlayın
logger = logging.getLogger(__name__)

def register_handlers(self, dispatcher):
    """Komut işleyicilerini kaydeder."""
    # Mevcut kayıtlar...
    
    # Premium kullanıcı yönetimi komutları
    dispatcher.add_handler(CommandHandler("premium", self.premium_users_command, 
                          filters=Filters.user(username=self.superusers)))
    dispatcher.add_handler(CommandHandler("addpremium", self.add_premium_user_command, 
                          filters=Filters.user(username=self.superusers)))
    dispatcher.add_handler(CommandHandler("delpremium", self.del_premium_user_command,
                          filters=Filters.user(username=self.superusers)))

def premium_users_command(self, update: Update, context: CallbackContext):
    """
    Premium kullanıcıları listeler.
    """
    try:
        if not self.db:
            update.message.reply_text("Veritabanı bağlantısı mevcut değil.")
            return
            
        premium_users = self.db.get_premium_users()
        
        if not premium_users:
            update.message.reply_text("Hiç premium kullanıcı bulunamadı.")
            return
            
        # Kullanıcı listesi hazırla
        message = "*Premium Kullanıcılar:*\n\n"
        for i, user in enumerate(premium_users, 1):
            expiry = datetime.fromisoformat(user['expiration_date'])
            days_left = (expiry - datetime.now()).days
            status = "✅ Aktif" if user['is_active'] else "❌ Pasif"
            
            message += (f"{i}. *{user['username'] or 'İsimsiz'}* - {status}\n"
                      f"   📱 {user['phone_number'] or 'Telefon yok'}\n"
                      f"   🔑 {user['license_key'][:8]}...{user['license_key'][-4:]}\n"
                      f"   ⏳ {days_left} gün kaldı\n\n")
        
        update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Premium kullanıcıları listelerken hata: {e}")
        update.message.reply_text(f"Hata oluştu: {str(e)}")

def add_premium_user_command(self, update: Update, context: CallbackContext):
    """
    Yeni premium kullanıcı ekler.
    
    Kullanım: /addpremium <user_id> <license_key> [license_type] [api_id] [api_hash] [phone_number]
    Örnek: /addpremium 123456789 ABC-DEF-GHI professional 12345 abcdef123456 +901234567890
    """
    try:
        args = context.args
        
        if len(args) < 2:
            update.message.reply_text("Eksik parametre. Kullanım:\n/addpremium <user_id> <license_key> [license_type] [api_id] [api_hash] [phone_number]")
            return
            
        user_id = int(args[0])
        license_key = args[1]
        license_type = args[2] if len(args) > 2 else 'standard'
        api_id = args[3] if len(args) > 3 else None
        api_hash = args[4] if len(args) > 4 else None
        phone_number = args[5] if len(args) > 5 else None
        
        # Veritabanına ekle
        if self.db.add_premium_user(user_id, license_key, license_type, api_id, api_hash, phone_number):
            update.message.reply_text(f"Premium kullanıcı başarıyla eklendi: {user_id}")
        else:
            update.message.reply_text("Premium kullanıcı eklenirken hata oluştu.")
            
    except ValueError:
        update.message.reply_text("Geçersiz user_id. Sayısal bir değer giriniz.")
    except Exception as e:
        logger.error(f"Premium kullanıcı eklerken hata: {e}")
        update.message.reply_text(f"Hata oluştu: {str(e)}")