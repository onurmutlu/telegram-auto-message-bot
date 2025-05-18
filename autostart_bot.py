#!/usr/bin/env python3
"""
Telegram botunu otomatik başlatma ve kimlik doğrulama scripti.
Bu script:
1. Önce mevcut oturum durumunu kontrol eder
2. Gerekirse yeni oturum oluşturur ve yetkilendirir
3. Bot servisini başlatır
"""
import os
import sys
import asyncio
import time
import logging
import subprocess
from pathlib import Path

# Kök dizini ekle
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# Loglama yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(BASE_DIR, "bot_autostart.log"))
    ]
)
logger = logging.getLogger("BotAutostart")

# Güvenli input yardımcısını içe aktar
try:
    from input_helper import safe_input
except ImportError:
    logger.warning("input_helper modülü bulunamadı, standart input kullanılacak")
    def safe_input(prompt, file_path=None, retry_count=3, retry_delay=1):
        return input(prompt)

# Ortam değişkenlerini yükleyin
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    logger.warning("python-dotenv yüklü değil, .env dosyasından değişkenler yüklenemeyecek")

# Telethon kütüphanesini import et
from telethon import TelegramClient, errors

# Uygulama konfigürasyon ayarlarını import et
try:
    from app.core.config import settings
except Exception as e:
    logger.error(f"Ayarları içe aktarırken hata: {e}")
    sys.exit(1)

async def check_connection(client):
    """Bağlantı durumunu kontrol eder."""
    logger.info("Bağlantı durumu kontrol ediliyor...")
    
    try:
        await client.connect()
        
        if not client.is_connected():
            logger.error("Bağlantı kurulamadı!")
            return False, "Bağlantı kurulamadı"
        
        logger.info("Bağlantı kuruldu.")
        
        # Oturum açık mı kontrol et
        is_authorized = await client.is_user_authorized()
        
        if is_authorized:
            logger.info("Oturum açık, kimlik doğrulama gerekmiyor.")
            
            # Kullanıcı bilgileri al
            me = await client.get_me()
            logger.info(f"Kullanıcı: {me.first_name} (ID: {me.id}, Kullanıcı adı: @{me.username or 'Yok'})")
            
            return True, "Oturum açık"
        else:
            logger.warning("Oturum kapalı, kimlik doğrulama gerekiyor.")
            return False, "Oturum kapalı"
    
    except Exception as e:
        logger.error(f"Bağlantı kontrolü sırasında hata: {e}")
        return False, str(e)

async def authorize_session(client):
    """Oturum yetkilendirmesi yapar."""
    logger.info("Oturum yetkilendirme başlatılıyor...")
    
    try:
        # Telefon numarasını al
        phone = settings.PHONE
        if hasattr(phone, 'get_secret_value'):
            phone = phone.get_secret_value()
        
        if not phone:
            logger.error("Telefon numarası ayarlanmamış! .env dosyasında PHONE değerini kontrol edin.")
            return False
        
        logger.info(f"Telefon numarası: {phone}")
        
        # Önceki oturum kontrolü
        if await client.is_user_authorized():
            me = await client.get_me()
            logger.info(f"Önceki oturum aktif! Kullanıcı: {me.first_name} (ID: {me.id})")
            return True
        
        # Doğrulama kodu gönder
        try:
            # Doğrulama kodu ve 2FA şifresi için .env dosyasını kontrol et
            code = os.environ.get("TELEGRAM_AUTH_CODE")
            two_fa_password = os.environ.get("TELEGRAM_2FA_PASSWORD")
            
            # Doğrulama kodu işlemi
            logger.info("Doğrulama kodu isteniyor...")
            await client.send_code_request(phone)
            
            if not code:
                # Kodu standart girişten veya dosyadan al
                logger.info("Doğrulama kodu bekleniyor...")
                auth_code_file = os.path.join(BASE_DIR, ".telegram_auth_code")
                code = safe_input("Telegram'dan gelen doğrulama kodunu girin: ", file_path=auth_code_file)
                
                if not code:
                    logger.error("Doğrulama kodu alınamadı!")
                    return False
                    
                logger.info(f"Doğrulama kodu girildi: {code[:1]}{'*' * (len(code)-2)}{code[-1:]}")
            else:
                logger.info(f"Önceden tanımlanmış doğrulama kodu kullanılıyor: {code[:1]}{'*' * (len(code)-2)}{code[-1:]}")
            
            # Giriş yap
            logger.info("Giriş yapılıyor...")
            try:
                await client.sign_in(phone, code)
                
                # Kontrol et
                if await client.is_user_authorized():
                    me = await client.get_me()
                    logger.info(f"Giriş başarılı! Kullanıcı: {me.first_name} (ID: {me.id})")
                    
                    # Doğrulama kodu kullanıldı, temizle
                    if "TELEGRAM_AUTH_CODE" in os.environ:
                        del os.environ["TELEGRAM_AUTH_CODE"]
                        logger.info("Kullanılan doğrulama kodu ortam değişkeninden temizlendi.")
                    
                    return True
                else:
                    logger.error("Giriş sonrası oturum açılamadı!")
                    return False
            
            except errors.PhoneCodeInvalidError:
                logger.error("Geçersiz doğrulama kodu!")
                
                # Doğrulama kodu kullanıldı, temizle
                if "TELEGRAM_AUTH_CODE" in os.environ:
                    del os.environ["TELEGRAM_AUTH_CODE"]
                
                # Yeni kod iste
                code = input("Geçersiz kod. Yeni doğrulama kodunu girin: ")
                logger.info("Yeni doğrulama kodu girildi.")
                
                # Tekrar giriş yap
                await client.sign_in(phone, code)
                
                # Kontrol et
                if await client.is_user_authorized():
                    me = await client.get_me()
                    logger.info(f"Giriş başarılı! Kullanıcı: {me.first_name} (ID: {me.id})")
                    return True
                else:
                    logger.error("Giriş sonrası oturum açılamadı!")
                    return False
                
        except errors.SessionPasswordNeededError:
            # 2FA aktif
            logger.info("İki faktörlü kimlik doğrulama (2FA) gerekli")
            
            # Önce çevre değişkenlerinden kontrol et
            password = two_fa_password if two_fa_password else None
            
            # Şifre yoksa standart girişten veya dosyadan al
            if not password:
                logger.info("2FA şifresi bekleniyor...")
                two_fa_file = os.path.join(BASE_DIR, ".telegram_2fa_password")
                password = safe_input("Lütfen iki faktörlü kimlik doğrulama şifrenizi girin: ", file_path=two_fa_file)
                
                if not password:
                    logger.error("2FA şifresi alınamadı!")
                    return False
            else:
                logger.info("Önceden tanımlanmış 2FA şifresi kullanılıyor...")
            
            # 2FA ile giriş yap
            try:
                await client.sign_in(password=password)
                
                # Kontrol et
                if await client.is_user_authorized():
                    me = await client.get_me()
                    logger.info(f"2FA ile giriş başarılı! Kullanıcı: {me.first_name} (ID: {me.id})")
                    
                    # 2FA şifresi kullanıldı, temizle
                    if "TELEGRAM_2FA_PASSWORD" in os.environ:
                        del os.environ["TELEGRAM_2FA_PASSWORD"]
                        logger.info("Kullanılan 2FA şifresi ortam değişkeninden temizlendi.")
                    
                    return True
                else:
                    logger.error("2FA sonrası oturum açılamadı!")
                    return False
            except errors.PasswordHashInvalidError:
                logger.error("Geçersiz 2FA şifresi!")
                
                # 2FA şifresi kullanıldı, temizle
                if "TELEGRAM_2FA_PASSWORD" in os.environ:
                    del os.environ["TELEGRAM_2FA_PASSWORD"]
                
                # Yeni şifre iste
                password = input("Geçersiz şifre. Yeni 2FA şifrenizi girin: ")
                
                # Tekrar giriş yap
                await client.sign_in(password=password)
                
                # Kontrol et
                if await client.is_user_authorized():
                    me = await client.get_me()
                    logger.info(f"2FA ile giriş başarılı! Kullanıcı: {me.first_name} (ID: {me.id})")
                    return True
                else:
                    logger.error("2FA sonrası oturum açılamadı!")
                    return False
    
    except Exception as e:
        logger.error(f"Kimlik doğrulama sırasında hata: {e}")
        return False

async def set_session_in_env(session_name):
    """Oturum adını .env dosyasında günceller."""
    try:
        env_path = os.path.join(BASE_DIR, ".env")
        
        if os.path.exists(env_path):
            logger.info(f".env dosyası güncelleniyor. Yeni oturum adı: {session_name}")
            
            # Dosyayı oku
            with open(env_path, "r") as f:
                content = f.read()
            
            # SESSION_NAME değerini güncelle
            import re
            pattern = r"(SESSION_NAME=)([^\r\n]*)"
            replacement = f"\\1{session_name}"
            
            # Değişiklik yapılacak mı kontrol et
            if re.search(pattern, content):
                # Pattern bulundu, değiştir
                new_content = re.sub(pattern, replacement, content)
                
                # Değişiklik var mı kontrol et
                if new_content != content:
                    # Dosyayı yaz
                    with open(env_path, "w") as f:
                        f.write(new_content)
                    
                    logger.info(f".env dosyası güncellendi, yeni oturum adı: {session_name}")
                    return True
                else:
                    logger.info(f"Oturum adı zaten '{session_name}' olarak ayarlanmış.")
                    return True
            else:
                # Pattern bulunamadı, yeni satır ekle
                with open(env_path, "a") as f:
                    f.write(f"\nSESSION_NAME={session_name}\n")
                
                logger.info(f".env dosyasına SESSION_NAME={session_name} eklendi.")
                return True
        else:
            logger.warning(f".env dosyası bulunamadı: {env_path}")
            # Yeni .env dosyası oluştur
            with open(env_path, "w") as f:
                f.write(f"SESSION_NAME={session_name}\n")
            
            logger.info(f"Yeni .env dosyası oluşturuldu, SESSION_NAME={session_name}")
            return True
    
    except Exception as e:
        logger.error(f".env dosyası güncellenirken hata: {e}")
        return False

async def start_bot_service():
    """Bot servisini başlatır."""
    logger.info("Bot servisi başlatılıyor...")
    
    try:
        # Farklı bir process olarak başlat
        cmd = [sys.executable, "-m", "app.main"]
        env = os.environ.copy()
        
        process = subprocess.Popen(
            cmd,
            env=env,
            cwd=BASE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        logger.info(f"Bot servisi başlatıldı (PID: {process.pid})")
        
        # Süreç durumunu kontrol et
        if process.poll() is None:
            logger.info("Bot servisi çalışıyor.")
            return True, process
        else:
            stdout, stderr = process.communicate()
            logger.error(f"Bot servisi başlatılamadı. Çıkış kodu: {process.returncode}")
            logger.error(f"Çıktı: {stdout}")
            logger.error(f"Hata: {stderr}")
            return False, None
    
    except Exception as e:
        logger.error(f"Bot servisi başlatılırken hata: {e}")
        return False, None

async def check_create_session():
    """Oturum dosyasını kontrol eder, gerekirse yeni oluşturur ve yetkilendirir."""
    try:
        # Gerekli ayarları al
        from app.core.config import settings
        
        api_id = settings.API_ID
        api_hash = settings.API_HASH
        if hasattr(api_hash, 'get_secret_value'):
            api_hash = api_hash.get_secret_value()
        
        session_name = settings.SESSION_NAME
        
        # Oturum dosyası yolu
        if hasattr(settings, "SESSIONS_DIR"):
            session_dir = settings.SESSIONS_DIR
        else:
            session_dir = os.path.join(BASE_DIR, "app", "sessions")
        
        # Dizini kontrol et
        os.makedirs(session_dir, exist_ok=True)
        
        session_path = os.path.join(session_dir, f"{session_name}")
        logger.info(f"Mevcut oturum: {session_name}")
        logger.info(f"Oturum dosyası: {session_path}.session")
        
        # Client oluştur
        client = TelegramClient(session_path, api_id, api_hash)
        
        # Bağlantı durumunu kontrol et
        success, message = await check_connection(client)
        
        if success:
            logger.info("Oturum dosyası geçerli ve kimlik doğrulaması yapılmış.")
            await client.disconnect()
            return True
        
        # Bağlantı başarısız veya oturum kapalı, yeni oturum oluştur
        if "Oturum kapalı" in message:
            # Mevcut oturumu yetkilendir
            logger.info("Mevcut oturumu yetkilendirme deneniyor...")
            auth_success = await authorize_session(client)
            
            if auth_success:
                logger.info("Oturum başarıyla yetkilendirildi.")
                await client.disconnect()
                return True
            else:
                logger.warning("Mevcut oturum yetkilendirilemedi, yeni oturum oluşturulacak.")
        
        # Yeni oturum oluştur
        new_session_name = f"{session_name}_new_{int(time.time())}"
        new_session_path = os.path.join(session_dir, f"{new_session_name}")
        
        logger.info(f"Yeni oturum oluşturuluyor: {new_session_name}")
        
        # Yeni client oluştur
        new_client = TelegramClient(new_session_path, api_id, api_hash)
        
        # Bağlan
        await new_client.connect()
        
        if not new_client.is_connected():
            logger.error("Yeni oturum için bağlantı kurulamadı!")
            await new_client.disconnect()
            return False
        
        # Yeni oturumu yetkilendir
        auth_success = await authorize_session(new_client)
        
        if auth_success:
            logger.info("Yeni oturum başarıyla yetkilendirildi.")
            
            # .env dosyasını güncelle
            env_updated = await set_session_in_env(new_session_name)
            
            if env_updated:
                logger.info("Yeni oturum adı .env dosyasına kaydedildi.")
            else:
                logger.warning("Yeni oturum adı .env dosyasına kaydedilemedi!")
            
            await new_client.disconnect()
            
            # Ayarları yeniden yükle
            from importlib import reload
            import app.core.config
            reload(app.core.config)
            from app.core.config import settings
            
            logger.info(f"Ayarlar yeniden yüklendi. Oturum adı: {settings.SESSION_NAME}")
            
            return True
        else:
            logger.error("Yeni oturum yetkilendirilemedi!")
            await new_client.disconnect()
            return False
    
    except Exception as e:
        logger.error(f"Oturum kontrolü/oluşturma sırasında hata: {e}")
        if client.is_connected():
            await client.disconnect()
        return False
    finally:
        # Bağlantıları temizle
        if client and client.is_connected():
            await client.disconnect()

async def main():
    """Ana işlev."""
    try:
        logger.info("Bot otomatik başlatma işlemi başlatılıyor...")
        
        # Oturum kontrolü/oluşturma
        session_success = await check_create_session()
        
        if session_success:
            logger.info("Oturum kontrolü/oluşturma başarılı, bot servisi başlatılıyor...")
            
            # Bot servisini başlat
            service_success, process = await start_bot_service()
            
            if service_success:
                logger.info("Bot servisi başarıyla başlatıldı.")
                
                # Sürecin çıktılarını yakala
                if process:
                    logger.info("Bot servis çıktıları izleniyor...")
                    
                    # Çıktıları sınırlı bir süre boyunca izle
                    monitor_time = 10  # 10 saniye boyunca izle
                    start_time = time.time()
                    
                    while time.time() - start_time < monitor_time:
                        if process.poll() is not None:
                            # Süreç bitti
                            stdout, stderr = process.communicate()
                            logger.info(f"Bot servisi sonlandı. Çıkış kodu: {process.returncode}")
                            if stdout:
                                logger.info(f"Çıktı: {stdout}")
                            if stderr:
                                logger.error(f"Hata: {stderr}")
                            break
                        
                        # Çıktı varsa al (non-blocking)
                        output_line = process.stdout.readline() if process.stdout else None
                        
                        if output_line and output_line.strip():
                            logger.info(f"Bot: {output_line.strip()}")
                        
                        # Kısa bekleme
                        await asyncio.sleep(0.2)
                    
                    # Sadece kontrol et, süreç devam ediyor mu?
                    if process.poll() is None:
                        logger.info("Bot servisi çalışmaya devam ediyor.")
                    else:
                        logger.error(f"Bot servisi beklenmedik şekilde sonlandı. Çıkış kodu: {process.returncode}")
                        return False
                
                logger.info("Bot servisi çalışmaya devam ediyor.")
                return True
            else:
                logger.error("Bot servisi başlatılamadı!")
                return False
        else:
            logger.error("Oturum kontrolü/oluşturma başarısız, bot servisi başlatılamıyor!")
            return False
    
    except Exception as e:
        logger.error(f"Bot otomatik başlatma sırasında hata: {e}")
        return False

if __name__ == "__main__":
    # Çalıştır
    success = asyncio.run(main())
    
    if success:
        print("Bot otomatik başlatma işlemi başarılı.")
        sys.exit(0)
    else:
        print("Bot otomatik başlatma işlemi başarısız!")
        sys.exit(1)
