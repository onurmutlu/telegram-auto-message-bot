"""
Bot durumu komutları
"""
import os
import sys
import json
import logging
import asyncio
import requests
import time
from pathlib import Path
from app.services.service_manager import ServiceManager
from app.core.config import settings
from app.db.session import get_session
from telethon import TelegramClient
from app.core.unified.client import get_client

logger = logging.getLogger(__name__)

async def get_status():
    """Tüm servislerin durumunu kontrol eder ve gösterir"""
    retries = 3
    for attempt in range(retries):
        try:
            db = next(get_session())
            # Manage edilmiş client oluştur - Memory session kullanarak
            client = await get_client()
            if not client:
                return False, "Telegram client oluşturulamadı. Lütfen oturum bilgilerinizi kontrol edin."
            
            manager = ServiceManager(client=client, db=db, config=settings)
            await manager.load_all_services()
            status = await manager.get_all_services_status()
            print("\n\033[1mSERVİS DURUM RAPORU\033[0m\n" + "="*60)
            print(f"{'Servis':20} | {'Durum':10} | {'Başlatıldı':10} | {'Uptime':8} | {'Son Hata':20}")
            print("-"*80)
            for name, info in status.items():
                durum = info.get("status") or info.get("running")
                initialized = info.get('initialized', False)
                uptime = info.get('uptime', '-') if 'uptime' in info else '-'
                last_error = info.get('error') or info.get('last_error') or ''
                if durum is True or durum == 'running':
                    icon = '\u2705'  # ✅
                    color = '\033[92m'  # Yeşil
                    durum_str = "ÇALIŞIYOR"
                elif durum == 'error':
                    icon = '\u26A0'  # ⚠️
                    color = '\033[93m'  # Sarı
                    durum_str = "HATA"
                else:
                    icon = '\u274C'  # ❌
                    color = '\033[91m'  # Kırmızı
                    durum_str = "DURDU"
                print(f"{color}{icon} {name:18} | {durum_str:10} | {str(initialized):10} | {str(uptime):8} | {last_error[:20]:20}\033[0m")
            print("-"*80)
            # Özet ve öneri
            errors = [n for n, i in status.items() if (i.get('status') == 'error' or i.get('running') is False)]
            if errors:
                print("\033[93m\nDikkat! Hatalı veya durmuş servisler var:")
                for n in errors:
                    print(f"- {n}")
                print("Lütfen logları kontrol edin veya 'python -m app.cli start' ile tekrar başlatmayı deneyin.\033[0m")
            else:
                print("\033[92m\nTüm servisler sorunsuz çalışıyor!\033[0m")
            print("\nBir sonraki adım için: 'python -m app.cli dashboard' komutuyla web arayüzünü başlatabilirsiniz.")
            return True, "Servis durumu başarıyla alındı."
        except Exception as e:
            if "database is locked" in str(e) and attempt < retries - 1:
                time.sleep(2)
                continue
            logging.error(f"Servis durumu alınırken hata: {e}")
            return False, f"Hata: {str(e)}"

def run_status():
    """CLI için status çalıştırıcı"""
    result, message = asyncio.run(get_status())
    
    if result:
        print("\033[92m" + message + "\033[0m")  # Yeşil
    else:
        print("\033[91m" + message + "\033[0m")  # Kırmızı
    
    return result 