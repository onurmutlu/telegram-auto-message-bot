#!/usr/bin/env python3
"""
Telegram'a doğrudan bağlantı kurmayı ve yetkilendirmeyi test eden basit script.
"""
import os
import sys
import asyncio
import time
from telethon import TelegramClient, errors

# API_ID ve API_HASH alın
API_ID = input("API ID: ")
API_HASH = input("API HASH: ")
PHONE = input("Telefon numarası (uluslararası formatta, örn: +90...): ")

# Benzersiz bir oturum adı oluşturun
SESSION_NAME = f"test_session_{int(time.time())}"
print(f"Oturum adı: {SESSION_NAME}")

async def main():
    # TelegramClient oluştur
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    
    try:
        print("Bağlanılıyor...")
        await client.connect()
        
        if not client.is_connected():
            print("Bağlantı kurulamadı!")
            return
        
        print("Bağlantı kuruldu!")
        
        # Yetkilendirme durumunu kontrol et
        authorized = await client.is_user_authorized()
        print(f"Yetkilendirilmiş: {'Evet' if authorized else 'Hayır'}")
        
        if not authorized:
            print("Doğrulama kodu isteniyor...")
            await client.send_code_request(PHONE)
            code = input("Telegram'dan gelen doğrulama kodunu girin: ")
            
            try:
                print("Giriş yapılıyor...")
                await client.sign_in(PHONE, code)
                print("Giriş başarılı!")
            except errors.SessionPasswordNeededError:
                # 2FA aktifse
                print("İki faktörlü kimlik doğrulama (2FA) gerekiyor")
                password = input("Lütfen iki faktörlü kimlik doğrulama şifrenizi girin: ")
                await client.sign_in(password=password)
                print("2FA ile giriş başarılı!")
        
        # Yetkilendirme sonrası tekrar kontrol et
        authorized = await client.is_user_authorized()
        if not authorized:
            print("Yetkilendirme başarısız oldu.")
            return
        
        # Kullanıcı bilgilerini al
        me = await client.get_me()
        print(f"\nYetkilendirme başarılı!")
        print(f"Kullanıcı: {me.first_name} {me.last_name or ''}")
        print(f"ID: {me.id}")
        print(f"Kullanıcı adı: @{me.username or 'Yok'}")
        
        # Diyalogları kontrol et
        print("\nDiyaloglar çekiliyor...")
        dialogs = await client.get_dialogs(limit=5)
        
        print(f"{len(dialogs)} diyalog bulundu:")
        for i, dialog in enumerate(dialogs, 1):
            entity_type = "Grup" if dialog.is_group else "Kanal" if dialog.is_channel else "Kullanıcı"
            print(f"{i}. {dialog.name} ({entity_type}, ID: {dialog.id})")
        
        # Test mesajı gönder
        if dialogs:
            try:
                target_index = int(input("\nHangi diyaloğa mesaj göndermek istersiniz? (1-5, 0 iptal): ")) - 1
                
                if target_index >= 0 and target_index < len(dialogs):
                    target = dialogs[target_index]
                    message = input("Gönderilecek mesaj: ")
                    
                    print(f"\n'{target.name}' adlı diyaloğa mesaj gönderiliyor...")
                    await client.send_message(target.entity, message)
                    print("Mesaj gönderildi!")
                else:
                    print("Mesaj gönderme iptal edildi.")
            except ValueError:
                print("Geçersiz giriş, mesaj gönderme iptal edildi.")
        
    except Exception as e:
        print(f"Hata: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if client.is_connected():
            await client.disconnect()
        print("\nBağlantı kapatıldı.")
        print(f"Yeni oturum dosyası: {SESSION_NAME}.session")
        print("Bu dosyayı app/sessions/ klasörüne taşıyıp .env dosyasında SESSION_NAME ayarını güncelleyebilirsiniz.")

if __name__ == "__main__":
    asyncio.run(main())
