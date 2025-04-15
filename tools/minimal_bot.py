import os
import sys
import asyncio
import logging
import random
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.tl.types import InputPeerChat, InputPeerChannel

# Loglama ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('minimal_bot')

# Çevre değişkenlerini yükle
load_dotenv()

# API kimlik bilgileri
API_ID = int(os.getenv("API_ID", "23692263"))
API_HASH = os.getenv("API_HASH", "ff5d6053b266f78d1293f9343f40e77e")

# Session dizini - proje yapısına uygun
SESSION_DIR = "runtime/sessions"
SESSION_FILE = os.path.join(SESSION_DIR, "bot_session")

# Test mesajları
TEST_MESSAGES = [
    "Merhaba! Bu bir test mesajıdır.",
    "Bot çalışıyor mu kontrol ediyorum.",
    "Test mesajı, lütfen dikkate almayın.",
    "Sistem testi - bot aktif.",
    "Bu otomatik bir test mesajıdır."
]

# Sohbet/Grup ID'leri - bunları gerçek değerlerle değiştirin
CHAT_IDS = [-1001234567890]  # Örnek değer, kendi grubunuzun ID'sini yazın

async def main():
    """Minimal bot uygulaması"""
    logger.info(f"Bot başlatılıyor...")
    
    try:
        # Dizin oluştur
        os.makedirs(SESSION_DIR, exist_ok=True)
        
        # Telegram istemcisini oluştur
        client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
        
        # Event handler ekle
        @client.on(events.NewMessage(pattern='/test'))
        async def handle_test_command(event):
            """Test komutunu işle"""
            await event.respond("Bot çalışıyor! Bu bir test yanıtıdır.")
        
        # İstemciyi başlat
        await client.start()
        
        if await client.is_user_authorized():
            me = await client.get_me()
            logger.info(f"Bot başarıyla başlatıldı: {me.first_name} (@{me.username})")
            
            # Session string bilgisini al ve göster
            session_string = client.session.save()
            logger.info(f"Session string oluşturuldu. Bu değeri veritabanına kaydedebilirsiniz.")
            
            # Her grup/sohbete test mesajları gönder
            for chat_id in CHAT_IDS:
                try:
                    message = random.choice(TEST_MESSAGES)
                    entity = None
                    
                    # Farklı entity türlerini dene
                    try:
                        entity = await client.get_entity(chat_id)
                    except ValueError:
                        try:
                            entity = InputPeerChat(chat_id)
                        except:
                            try:
                                entity = InputPeerChannel(chat_id, 0)
                            except:
                                pass
                    
                    if entity:
                        await client.send_message(entity, message)
                        logger.info(f"Mesaj gönderildi: {chat_id}")
                    else:
                        logger.error(f"Sohbet bulunamadı: {chat_id}")
                        
                except Exception as e:
                    logger.error(f"Mesaj gönderilirken hata: {chat_id} - {str(e)}")
            
            # Veritabanına session string'i kaydet
            try:
                import sqlite3
                os.makedirs("data", exist_ok=True)
                conn = sqlite3.connect("data/users.db")
                cursor = conn.cursor()
                cursor.execute('''CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY, 
                    value TEXT
                )''')
                cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                             ("session_string", session_string))
                conn.commit()
                conn.close()
                logger.info("Session string veritabanına kaydedildi!")
            except Exception as e:
                logger.error(f"Veritabanına kaydedilirken hata: {e}")
            
            # Bir süre bekle
            logger.info("Bot 60 saniye boyunca çalışacak ve sonra kapanacak")
            await asyncio.sleep(60)
            
        else:
            logger.error("Bot oturumu açık değil! Lütfen önce manuel oturum açın.")
            logger.info("Manuel oturum açmak için telefon numaranızı girip, gelen kodu onaylayın:")
            phone = input("Telefon numaranızı girin (+90xxxxxxxxxx): ")
            await client.send_code_request(phone)
            code = input("Doğrulama kodunu girin: ")
            await client.sign_in(phone, code)
            logger.info("Oturum açma başarılı!")
            
        # İstemciyi kapat
        await client.disconnect()
        
    except Exception as e:
        logger.error(f"Bot çalıştırılırken hata: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main()) 