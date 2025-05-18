#!/usr/bin/env python3
# filepath: /Users/siyahkare/code/telegram-bot/test_telegram_connection.py
"""
Telegram API bağlantısını doğrudan sert kodlanmış değerlerle test etmek için basit bir betik.
Bu, API kimlik doğrulama sorunlarını izole etmek için tasarlanmıştır.
"""
import asyncio
from telethon import TelegramClient, functions, errors
import logging
import os
import platform
import time

# Log yapılandırması
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Doğrudan sabit değerler kullanın (otomatik okuma olmadan)
API_ID = 23692263
API_HASH = "ff5d6053b266f78d1293f9343f40e77e"  # Ekran görüntüsündeki değer
PHONE = "+905382617727"
SESSION_NAME = f"connection_test_{int(time.time())}"  # Benzersiz oturum adı

# Renk kodları
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
RESET = '\033[0m'

def print_color(text, color=YELLOW):
    """Renkli metin yazdır"""
    print(f"{color}{text}{RESET}")

async def main():
    print_color("=" * 60, GREEN)
    print_color("TELEGRAM BAĞLANTI TESTİ (Sabit Kimlik Bilgileriyle)", GREEN)
    print_color("=" * 60, GREEN)
    
    print_color(f"API_ID: {API_ID}")
    print_color(f"API_HASH: {API_HASH}")
    print_color(f"PHONE: {PHONE}")
    print_color(f"SESSION_NAME: {SESSION_NAME}")
    print_color(f"PYTHON: {platform.python_version()} {platform.system()}")
    
    # Oturum dosyalarını temizle
    if os.path.exists(f"{SESSION_NAME}.session"):
        os.remove(f"{SESSION_NAME}.session")
        print_color(f"Eski oturum dosyası silindi.")
    
    # Cihaz bilgisi
    device_info = f"Python {platform.python_version()} on {platform.system()} {platform.release()}"
    print_color(f"Cihaz bilgisi: {device_info}")
    
    client = TelegramClient(
        SESSION_NAME, 
        API_ID, 
        API_HASH,
        device_model=device_info,
        app_version='1.0',
        system_version=platform.version()
    )
    
    try:
        print_color("Bağlanılıyor...")
        await client.connect()
        
        if client.is_connected():
            print_color("Bağlantı başarılı!", GREEN)
            
            # Basit API doğrulama
            try:
                print_color("GetConfig sorgusu yapılıyor...")
                config = await client(functions.help.GetConfigRequest())
                print_color(f"API doğrulandı! DC: {config.this_dc}", GREEN)
                
                # Kod isteme testi
                print_color("\nKod isteme testi yapılıyor...")
                try:
                    # Bağlantı sonrası kısa bir bekleme
                    print_color("5 saniye bekleniyor...")
                    await asyncio.sleep(5)
                    
                    code_request = await client.send_code_request(PHONE)
                    print_color(f"Kod isteği başarılı! Kod tipi: {code_request.type}", GREEN)
                    print_color("Telefonunuza gönderilen kodu girin:")
                    
                    code = input("Kod: ")
                    
                    # Kodu doğrula
                    me = await client.sign_in(PHONE, code)
                    print_color(f"Giriş başarılı! {me.first_name} ({me.id})", GREEN)
                    
                    current_session = client.session.save()
                    print_color(f"Oturum dosyası: {current_session}")
                    
                except errors.ApiIdInvalidError as e:
                    print_color(f"API ID/HASH geçersiz: {e}", RED)
                except errors.PhoneCodeInvalidError:
                    print_color("Kod geçersiz. Tekrar deneyin.", RED)
                except errors.FloodWaitError as e:
                    print_color(f"Flood wait hatası. {e.seconds} saniye beklemeniz gerekiyor.", RED)
                except errors.PhoneNumberInvalidError:
                    print_color(f"Telefon numarası geçersiz: {PHONE}", RED)
                except Exception as e:
                    print_color(f"Kod gönderme hatası: {type(e).__name__}: {e}", RED)
            except errors.ApiIdInvalidError as e:
                print_color(f"API ID/HASH geçersiz: {e}", RED)
            except Exception as e:
                print_color(f"API doğrulama hatası: {type(e).__name__}: {e}", RED)
        else:
            print_color("Bağlantı kurulamadı!", RED)
            
    except Exception as e:
        print_color(f"Genel hata: {type(e).__name__}: {e}", RED)
    finally:
        if client and client.is_connected():
            await client.disconnect()
            print_color("Bağlantı kapatıldı.")
        
        # Özet göster
        print_color("\n" + "=" * 60, GREEN)
        print_color("TEST SONUCU:", GREEN)
        if client and client.is_connected():
            print_color("Telegram API Bağlantısı: BAŞARILI ✓", GREEN)
        else:
            print_color("Telegram API Bağlantısı: BAŞARISIZ ✗", RED)
        print_color("=" * 60, GREEN)

if __name__ == "__main__":
    asyncio.run(main())
