#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Telegram Bot - Unified başlatıcı
Bu dosya, Telegram botunu production modunda çalıştırmak için tasarlanmıştır.
"""

import os
import asyncio
import sys
import logging
from dotenv import load_dotenv
import importlib.util

# Ana dizine geç
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
project_dir = os.path.dirname(parent_dir)
sys.path.insert(0, project_dir)
sys.path.insert(0, parent_dir)

# Çevre değişkenlerini yükle
load_dotenv()

# Production modunu zorla
os.environ["ENV"] = "production"
os.environ["DEBUG"] = "false"

# Ana main.py dosya yolunu oluştur
main_path = os.path.join(parent_dir, "main.py")
if not os.path.exists(main_path):
    print(f"Hata: {main_path} dosyası bulunamadı!")
    sys.exit(1)

# main.py modülünü dinamik olarak yükle
spec = importlib.util.spec_from_file_location("app_main", main_path)
app_main = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app_main)

async def start_bot():
    """
    Botu başlatır ve hataları yakalar
    """
    try:
        print("Telegram Bot production modunda başlatılıyor...")
        await app_main.main()
    except Exception as e:
        print(f"Bot çalıştırılırken hata oluştu: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    # Windows için asyncio ayarı
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # AsyncIO event loop al
    loop = asyncio.get_event_loop()
    
    try:
        # Ana uygulamayı başlat
        loop.run_until_complete(start_bot())
    except KeyboardInterrupt:
        print("\nBot kullanıcı tarafından durduruldu.")
    except Exception as e:
        print(f"Kritik hata: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        print("Uygulama kapatılıyor...")
        loop.close() 