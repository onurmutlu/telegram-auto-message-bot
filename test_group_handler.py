import asyncio
import os
from colorama import init, Fore, Style
from dotenv import load_dotenv

# Renk desteğini başlat
init()

# Çevre değişkenlerini yükle
load_dotenv()

# Gerekli modülleri içe aktar
from telethon import TelegramClient
from config.settings import Config
from database.user_db import UserDatabase
from bot.handlers.group_handler import GroupHandler

print(f"{Fore.CYAN}=========== GRUP MESAJI GÖNDERME TESTİ ==========={Style.RESET_ALL}")

async def test_group_handler():
    """GroupHandler'ın mesaj gönderme işlevini test eder."""
    config = Config()
    user_db = UserDatabase()
    
    # API Kimlik bilgileri
    api_id = int(os.getenv("API_ID"))
    api_hash = os.getenv("API_HASH")
    phone_number = os.getenv("PHONE_NUMBER")
    
    print(f"{Fore.YELLOW}Telegram'a bağlanılıyor...{Style.RESET_ALL}")
    client = TelegramClient('mysession', api_id, api_hash)
    await client.connect()
    
    if not await client.is_user_authorized():
        print(f"{Fore.RED}Telegram oturumu başlatılamamış! Önce main.py çalıştırın.{Style.RESET_ALL}")
        return
    
    print(f"{Fore.GREEN}Telegram bağlantısı başarılı!{Style.RESET_ALL}")
    
    # Grup listesini al
    target_groups = os.getenv("TARGET_GROUPS", "").split(',')
    if not target_groups or target_groups == [""]:
        print(f"{Fore.RED}Hedef grup tanımlanmamış! TARGET_GROUPS çevre değişkenini kontrol edin.{Style.RESET_ALL}")
        return
    
    print(f"{Fore.CYAN}Hedef gruplar: {target_groups}{Style.RESET_ALL}")
    
    # GroupHandler örneği oluştur
    group_handler = GroupHandler(client, config, user_db)
    
    # Her gruba test mesajı gönder
    for group_id in target_groups:
        try:
            print(f"{Fore.YELLOW}'{group_id}' grubuna mesaj gönderiliyor...{Style.RESET_ALL}")
            
            # _send_message_to_group metodunu doğrudan çağır
            # Debug için bunu test et
            result = await group_handler._send_message_to_group(group_id)
            
            if result:
                print(f"{Fore.GREEN}✓ Mesaj başarıyla gönderildi!{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}✗ Mesaj gönderilemedi!{Style.RESET_ALL}")
                
        except Exception as e:
            print(f"{Fore.RED}Hata: {str(e)}{Style.RESET_ALL}")
    
    # Bağlantıyı kapat
    await client.disconnect()

if __name__ == "__main__":
    # Test fonksiyonunu çalıştır
    asyncio.run(test_group_handler())