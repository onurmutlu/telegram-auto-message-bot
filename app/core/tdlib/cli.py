#!/usr/bin/env python3
"""
Telegram Client CLI - TDLib veya Telethon kullanan basit bir komut satırı aracı.
Telegram hesabına giriş yapmak ve temel işlemler gerçekleştirmek için kullanılır.
"""

import asyncio
import logging
import os
import sys
import argparse

# Logging yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Proje modüllerini dahil et
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from app.core.tdlib.session import get_telegram_client, TDLIB_AVAILABLE
from app.core.config import settings

# Otomatik oturum açma yardımcı fonksiyonu
async def auto_login(client, phone=None, password=None, bot_token=None):
    """
    Telegram hesabına otomatik giriş yapar.
    
    Args:
        client: TelegramClient nesnesi
        phone: Telefon numarası (isteğe bağlı, settings'ten alınacak)
        password: İki faktörlü doğrulama şifresi (isteğe bağlı, settings'ten alınacak)
        bot_token: Bot token (isteğe bağlı, settings'ten alınacak)
        
    Returns:
        bool: Başarılı ise True, değilse False
    """
    try:
        # Veri tiplerini kontrol et
        if hasattr(client, 'session') and hasattr(client.session, '_auth_key') and client.session._auth_key:
            if isinstance(client.session._auth_key.key, memoryview):
                client.session._auth_key.key = bytes(client.session._auth_key.key)
                logger.info("Auth key memoryview -> bytes dönüşümü yapıldı")
        
        # Bağlantı kuralım
        if not client.is_connected():
            await client.connect()
        
        # Zaten yetkili mi kontrol edelim
        if await client.is_user_authorized():
            logger.info("Hesaba zaten giriş yapılmış")
            return True
        
        logger.warning("Hesaba giriş yapılmamış, otomatik giriş deneniyor...")
        
        # Giriş parametrelerini ayarlayalım
        if not phone and hasattr(settings, 'PHONE'):
            phone = settings.PHONE
        
        if not password and hasattr(settings, 'TWO_FACTOR_PASSWORD'):
            password = settings.TWO_FACTOR_PASSWORD
            
        if not bot_token and hasattr(settings, 'BOT_TOKEN'):
            bot_token = settings.BOT_TOKEN
        
        # Bot hesabı için giriş
        if bot_token:
            logger.info("Bot hesabına giriş yapılıyor...")
            await client.sign_in(bot_token=bot_token)
            logger.info("Bot hesabına başarıyla giriş yapıldı")
            return True
        
        # Kullanıcı hesabı için giriş
        if phone:
            logger.info(f"Kullanıcı hesabına giriş yapılıyor: {phone}")
            
            # Kod gönderelim
            try:
                code_sent = await client.send_code_request(phone)
                logger.info("Doğrulama kodu gönderildi")
                
                # Otomatik kod girişi için
                # Burada bir kod okuma mekanizması eklenebilir
                # Örneğin bir dosyadan veya environment variable'dan
                
                # Örnek olarak, .code_verification dosyasından kodu okuyalım
                code_file = os.path.join(settings.SESSIONS_DIR, ".code_verification")
                verification_code = None
                
                # Kod dosyası var mı kontrol edelim
                if os.path.exists(code_file):
                    try:
                        with open(code_file, 'r') as f:
                            verification_code = f.read().strip()
                        
                        # Dosyayı kullındıktan sonra silelim
                        os.remove(code_file)
                        
                        logger.info(f"Doğrulama kodu dosyadan okundu")
                    except Exception as e:
                        logger.error(f"Doğrulama kodu dosyası okuma hatası: {e}")
                
                # Environment variable'dan kod okuma
                if not verification_code and 'TELEGRAM_CODE' in os.environ:
                    verification_code = os.environ['TELEGRAM_CODE']
                    logger.info("Doğrulama kodu çevre değişkeninden alındı")
                
                # Eğer kod bulunamazsa, manuel olarak yeniden bağlanılması gerekir
                if not verification_code:
                    logger.warning("Doğrulama kodu bulunamadı, manuel olarak giriş yapmanız gerekiyor")
                    return False
                
                # Kodu gönderelim
                try:
                    await client.sign_in(phone, verification_code)
                    
                    # İki faktörlü doğrulama kontrolü
                    if password and isinstance(await client.get_me(), None):
                        await client.sign_in(password=password)
                        
                    logger.info("Kullanıcı hesabına başarıyla giriş yapıldı")
                    return True
                except Exception as e:
                    logger.error(f"Giriş yapılırken hata: {e}")
                    return False
                
            except Exception as e:
                logger.error(f"Doğrulama kodu gönderilirken hata: {e}")
                return False
        else:
            logger.error("Giriş yapılabilmesi için telefon numarası, bot token veya oturum verisi gerekiyor")
            return False
    
    except Exception as e:
        logger.error(f"Otomatik giriş sırasında beklenmeyen hata: {e}")
        return False

async def list_dialogs(client):
    """Son mesajlaşmaları listeler"""
    logger.info("Son mesajlaşmalar listeleniyor...")
    async for dialog in client.iter_dialogs():
        print(f"{dialog.id}: {dialog.name} - {dialog.entity.username if hasattr(dialog.entity, 'username') else 'Bilinmiyor'}")

async def send_message(client, chat_id, message):
    """Belirtilen sohbete mesaj gönderir"""
    logger.info(f"'{chat_id}' sohbetine mesaj gönderiliyor...")
    result = await client.send_message(chat_id, message)
    print(f"Mesaj başarıyla gönderildi: {result.id}")

async def main(args):
    """Ana program fonksiyonu"""
    client = None
    
    try:
        # TDLib veya Telethon kullanımı seçimi
        use_tdlib = args.tdlib and TDLIB_AVAILABLE
        
        if use_tdlib:
            logger.info("TDLib kullanılıyor")
        else:
            logger.info("Telethon kullanılıyor")
        
        # İstemciyi başlat
        client = get_telegram_client(use_tdlib=use_tdlib, auto_auth=False)  # Auto auth'u kapatıyoruz
        
        # Telethon istemcisi ise asenkron işlemleri çalıştır
        if not use_tdlib:
            try:
                # Bağlantı kurma
                if not client.is_connected():
                    await client.connect()
                
                # Giriş yapılmış mı kontrol et
                if not await client.is_user_authorized():
                    logger.warning("Telegram hesabına giriş yapılmamış!")
                    
                    # Auto login işlemi
                    if args.auto_login:
                        logger.info("Otomatik giriş deneniyor...")
                        if await auto_login(client):
                            logger.info("Otomatik giriş başarılı")
                        else:
                            logger.error("Otomatik giriş başarısız")
                            # Telefon numarası ile giriş dene
                            if args.phone:
                                await manual_login(client, args.phone)
                            else:
                                logger.error("Giriş yapabilmek için telefon numarası gerekiyor")
                                return
                    # Manuel giriş işlemi        
                    elif args.phone:
                        await manual_login(client, args.phone)
                    else:
                        logger.error("Giriş yapabilmek için -a/--auto-login veya -p/--phone parametresi gerekiyor")
                        return
            except Exception as e:
                logger.error(f"Bağlantı veya giriş sırasında hata: {e}")
                if client and client.is_connected():
                    await client.disconnect()
                return
        
        # İstemci işlem seçimi
        if args.list_dialogs:
            if not use_tdlib:
                await list_dialogs(client)
            else:
                logger.info("Dialog listeleme şu anda TDLib için desteklenmiyor")
        
        if args.send_message and args.chat_id:
            if not use_tdlib:
                await send_message(client, args.chat_id, args.send_message)
            else:
                logger.info("Mesaj gönderme şu anda TDLib için desteklenmiyor")
        
        # İşlem yapılmadıysa ne yapabileceğini göster
        if not (args.list_dialogs or args.send_message):
            logger.info("Kullanılabilir komutlar:")
            logger.info("  --list-dialogs : Son mesajlaşmaları listele")
            logger.info("  --send-message mesaj --chat-id ID : Belirtilen sohbete mesaj gönder")
    except Exception as e:
        logger.error(f"İşlem sırasında beklenmeyen hata: {e}")
    finally:
        # Bağlantıyı kapat
        if client and not use_tdlib and client.is_connected():
            try:
                await client.disconnect()
                logger.info("Bağlantı başarıyla kapatıldı")
            except Exception as e:
                logger.error(f"Bağlantı kapatılırken hata: {e}")
    
    return client

async def manual_login(client, phone):
    """Manuel giriş yapma"""
    logger.info(f"Telefon numarası kullanılarak giriş deneniyor: {phone}")
    
    # Kod isteği gönder
    await client.send_code_request(phone)
    verification_code = input("Doğrulama kodu: ")
    
    try:
        # Giriş yap
        await client.sign_in(phone, verification_code)
        
        # İki faktörlü doğrulama kontrolü
        if not await client.is_user_authorized():
            password = input("İki faktörlü doğrulama şifresi: ")
            await client.sign_in(password=password)
            
        logger.info("Başarıyla giriş yapıldı!")
    except Exception as e:
        logger.error(f"Giriş yapılırken hata: {e}")

if __name__ == "__main__":
    # Komut satırı argümanları
    parser = argparse.ArgumentParser(description="Telegram Client CLI")
    parser.add_argument("-t", "--tdlib", action="store_true", help="TDLib kullan (kullanılabilirse)")
    parser.add_argument("-a", "--auto-login", action="store_true", help="Otomatik giriş dene")
    parser.add_argument("-p", "--phone", help="Telefon numarası")
    parser.add_argument("-l", "--list-dialogs", action="store_true", help="Son mesajlaşmaları listele")
    parser.add_argument("-s", "--send-message", help="Gönderilecek mesaj")
    parser.add_argument("-c", "--chat-id", help="Mesaj gönderilecek sohbet ID'si")
    
    # Argümanları ayrıştır
    args = parser.parse_args()
    
    # Asenkron ana fonksiyonu çalıştır
    if sys.platform == 'win32':
        # Windows için politikayı ayarla
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    try:
        # Yeni event loop oluştur
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Main fonksiyonunu çalıştır
        client = None
        try:
            client = loop.run_until_complete(main(args))
        except KeyboardInterrupt:
            logger.info("İşlem kullanıcı tarafından sonlandırıldı")
        except Exception as e:
            logger.error(f"İşlem sırasında beklenmeyen hata: {e}")
        finally:
            # Eğer client hala bağlıysa, bağlantıyı kapat
            if client and hasattr(client, 'disconnect') and client.is_connected():
                loop.run_until_complete(client.disconnect())
                
            # Bitmemiş görevleri kontrol et ve temizle
            pending = asyncio.all_tasks(loop)
            if pending:
                for task in pending:
                    try:
                        task.cancel()
                    except Exception as e:
                        logger.debug(f"Görev iptal edilirken hata: {e}")
    finally:
        # Loop'u kapat
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()
        except Exception as e:
            logger.error(f"Event loop kapatılırken hata: {e}")
        logger.info("Program sonlandı") 