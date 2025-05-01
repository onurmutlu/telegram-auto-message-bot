#!/usr/bin/env python3
"""
# ============================================================================ #
# Dosya: check_database_runner.py
# Yol: /Users/siyahkare/code/telegram-bot/check_database_runner.py
# İşlev: Veritabanı kontrol aracını çalıştırır
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

import asyncio
import os
import sys

# Ana proje dizinini Python path'ine ekle
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def run_db_checker():
    """Veritabanı kontrol aracını çalıştır"""
    try:
        from bot.utils.db_checker import main
        asyncio.run(main())
    except ImportError:
        print("❌ Hata: bot.utils.db_checker modülü bulunamadı!")
        print("Bot dizin yapısı kontrol edilmeli.")
    except Exception as e:
        print(f"❌ Hata: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_db_checker() 