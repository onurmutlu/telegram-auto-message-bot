#!/usr/bin/env python3
"""
# ============================================================================ #
# Dosya: bot_starter.py
# Yol: /Users/siyahkare/code/telegram-bot/bot_starter.py
# İşlev: Telegram bot başlatma ve yönetme aracı
#
# Build: 2025-04-01-01:25:30
# Versiyon: v3.4.0
# ============================================================================ #
#
# Bu script, Telegram botunu başlatır ve yönetir:
# - Başlamadan önce isteğe bağlı olarak temizlik yapar
# - Bot yapılandırması ve parametreleri yönetir
# - Servisleri kontrol eder ve raporlar
#
# Kullanım: python bot_starter.py [--clean] [--config CONFIG]
# ============================================================================ #
"""
import argparse
import sys
import os
import subprocess
from pathlib import Path

def run_cleanup(args):
    """Temizlik scriptini çalıştır"""
    cleanup_args = []
    
    if args.clean_all:
        cleanup_args.append("--all")
    else:
        if args.clean_logs:
            cleanup_args.append("--logs")
        if args.clean_cache:
            cleanup_args.append("--cache")
        if args.clean_temp:
            cleanup_args.append("--temp")
    
    if cleanup_args:
        print("🧹 Temizlik yapılıyor...")
        subprocess.run([sys.executable, "cleanup.py"] + cleanup_args)

def main():
    parser = argparse.ArgumentParser(description="Telegram Bot Başlatıcı")
    parser.add_argument("--clean", action="store_true", help="Başlamadan önce temizlik yapılsın mı?")
    parser.add_argument("--clean-all", action="store_true", help="Tüm geçici dosyaları temizle")
    parser.add_argument("--clean-logs", action="store_true", help="Sadece log dosyalarını temizle")
    parser.add_argument("--clean-cache", action="store_true", help="Sadece cache dosyalarını temizle")
    parser.add_argument("--clean-temp", action="store_true", help="Sadece geçici dosyalarını temizle")
    
    # Bot'a özel argümanlar
    parser.add_argument("--config", help="Kullanılacak yapılandırma dosyası")
    parser.add_argument("--verbose", action="store_true", help="Ayrıntılı çıktı")
    
    args = parser.parse_args()
    
    # Temizlik argümanı verildiyse temizlik yap
    if args.clean or args.clean_all or args.clean_logs or args.clean_cache or args.clean_temp:
        run_cleanup(args)
    
    # Bot'u başlat
    print("🤖 Telegram Bot başlatılıyor...")
    # Bot başlatma kodları...

if __name__ == "__main__":
    main()