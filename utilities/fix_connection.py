#!/usr/bin/env python3
"""
Telegram oturum sorunlarını çözen ve temiz bir bağlantı kuran araç.
Bu araç, mevcut oturum dosyasını kontrol eder, gerekirse yenisini oluşturur
ve bağlantı kurmayı dener.

Kullanım:
    python fix_connection.py

Çıkış:
    Başarılı: Bot bağlantı durumu ve yetkilendirme bilgisi
    Başarısız: Hata mesajları ve tanı bilgisi
"""

import os
import sys
import time
import asyncio
import logging
import platform
import re
from pathlib import Path

# Ana dizini ekle
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

# Loglama
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("tg_connection_fix.log")
    ]
)
logger = logging.getLogger("tg_connection_fix")

async def check_env_vars():
    """Gerekli çevre değişkenlerini kontrol eder."""
    try:
        from app.core.config import settings
        
        # Gerekli değerleri kontrol et
        api_id = settings.API_ID
        api_hash = settings.API_HASH
        phone = settings.PHONE
        session_name = settings.SESSION_NAME
        
        logger.info("Çevre değişkenleri kontrol ediliyor...")
        logger.info(f"API ID: {api_id} (Tip: {type(api_id)})")
        
        if hasattr(api_hash, 'get_secret_value'):
            api_hash_val = api_hash.get_secret_value()
            api_hash_safe = f"{api_hash_val[:4]}...{api_hash_val[-4:]}"
        else:
            api_hash_val = str(api_hash)
            api_hash_safe = f"{api_hash_val[:4]}...{api_hash_val[-4:]}" if len(api_hash_val) > 8 else "Yok"
            
        logger.info(f"API HASH: {api_hash_safe} (Tip: {type(api_hash)})")
        
        if hasattr(phone, 'get_secret_value'):
            phone_val = phone.get_secret_value()
        else:
            phone_val = str(phone)
            
        phone_safe = phone_val[:4] + "*****" + phone_val[-4:] if len(phone_val) > 8 else "Yok"
        logger.info(f"Telefon: {phone_safe}")
        logger.info(f"Oturum Adı: {session_name}")
        
        # Değerlerin varlığını kontrol et
        if not api_id or api_id == 0:
            logger.error("API ID değeri geçerli değil")
            return False
            
        if not api_hash_val or len(api_hash_val) < 10:
            logger.error("API HASH değeri geçerli değil")
            return False
            
        if not phone_val or len(phone_val) < 10:
            logger.error("Telefon numarası geçerli değil")
            return False
            
        logger.info("✅ Çevre değişkenleri geçerli.")
        return True
        
    except Exception as e:
        logger.error(f"Çevre değişkenleri kontrol edilirken hata: {str(e)}")
        return False

async def check_session_file():
    """Oturum dosyasının durumunu kontrol eder."""
    try:
        from app.core.config import settings
        
        session_name = settings.SESSION_NAME
        session_file = f"{session_name}.session"
        session_journal = f"{session_name}.session-journal"
        
        # Ana dizin ve session dizinini kontrol et
        session_files = []
        
        # Ana dizinde ara
        if os.path.exists(os.path.join(BASE_DIR, session_file)):
            session_files.append(os.path.join(BASE_DIR, session_file))
            
        if os.path.exists(os.path.join(BASE_DIR, session_journal)):
            session_files.append(os.path.join(BASE_DIR, session_journal))
            
        # session/ dizininde ara
        session_dir = os.path.join(BASE_DIR, "session")
        if os.path.exists(session_dir):
            if os.path.exists(os.path.join(session_dir, session_file)):
                session_files.append(os.path.join(session_dir, session_file))
                
            if os.path.exists(os.path.join(session_dir, session_journal)):
                session_files.append(os.path.join(session_dir, session_journal))
                
        # sessions/ dizininde ara
        sessions_dir = os.path.join(BASE_DIR, "sessions")
        if os.path.exists(sessions_dir):
            if os.path.exists(os.path.join(sessions_dir, session_file)):
                session_files.append(os.path.join(sessions_dir, session_file))
                
            if os.path.exists(os.path.join(sessions_dir, session_journal)):
                session_files.append(os.path.join(sessions_dir, session_journal))
                
        # app/session/ dizininde ara
        app_session_dir = os.path.join(BASE_DIR, "app", "session")
        if os.path.exists(app_session_dir):
            if os.path.exists(os.path.join(app_session_dir, session_file)):
                session_files.append(os.path.join(app_session_dir, session_file))
                
            if os.path.exists(os.path.join(app_session_dir, session_journal)):
                session_files.append(os.path.join(app_session_dir, session_journal))
                
        # app/sessions/ dizininde ara 
        app_sessions_dir = os.path.join(BASE_DIR, "app", "sessions")
        if os.path.exists(app_sessions_dir):
            if os.path.exists(os.path.join(app_sessions_dir, session_file)):
                session_files.append(os.path.join(app_sessions_dir, session_file))
                
            if os.path.exists(os.path.join(app_sessions_dir, session_journal)):
                session_files.append(os.path.join(app_sessions_dir, session_journal))
        
        # Sonuçları göster
        if session_files:
            logger.info(f"Bulunan oturum dosyaları:")
            for f in session_files:
                file_size = os.path.getsize(f)
                file_time = os.path.getmtime(f)
                file_time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(file_time))
                logger.info(f"  - {f} (Boyut: {file_size} bytes, Güncelleme: {file_time_str})")
                
            return True, session_files
        else:
            logger.warning("Hiçbir oturum dosyası bulunamadı.")
            return False, []
            
    except Exception as e:
        logger.error(f"Oturum dosyası kontrol edilirken hata: {str(e)}")
        return False, []

async def create_fresh_session():
    """Temiz bir oturum dosyası oluşturur."""
    try:
        from app.scripts.create_fresh_session import create_new_session
        from app.core.config import settings
        
        session_name = settings.SESSION_NAME
        logger.info(f"'{session_name}' için yeni oturum dosyası oluşturuluyor...")
        
        # Önce yedek oluştur
        session_file = f"{session_name}.session"
        session_journal = f"{session_name}.session-journal"
        
        # Ana dizindeki dosyaları yedekle
        if os.path.exists(os.path.join(BASE_DIR, session_file)):
            backup_name = f"{session_name}.session.bak"
            os.rename(
                os.path.join(BASE_DIR, session_file),
                os.path.join(BASE_DIR, backup_name)
            )
            logger.info(f"Ana dizindeki oturum dosyası yedeklendi: {backup_name}")
            
        if os.path.exists(os.path.join(BASE_DIR, session_journal)):
            backup_name = f"{session_name}.session-journal.bak"
            os.rename(
                os.path.join(BASE_DIR, session_journal),
                os.path.join(BASE_DIR, backup_name)
            )
            logger.info(f"Ana dizindeki oturum journal dosyası yedeklendi: {backup_name}")
        
        # Temiz oturum oluştur
        result = create_new_session(session_name)
        
        if result:
            logger.info(f"✅ Yeni oturum dosyası başarıyla oluşturuldu.")
            return True
        else:
            logger.error("Oturum dosyası oluşturulamadı.")
            return False
            
    except Exception as e:
        logger.error(f"Temiz oturum oluşturulurken hata: {str(e)}")
        return False

async def initialize_connection(session_files=None):
    """Telegram bağlantısı kurar."""
    try:
        from telethon import TelegramClient
        from app.core.config import settings
        import telethon.sync
        
        # Değerleri al
        api_id = settings.API_ID
        api_hash = settings.API_HASH
        phone = settings.PHONE
        session_name = settings.SESSION_NAME
        
        # API HASH değerini kontrol et
        if hasattr(api_hash, 'get_secret_value'):
            api_hash = api_hash.get_secret_value()
            
        # Telefon değerini kontrol et
        if hasattr(phone, 'get_secret_value'):
            phone = phone.get_secret_value()
        
        # Cihaz bilgisi
        device_info = f"Python {platform.python_version()} on {platform.system()} {platform.release()}"
        
        logger.info(f"TelegramClient başlatılıyor...")
        logger.info(f"Kullanılan değerler:")
        logger.info(f"  - API ID: {api_id}")
        logger.info(f"  - API HASH: {api_hash[:4]}...{api_hash[-4:]}")
        logger.info(f"  - Session Name: {session_name}")
        logger.info(f"  - Cihaz: {device_info}")
        
        # Client oluştur
        client = TelegramClient(
            session_name, 
            api_id, 
            api_hash,
            device_model=device_info,
            system_version=platform.release(),
            app_version="1.0",
            lang_code="tr"
        )
        
        # Bağlan
        logger.info("Telegram'a bağlanılıyor...")
        await client.connect()
        
        # Bağlantı durumunu kontrol et
        if client.is_connected():
            logger.info("✅ Telegram'a bağlantı başarılı!")
            
            # Oturum durumunu kontrol et
            is_authorized = await client.is_user_authorized()
            
            if is_authorized:
                logger.info("✅ Oturum yetkili, kullanıcı bilgileri alınıyor...")
                me = await client.get_me()
                
                if me:
                    logger.info(f"✅ Kullanıcı: {me.first_name} (ID: {me.id})")
                    if hasattr(me, 'username') and me.username:
                        logger.info(f"   Kullanıcı adı: @{me.username}")
                    
                    # Ping testi
                    logger.info("Ping testi yapılıyor...")
                    start_time = time.time()
                    await client.get_me()
                    ping_ms = round((time.time() - start_time) * 1000, 2)
                    logger.info(f"✅ Ping: {ping_ms}ms")
                    
                    # Başarılı bağlantı
                    return True, client, me
                else:
                    logger.warning("⚠️ Kullanıcı bilgileri alınamadı")
            else:
                logger.warning("⚠️ Oturum yetkili değil, yeniden yetkilendirme gerekiyor")
                
                # Kullanıcı kodunu gönder
                try:
                    logger.info(f"📱 Telefon numarasına ({phone}) kod gönderiliyor...")
                    await client.send_code_request(phone)
                    
                    # Kodu al
                    logger.info("Lütfen telefonunuza gelen kodu girin:")
                    code = input("Kod: ")
                    
                    # Giriş yap
                    logger.info("Kod kullanılarak giriş yapılıyor...")
                    await client.sign_in(phone, code)
                    
                    # Oturum durumunu tekrar kontrol et
                    is_authorized = await client.is_user_authorized()
                    
                    if is_authorized:
                        logger.info("✅ Yetkilendirme başarılı!")
                        me = await client.get_me()
                        
                        if me:
                            logger.info(f"✅ Kullanıcı: {me.first_name} (ID: {me.id})")
                            return True, client, me
                        else:
                            logger.warning("⚠️ Kullanıcı bilgileri alınamadı")
                    else:
                        logger.error("❌ Yetkilendirme başarısız")
                        
                except Exception as auth_err:
                    logger.error(f"❌ Yetkilendirme sırasında hata: {str(auth_err)}")
        else:
            logger.error("❌ Telegram'a bağlantı kurulamadı")
            
        return False, client, None
            
    except Exception as e:
        logger.error(f"Bağlantı kurulurken hata: {str(e)}")
        return False, None, None

async def test_bot():
    """Bot bağlantı ve oturum testini çalıştırır."""
    try:
        # Çevre değişkenlerini kontrol et
        if not await check_env_vars():
            logger.error("Çevre değişkenleri geçerli değil, bot başlatılamaz")
            return False
            
        # Oturum dosyasını kontrol et
        session_exists, session_files = await check_session_file()
        
        # Bağlantıyı kur
        connection_success, client, user = await initialize_connection(session_files)
        
        if connection_success:
            logger.info("\n✅ Tüm testler başarılı. Bot çalışmaya hazır.")
            
            if client and client.is_connected():
                await client.disconnect()
                logger.info("Bağlantı kapatıldı.")
                
            return True
        
        # Eğer bağlantı kuramazsak ve oturum dosyası varsa, temiz oturum oluşturalım
        if not connection_success and session_exists:
            logger.warning("\n⚠️ Bağlantı kurulamadı, temiz oturum oluşturuluyor...")
            
            if await create_fresh_session():
                logger.info("Yeni oturum oluşturuldu, bağlantı tekrar deneniyor...")
                
                # Yeni oturum ile tekrar dene
                connection_success, client, user = await initialize_connection()
                
                if connection_success:
                    logger.info("\n✅ Yeni oturum ile bağlantı başarılı. Bot çalışmaya hazır.")
                    
                    if client and client.is_connected():
                        await client.disconnect()
                        logger.info("Bağlantı kapatıldı.")
                        
                    return True
                else:
                    logger.error("\n❌ Yeni oturum ile de bağlantı kurulamadı.")
            else:
                logger.error("\n❌ Temiz oturum oluşturulamadı.")
        
        logger.error("\n❌ Test başarısız. Bağlantı kurulamadı.")
        return False
            
    except Exception as e:
        logger.error(f"Test çalıştırılırken hata: {str(e)}")
        return False

async def main():
    """Ana çalışma fonksiyonu."""
    logger.info("=" * 50)
    logger.info("Telegram Bot Bağlantı Sorunu Onarım Aracı")
    logger.info("=" * 50)
    
    # Bot testini çalıştır
    test_result = await test_bot()
    
    if test_result:
        logger.info("\n🎉 Bot bağlantısı başarıyla test edildi ve onarıldı.")
        logger.info("Bot'u şimdi başlatabilirsiniz:")
        logger.info("$ python -m app.main")
    else:
        logger.error("\n❌ Bot bağlantısı test edilemedi veya onarılamadı.")
        logger.error("Lütfen .env dosyasındaki değerleri kontrol edin ve tekrar deneyin.")
    
    logger.info("=" * 50)

if __name__ == "__main__":
    # Windows için koruma
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    # Anaconsole.sync()io döngüsünü çalıştır
    asyncio.run(main())
