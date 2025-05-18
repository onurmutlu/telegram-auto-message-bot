import asyncio
from telethon import TelegramClient, errors, functions, types
import os
import logging
import time
import sys
import platform

# logging yapılandırması
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logging.getLogger('telethon').setLevel(logging.DEBUG) # Telethon için DEBUG seviyesinde loglama

# --- Kimlik Bilgisi Setleri ---
# Set 1 (Mevcut bilgileriniz)
API_ID_1 = 23692263
API_HASH_1 = 'ff5d6ee1ba5a22f4b6734eac0c0e77e1' # API_HASH muhtemelen eksik - tam değeri kontrol edin
PHONE_1 = '+905382617727'

# Set 2 (Alternatif bilgileriniz için yer tutucular)
API_ID_2 = 20689123
API_HASH_2 = '74dcf2a06df47f54389bec40303e3aca'
PHONE_2 = '+905358606506'

# Hangi kimlik bilgisi setinin kullanılacağını seçin (1 veya 2)
USE_CREDENTIALS_SET = 2
# --- -------------------- ---

# Seçilen sete göre API bilgilerini ata
if USE_CREDENTIALS_SET == 1:
    CURRENT_API_ID = API_ID_1
    CURRENT_API_HASH = API_HASH_1
    CURRENT_PHONE = PHONE_1
    print("1. Kimlik Bilgisi Seti kullanılıyor.")
elif USE_CREDENTIALS_SET == 2:
    CURRENT_API_ID = API_ID_2
    CURRENT_API_HASH = API_HASH_2
    CURRENT_PHONE = PHONE_2
    print("2. Kimlik Bilgisi Seti kullanılıyor.")
else:
    print("HATA: Geçersiz USE_CREDENTIALS_SET değeri. Lütfen 1 veya 2 seçin.")
    exit()

SESSION_NAME = f"test_session_{USE_CREDENTIALS_SET}_{os.getpid()}"  # Benzersiz bir oturum adı

# Ağ zaman aşımı değerlerini artırın
client = TelegramClient(SESSION_NAME, CURRENT_API_ID, CURRENT_API_HASH, 
                        connection_retries=5, 
                        retry_delay=10,
                        timeout=60,
                        device_model=f"Python {platform.python_version()} on {platform.system()}")

async def main():
    try:
        print(f"Minimal test (bellek içi oturum, direkt giriş denemesi): Bağlanmaya çalışılıyor API_ID: {CURRENT_API_ID}, HASH: {'*'*len(CURRENT_API_HASH[:-4]) + CURRENT_API_HASH[-4:]}, Telefon: {CURRENT_PHONE}")

        # Olası eski oturum dosyalarını sil
        session_file_default = "telegram_session.session"
        session_file_none_str = "None.session"
        if os.path.exists(session_file_default):
            os.remove(session_file_default)
            print(f"{session_file_default} dosyası silindi.")
        if os.path.exists(session_file_none_str):
            os.remove(session_file_none_str)
            print(f"{session_file_none_str} dosyası silindi.")

        print("client.connect() çağrılıyor...")
        await client.connect() 
        print("client.connect() başarılı.")
        
        print("Bağlantı sonrası bekleniyor (5 saniye)...")
        await asyncio.sleep(5)  # Bağlantı kurulduktan sonra kısa bir bekleme süresi
        
        # Bağlantı durumunu doğrula
        if not client.is_connected():
            print("UYARI: client.connect() çağrıldı ancak bağlantı aktif değil! Yeniden bağlanmaya çalışılıyor...")
            await client.connect()
            if not client.is_connected():
                print("HATA: Tekrar bağlanmaya çalışıldı ancak başarısız oldu!")
                return
        
        print("Detaylı bağlantı bilgileri - DC ID:", client.session.dc_id)
        print("Sunucu adresini çözümleme...")
        
        try:
            dc = client._get_dc(client.session.dc_id)
            print(f"Sunucu: {dc.ip_address}:{dc.port}")
        except Exception as e:
            print(f"Sunucu bilgilerini çözümlerken hata: {e}")
        
        # Doğrudan kod isteme
        print(f"Kod isteği gönderiliyor: {CURRENT_PHONE}")
        try:
            # Sistem bilgilerini kullanarak kod gönderme
            init_system = platform.system()
            init_version = platform.version()
            init_device = f"Python {platform.python_version()} on {init_system} {init_version[:20]}"
            
            print(f"Telegram'a bildirilen cihaz: {init_device}")
            
            result = await asyncio.wait_for(
                client.send_code_request(
                    CURRENT_PHONE,
                    force_sms=False
                ), 
                timeout=30.0
            )
            print(f"Kod isteği gönderildi. Sonuç: {result}")
            print("Lütfen Telegram'dan gelen kodu girin.")
            code = input("Kodu girin: ")
            
            print("Giriş yapılıyor...")
            me = await asyncio.wait_for(
                client.sign_in(phone=CURRENT_PHONE, code=code.strip()), 
                timeout=30.0
            )
            print("Giriş başarılı!")
            
            if me:
                print(f"Başarıyla giriş yapıldı: {me.first_name} (ID: {me.id})")
            else:
                print("Kullanıcı bilgileri alınamadı.")

        except asyncio.TimeoutError:
            print(f"HATA: Kod gönderme veya giriş işlemi zaman aşımına uğradı (30s).")
            
    except errors.ApiIdInvalidError:
        print("HATA: API ID veya API HASH geçersiz. Lütfen my.telegram.org adresinden kontrol edin.")
    except errors.PhoneNumberInvalidError:
        print(f"HATA: Telefon numarası ({CURRENT_PHONE}) geçersiz.")
    except errors.PhoneCodeInvalidError:
        print("HATA: Girilen Telegram kodu geçersiz.")
    except errors.SessionPasswordNeededError:
        print("HATA: İki faktörlü kimlik doğrulama (2FA) şifresi gerekli. Bu test betiği 2FA'yı henüz desteklemiyor.")
    except errors.FloodWaitError as e:
        wait_seconds = e.seconds
        print(f"HATA: Flood wait hatası. {wait_seconds} saniye beklemeniz gerekiyor.")
        print(f"Yeniden denemeden önce {wait_seconds} saniye bekleyin.")
    except ConnectionError as e:
        print(f"HATA: Bağlantı hatası: {type(e).__name__}: {e}")
    except errors.RPCError as e:
        print(f"HATA: Telegram RPC hatası: {type(e).__name__}: {e}")
    except Exception as e:
        print(f"Genel bir hata oluştu: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if client.is_connected():
            print("Bağlantı kesiliyor...")
            await client.disconnect()
            print("Bağlantı kesildi.")
        else:
            print("Bağlantı zaten kapalı veya kurulamadı.")

if __name__ == '__main__':
    asyncio.run(main())
