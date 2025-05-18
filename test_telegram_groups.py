#!/usr/bin/env python3
"""
Telegram grup ve mesaj işlemlerini test eden basit script.
Mevcut oturum dosyasını kullanarak grupları listeler ve istenirse mesaj gönderir.
"""
import os
import sys
import asyncio
import argparse
import logging

# Proje kök dizini
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# Loglama ayarları
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(BASE_DIR, "group_test.log"))
    ]
)
logger = logging.getLogger("GrupTesti")

async def test_groups(only_list=True, send_message=None, target_dialog=None):
    """
    Grupları test et.
    
    Args:
        only_list (bool): Sadece grupları listele
        send_message (str): Gönderilecek mesaj (None ise sadece liste)
        target_dialog (int): Hedef diyalog indeksi (None ise kullanıcıdan sor)
    """
    # Gerekli modülleri import et
    from app.core.config import settings
    from telethon import TelegramClient
    
    # Oturum bilgilerini al
    api_id = settings.API_ID
    api_hash = settings.API_HASH
    if hasattr(api_hash, 'get_secret_value'):
        api_hash = api_hash.get_secret_value()
    
    session_path = settings.SESSIONS_DIR / f"{settings.SESSION_NAME}"
    
    print("="*50)
    print(f"TELEGRAM GRUP TESTİ")
    print("="*50)
    print(f"Oturum: {settings.SESSION_NAME}")
    print(f"Oturum dosyası: {session_path}")
    
    # Client oluştur
    client = TelegramClient(session_path, api_id, api_hash)
    
    try:
        print("Telegram API'ye bağlanılıyor...")
        await client.connect()
        
        if not client.is_connected():
            print("Bağlantı kurulamadı!")
            return
        
        print("Bağlantı KURULDU ✓")
        
        # Oturum açık mı kontrol et
        if not await client.is_user_authorized():
            print("Oturum açık değil! Lütfen önce oturum açın.")
            return
        
        print("Oturum AÇIK ✓")
        
        # Kullanıcı bilgilerini al
        me = await client.get_me()
        print(f"Kullanıcı: {me.first_name} {me.last_name or ''}")
        print(f"ID: {me.id}")
        print(f"Kullanıcı adı: @{me.username or 'Yok'}")
        
        # Diyalogları çek
        print("\nDiyaloglar (gruplar/sohbetler) yükleniyor...")
        dialogs = await client.get_dialogs()
        
        # Diyalogları türlerine göre ayır
        groups = [d for d in dialogs if d.is_group]
        channels = [d for d in dialogs if d.is_channel]
        private_chats = [d for d in dialogs if d.is_user]
        
        print(f"Toplam {len(dialogs)} diyalog bulundu:")
        print(f"  - {len(groups)} grup")
        print(f"  - {len(channels)} kanal")
        print(f"  - {len(private_chats)} özel sohbet")
        
        # Grupları listele
        if groups:
            print("\nGruplar:")
            for i, group in enumerate(groups[:10], 1):
                print(f"{i}. {group.name} (ID: {group.id})")
                # Son mesajı göster
                if hasattr(group, 'message') and group.message:
                    last_msg = group.message.message[:40] + "..." if group.message.message and len(group.message.message) > 40 else "(Boş veya medya mesajı)"
                    print(f"   Son mesaj: {last_msg}")
        
        # Mesaj gönderme testi
        if not only_list and (send_message or target_dialog is not None):
            if not groups:
                print("Mesaj göndermek için grup bulunamadı!")
                return
            
            # Hedef grup seçimi
            target_index = target_dialog
            if target_index is None:
                try:
                    target_index = int(input(f"\nHangi gruba mesaj göndermek istersiniz? (1-{len(groups)}): ")) - 1
                except ValueError:
                    print("Geçersiz giriş, mesaj gönderme iptal edildi.")
                    return
            
            if target_index < 0 or target_index >= len(groups):
                print("Geçersiz grup indeksi!")
                return
            
            target_group = groups[target_index]
            
            # Gönderilecek mesaj
            message = send_message
            if message is None:
                message = input("Gönderilecek mesaj: ")
            
            print(f"\n'{target_group.name}' grubuna mesaj gönderiliyor...")
            await client.send_message(target_group.entity, message)
            print("MESAJ GÖNDERİLDİ ✓")
            
    except Exception as e:
        print(f"HATA: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if client and client.is_connected():
            await client.disconnect()
            print("\nBağlantı kapatıldı.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Telegram grupları ve mesaj gönderme testi")
    parser.add_argument("--only-list", action="store_true", help="Sadece grupları listele, mesaj gönderme")
    parser.add_argument("--message", type=str, help="Gönderilecek mesaj", default=None)
    parser.add_argument("--target", type=int, help="Hedef grup indeksi (1'den başlar)", default=None)
    
    args = parser.parse_args()
    
    # Komut satırı argümanlarını işle
    only_list = args.only_list
    send_message = args.message
    target_dialog = args.target - 1 if args.target is not None else None
    
    asyncio.run(test_groups(only_list, send_message, target_dialog))
