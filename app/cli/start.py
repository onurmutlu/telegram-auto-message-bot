"""
Tüm servisleri başlatan CLI komutu
"""
import asyncio
import logging
from app.services.service_manager import ServiceManager
from app.core.config import settings
from app.db.session import get_session
from telethon import TelegramClient
from app.core.unified.client import get_client

def run_start():
    """CLI için tüm servisleri başlatıcı"""
    asyncio.run(start_all_services())

def print_status_table(status_dict):
    print("\nServis Durumları:")
    print("-" * 40)
    for name, status in status_dict.items():
        durum = status.get("status") or status.get("running")
        durum_str = "ÇALIŞIYOR" if durum or durum is True else "DURDU"
        print(f"{name:20} | {durum_str}")
    print("-" * 40)

async def start_all_services():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("start")
    print("\n\033[1mSERVİS BAŞLATMA RAPORU\033[0m\n" + "="*60)
    db = next(get_session())
    
    # Memory Session kullanarak client oluştur
    client = await get_client()
    if not client:
        print("\033[91mHata: Telegram client bağlantısı kurulamadı!\033[0m")
        return
    
    manager = ServiceManager(client=client, db=db, config=settings)
    await manager.load_all_services()
    results = await manager.start_all_services()
    print(f"{'Servis':20} | {'Sonuç':10} | {'Mesaj':30}")
    print("-"*70)
    for name, success in results.items():
        if success:
            icon = '\u2705'  # ✅
            color = '\033[92m'  # Yeşil
            msg = "Başarıyla başlatıldı"
        else:
            icon = '\u274C'  # ❌
            color = '\033[91m'  # Kırmızı
            msg = "Başlatılamadı! Logları kontrol edin."
        print(f"{color}{icon} {name:18} | {str(success):10} | {msg:30}\033[0m")
    print("-"*70)
    errors = [n for n, s in results.items() if not s]
    if errors:
        print("\033[93m\nDikkat! Hatalı başlatılamayan servisler var:")
        for n in errors:
            print(f"- {n}")
        print("Lütfen logları kontrol edin veya yapılandırma ayarlarını gözden geçirin.\033[0m")
    else:
        print("\033[92m\nTüm servisler başarıyla başlatıldı!\033[0m")
    print("\nBir sonraki adım için: 'python -m app.cli status' ile servis durumunu görebilir, 'python -m app.cli dashboard' ile web arayüzünü başlatabilirsiniz.") 