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

# .env dosyasını yükle
load_dotenv()

async def login():
    """Telegram hesabına giriş yapar ve session_string'i kaydeder"""
    try:
        print("\n" + "="*50)
        print("Telegram Oturum Açma Yardımcısı")
        print("="*50 + "\n")
        
        # API kimlik bilgilerini al
        api_id = os.getenv('API_ID')
        api_hash = os.getenv('API_HASH')
        
        # API bilgilerini string'den int'e çevir (eğer string ise)
        if api_id and isinstance(api_id, str):
            try:
                api_id = int(api_id)
            except ValueError:
                print(f"HATA: API ID ({api_id}) geçerli bir sayı değil")
                api_id = None
        
        # Eksik API kimlik bilgilerini kontrol et
        if not api_id or not api_hash:
            print("UYARI: API kimlik bilgileri eksik, lütfen .env dosyasını kontrol edin.")
            print("API_ID ve API_HASH değerlerini my.telegram.org adresinden alabilirsiniz.")
            # Kullanıcıdan giriş iste
            if not api_id:
                api_id_str = input("API ID: ")
                try:
                    api_id = int(api_id_str)
                except ValueError:
                    print("Geçersiz API ID formatı, bir sayı olmalı")
                    return
            if not api_hash:
                api_hash = input("API Hash: ")
                if not api_hash:
                    print("API Hash boş olamaz")
                    return
        
        # İstemciyi oluştur
        client = TelegramClient(StringSession(), api_id, api_hash)
        
        # Bağlantı kur
        print("Telegram sunucusuna bağlanılıyor...")
        await client.connect()
        
        # Telefon numarasını al
        phone = os.getenv('PHONE')
        if not phone:
            phone = input("Telefon numarası (+90xxxxxxxxxx): ")
        else:
            print(f"Telefon numarası .env dosyasından alındı: {phone}")
            proceed = input("Bu numarayı kullanmak istiyor musunuz? (E/h): ").lower()
            if proceed != 'e' and proceed != '':
                phone = input("Telefon numarası (+90xxxxxxxxxx): ")
        
        # Doğrulama kodu gönder
        print(f"Doğrulama kodu gönderiliyor: {phone}...")
        
        # Tekrar deneme mekanizması
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                await client.send_code_request(phone)
                break
            except Exception as e:
                if attempt < max_attempts - 1:
                    print(f"Kod gönderme hatası: {str(e)}")
                    print(f"Tekrar deneniyor ({attempt+1}/{max_attempts})...")
                    await asyncio.sleep(3)
                else:
                    print(f"Kod gönderme başarısız: {str(e)}")
                    # Hata varsa bağlantıyı kapat ve çık
                    await client.disconnect()
                    return
        
        # Doğrulama kodunu al ve oturum aç
        try:
            print("\nTelegram'dan aldığınız kodu girin")
            code = input("Kod: ")
            
            print("Kodla giriş yapılıyor...")
            await client.sign_in(phone, code)
            
            # Session string'i al
            session_string = client.session.save()
            print("Giriş başarılı!")
            
            # Kullanıcı bilgilerini göster
            me = await client.get_me()
            print(f"Hoş geldiniz, {me.first_name}!")
            if hasattr(me, 'username') and me.username:
                print(f"Kullanıcı adı: @{me.username}")
            print(f"Kullanıcı ID: {me.id}")
            
            # Session string'i veritabanına kaydet
            try:
                db_host = os.getenv('POSTGRES_HOST', 'localhost')
                db_port = os.getenv('POSTGRES_PORT', '5432')
                db_name = os.getenv('POSTGRES_DB', 'telegram_bot')
                db_user = os.getenv('POSTGRES_USER', 'postgres')
                db_password = os.getenv('POSTGRES_PASSWORD', '')
                
                conn = psycopg2.connect(
                    host=db_host,
                    port=db_port,
                    dbname=db_name,
                    user=db_user,
                    password=db_password
                )
                cursor = conn.cursor()
                
                # Settings tablosunu kontrol et, yoksa oluştur
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS settings (
                        key TEXT PRIMARY KEY,
                        value TEXT,
                        updated_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                conn.commit()
                
                # Session string'i kaydet
                cursor.execute(
                    "INSERT INTO settings (key, value) VALUES ('session_string', %s) ON CONFLICT (key) DO UPDATE SET value = %s, updated_at = NOW()",
                    (session_string, session_string)
                )
                conn.commit()
                
                # PHONE'u da settings tablosuna kaydet
                if phone:
                    cursor.execute(
                        "INSERT INTO settings (key, value) VALUES ('phone', %s) ON CONFLICT (key) DO UPDATE SET value = %s, updated_at = NOW()",
                        (phone, phone)
                    )
                    conn.commit()
                
                cursor.close()
                conn.close()
                print("Session string veritabanına kaydedildi")
                print("\nBot'u şimdi başlatabilirsiniz. Yeniden oturum açmanız gerekmeyecek.")
                
            except Exception as db_error:
                print(f"Session string veritabanına kaydedilemedi: {str(db_error)}")
                print(f"Lütfen bu session string'i bir yere kaydedin:")
                print(f"\n{session_string}\n")
            
        except PhoneCodeInvalidError:
            print("Hata: Geçersiz telefon kodu. Lütfen tekrar deneyin.")
            return
            
        except SessionPasswordNeededError:
            print("İki faktörlü kimlik doğrulama gerekiyor.")
            password = input("İki faktörlü kimlik doğrulama şifrenizi girin: ")
            await client.sign_in(password=password)
            
            # Session string'i al
            session_string = client.session.save()
            print("İki faktörlü doğrulama başarılı!")
            
            # Kullanıcı bilgilerini göster
            me = await client.get_me()
            print(f"Hoş geldiniz, {me.first_name}!")
            if hasattr(me, 'username') and me.username:
                print(f"Kullanıcı adı: @{me.username}")
            print(f"Kullanıcı ID: {me.id}")
            
            # Session string'i veritabanına kaydet
            try:
                db_host = os.getenv('POSTGRES_HOST', 'localhost')
                db_port = os.getenv('POSTGRES_PORT', '5432')
                db_name = os.getenv('POSTGRES_DB', 'telegram_bot')
                db_user = os.getenv('POSTGRES_USER', 'postgres')
                db_password = os.getenv('POSTGRES_PASSWORD', '')
                
                conn = psycopg2.connect(
                    host=db_host,
                    port=db_port,
                    dbname=db_name,
                    user=db_user,
                    password=db_password
                )
                cursor = conn.cursor()
                
                # Settings tablosunu kontrol et, yoksa oluştur
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS settings (
                        key TEXT PRIMARY KEY,
                        value TEXT,
                        updated_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                conn.commit()
                
                # Session string'i kaydet
                cursor.execute(
                    "INSERT INTO settings (key, value) VALUES ('session_string', %s) ON CONFLICT (key) DO UPDATE SET value = %s, updated_at = NOW()",
                    (session_string, session_string)
                )
                conn.commit()
                
                # PHONE'u da settings tablosuna kaydet
                if phone:
                    cursor.execute(
                        "INSERT INTO settings (key, value) VALUES ('phone', %s) ON CONFLICT (key) DO UPDATE SET value = %s, updated_at = NOW()",
                        (phone, phone)
                    )
                    conn.commit()
                
                cursor.close()
                conn.close()
                print("Session string veritabanına kaydedildi")
                print("\nBot'u şimdi başlatabilirsiniz. Yeniden oturum açmanız gerekmeyecek.")
                
            except Exception as db_error:
                print(f"Session string veritabanına kaydedilemedi: {str(db_error)}")
                print(f"Lütfen bu session string'i bir yere kaydedin:")
                print(f"\n{session_string}\n")
                
    except Exception as e:
        print(f"Giriş sırasında hata oluştu: {str(e)}")
    finally:
        # Bağlantıyı kapat
        if 'client' in locals() and client.is_connected():
            await client.disconnect()
        
        print("\nOturum açma işlemi tamamlandı.")

if __name__ == "__main__":
    asyncio.run(login()) 