#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Telegram oturum açma yardımcısı.
Bu script, bottan bağımsız olarak Telegram hesabına giriş yapmayı sağlar.
"""

import os
import sys
import asyncio
import logging
from dotenv import load_dotenv
import psycopg2
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError

# Loglama yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("telegram_login")

# Önce .env dosyasını yükle
load_dotenv(override=True)

# Değişkenleri al - .env dosyasından çevresel değişkenlere aktarıldı
API_ID = os.getenv("API_ID", "12345")  
API_HASH = os.getenv("API_HASH", "your_api_hash_here")
PHONE = os.getenv("PHONE", "+905551234567")
SESSION_NAME = os.getenv("SESSION_NAME", "telegram_session")

# API_ID'yi integer'a çevir
try:
    API_ID = int(API_ID)
except ValueError:
    print(f"HATA: API_ID ({API_ID}) bir sayı değil!")
    sys.exit(1)

async def main():
    print(f"Telegram oturumu oluşturuluyor...")
    print(f"API ID: {API_ID}")
    print(f"API HASH: {API_HASH[:5]}...{API_HASH[-5:] if len(API_HASH) > 10 else ''}")
    print(f"Telefon: {PHONE}")
    print(f"Session adı: {SESSION_NAME}")
    
    # TelegramClient oluştur
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    
    # Bağlantıyı kur
    print("Telegram'a bağlanılıyor...")
    await client.connect()
    
    # Oturum açık mı kontrol et
    if await client.is_user_authorized():
        print("Telegram oturumu zaten açık!")
        me = await client.get_me()
        print(f"Kullanıcı: {me.first_name} {me.last_name if me.last_name else ''} (@{me.username if me.username else 'Yok'})")
    else:
        print("Telegram oturumu açılması gerekiyor")
        print(f"Telefon doğrulaması gerekiyor. {PHONE} numarasına kod gönderiliyor...")
        await client.send_code_request(PHONE)
        
        # Kodu iste
        try:
            verification_code = input("Telegram'dan gelen kodu girin: ")
            await client.sign_in(PHONE, verification_code)
            print("Telegram oturumu başarıyla oluşturuldu!")
            
            me = await client.get_me()
            print(f"Kullanıcı: {me.first_name} {me.last_name if me.last_name else ''} (@{me.username if me.username else 'Yok'})")
        except Exception as e:
            print(f"Doğrulama hatası: {str(e)}")
    
    # Grupları listeleme
    print("\nKullanıcı gruplarını listeliyorum...")
    try:
        dialogs = await client.get_dialogs()
        groups = []
        
        for dialog in dialogs:
            if dialog.is_group or dialog.is_channel:
                groups.append({
                    "id": dialog.id,
                    "title": dialog.title,
                    "members": dialog.entity.participants_count if hasattr(dialog.entity, 'participants_count') else "Bilinmiyor"
                })
        
        print(f"Toplam {len(groups)} grup/kanal bulundu:")
        for i, group in enumerate(groups, 1):
            print(f"{i}. {group['title']} (ID: {group['id']}, Üye: {group['members']})")
    except Exception as e:
        print(f"Grupları listelerken hata: {str(e)}")
        
    # Bağlantıyı kapat
    await client.disconnect()
    print("İşlem tamamlandı!")

if __name__ == "__main__":
    # .env dosyasını yükle
    try:
        load_dotenv(override=True)
        print(".env dosyası yüklendi")
    except ImportError:
        print(".env modülü bulunamadı, ortam değişkenleri kullanılacak")
    
    # Ana fonksiyonu çalıştır
    asyncio.run(main()) 