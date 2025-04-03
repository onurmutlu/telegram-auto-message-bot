#!/usr/bin/env python3
"""
# ============================================================================ #
# Dosya: cleanup.py
# Yol: /Users/siyahkare/code/telegram-bot/cleanup.py
# İşlev: Proje temizleme aracı
#
# Build: 2025-04-01-01:15:05
# Versiyon: v3.4.0
# ============================================================================ #
#
# Bu script, projede oluşan geçici dosyaları ve logları temizler:
# - __pycache__ dizinleri ve .pyc dosyaları
# - pytest cache
# - Log dosyaları
# - Geçici dosyalar
#
# Kullanım: python cleanup.py [--all|--logs|--cache|--temp]
# ============================================================================ #
"""
import os
import sys
import shutil
import argparse
from pathlib import Path
import datetime

# Proje kök dizini
PROJECT_ROOT = Path(__file__).parent.absolute()

# Hariç tutulacak dizinler
EXCLUDED_DIRS = [".venv", "venv", "env", ".git"]

def should_exclude(path):
    """Belirtilen yol temizlik kapsamının dışında mı kontrol et"""
    path_str = str(path)
    for excluded in EXCLUDED_DIRS:
        if f"/{excluded}/" in path_str or path_str.endswith(f"/{excluded}"):
            return True
    return False

def delete_file(file_path, verbose=True):
    """Dosyayı sil ve isteğe bağlı olarak rapor et"""
    # Hariç tutulan dizinleri kontrol et
    if should_exclude(file_path):
        if verbose:
            print(f"⏭️ Atlandı (korunan): {file_path}")
        return False
        
    try:
        os.remove(file_path)
        if verbose:
            print(f"✅ Silindi: {file_path}")
        return True
    except Exception as e:
        if verbose:
            print(f"❌ Silinemiyor: {file_path} ({e})")
        return False

def delete_directory(dir_path, verbose=True):
    """Dizini sil ve isteğe bağlı olarak rapor et"""
    # Hariç tutulan dizinleri kontrol et
    if should_exclude(dir_path):
        if verbose:
            print(f"⏭️ Atlandı (korunan): {dir_path}")
        return False
        
    try:
        shutil.rmtree(dir_path)
        if verbose:
            print(f"✅ Dizin silindi: {dir_path}")
        return True
    except Exception as e:
        if verbose:
            print(f"❌ Dizin silinemiyor: {dir_path} ({e})")
        return False

def clean_cache_files(verbose=True):
    """Python cache dosyalarını temizle"""
    # __pycache__ dizinlerini bul ve sil (hariç tutulan dizinleri atlayarak)
    all_pycache_dirs = list(PROJECT_ROOT.glob("**/__pycache__"))
    all_pyc_files = list(PROJECT_ROOT.glob("**/*.pyc"))
    
    # Hariç tutulmayan dizinleri filtrele
    pycache_dirs = [d for d in all_pycache_dirs if not should_exclude(d)]
    pyc_files = [f for f in all_pyc_files if not should_exclude(f)]
    
    skipped_items = len(all_pycache_dirs) + len(all_pyc_files) - len(pycache_dirs) - len(pyc_files)
    
    if verbose:
        print(f"\n🧹 {len(pycache_dirs)} __pycache__ dizini ve {len(pyc_files)} .pyc dosyası bulundu")
        if skipped_items > 0:
            print(f"⏭️ {skipped_items} öğe korunan dizinlerde olduğundan atlandı")
    
    deleted_dirs = 0
    for cache_dir in pycache_dirs:
        if delete_directory(cache_dir, verbose):
            deleted_dirs += 1
            
    deleted_files = 0
    for pyc_file in pyc_files:
        if delete_file(pyc_file, verbose):
            deleted_files += 1
    
    # pytest cache temizliği
    pytest_cache = PROJECT_ROOT / ".pytest_cache"
    if pytest_cache.exists() and not should_exclude(pytest_cache):
        if delete_directory(pytest_cache, verbose):
            deleted_dirs += 1
    
    if verbose:
        print(f"\n🧹 Toplam {deleted_dirs} dizin ve {deleted_files} dosya silindi.")
    
    return deleted_dirs + deleted_files

def clean_log_files(verbose=True, days_old=None):
    """Log dosyalarını temizle, isteğe bağlı olarak belirli bir günden eski olanları"""
    log_dir = PROJECT_ROOT / "logs"
    if not log_dir.exists():
        if verbose:
            print("📂 Log dizini bulunamadı.")
        return 0
    
    log_files = list(log_dir.glob("*.log"))
    
    # Belirli bir günden eski logları filtreleme
    if days_old is not None:
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days_old)
        old_log_files = []
        
        for log_file in log_files:
            mod_time = datetime.datetime.fromtimestamp(log_file.stat().st_mtime)
            if mod_time < cutoff_date:
                old_log_files.append(log_file)
        
        log_files = old_log_files
    
    if verbose:
        if days_old is not None:
            print(f"\n🧹 {len(log_files)} log dosyası {days_old} günden eski")
        else:
            print(f"\n🧹 {len(log_files)} log dosyası bulundu")
    
    deleted_files = 0
    for log_file in log_files:
        if delete_file(log_file, verbose):
            deleted_files += 1
    
    if verbose:
        print(f"\n🧹 Toplam {deleted_files} log dosyası silindi.")
    
    return deleted_files

def clean_temp_files(verbose=True):
    """Geçici dosyaları temizle"""
    # .tmp uzantılı dosyaları bul (hariç tutulan dizinleri atlayarak)
    all_temp_files = list(PROJECT_ROOT.glob("**/*.tmp"))
    temp_files = [f for f in all_temp_files if not should_exclude(f)]
    
    # build/, dist/ gibi dizinler
    all_build_dirs = [
        PROJECT_ROOT / "build",
        PROJECT_ROOT / "dist",
        *list(PROJECT_ROOT.glob("**/*.egg-info")),
    ]
    build_dirs = [d for d in all_build_dirs if not should_exclude(d) and d.exists()]
    
    if verbose:
        print(f"\n🧹 {len(temp_files)} geçici dosya ve {len(build_dirs)} build dizini bulundu")
    
    deleted_files = 0
    for temp_file in temp_files:
        if delete_file(temp_file, verbose):
            deleted_files += 1
    
    deleted_dirs = 0
    for build_dir in build_dirs:
        if delete_directory(build_dir, verbose):
            deleted_dirs += 1
    
    if verbose:
        print(f"\n🧹 Toplam {deleted_files} geçici dosya ve {deleted_dirs} build dizini silindi.")
    
    return deleted_files + deleted_dirs

def prompt_user(message):
    """Kullanıcıya bir soru sor ve cevabını al"""
    while True:
        response = input(f"{message} (e/h): ").lower().strip()
        if response in ('e', 'evet', 'y', 'yes'):
            return True
        elif response in ('h', 'hayır', 'n', 'no'):
            return False
        print("Lütfen 'e' veya 'h' girin.")

def main():
    """Ana işlev"""
    parser = argparse.ArgumentParser(description="Telegram Bot projesi temizleme aracı")
    parser.add_argument("--all", action="store_true", help="Tüm geçici dosyaları sil")
    parser.add_argument("--logs", action="store_true", help="Sadece log dosyalarını sil")
    parser.add_argument("--cache", action="store_true", help="Sadece cache dosyalarını sil")
    parser.add_argument("--temp", action="store_true", help="Sadece geçici dosyaları sil")
    parser.add_argument("--days", type=int, default=None, help="Belirli bir günden eski logları sil")
    parser.add_argument("--no-interactive", action="store_true", help="Etkileşimsiz mod")
    parser.add_argument("--exclude", nargs="+", default=[], help="Hariç tutulacak ek dizinler")
    
    args = parser.parse_args()
    
    # Ek hariç tutulacak dizinleri ekle
    EXCLUDED_DIRS.extend(args.exclude)
    
    # Hiçbir argüman verilmemişse interaktif mod
    if not args.all and not args.logs and not args.cache and not args.temp and not args.no_interactive:
        print("👋 Telegram Bot Temizleme Aracına Hoş Geldiniz")
        print("===============================================")
        print(f"📁 Korunan dizinler: {', '.join(EXCLUDED_DIRS)}")
        print("===============================================")
        
        cache = prompt_user("📁 Cache dosyaları silinsin mi? (__pycache__, .pyc, pytest)")
        logs = prompt_user("📝 Log dosyaları silinsin mi?")
        temp = prompt_user("🗑️  Geçici dosyalar silinsin mi? (.tmp, build)")
        
        if cache:
            clean_cache_files()
        if logs:
            days = None
            if prompt_user("🕒 Sadece belirli bir günden eski loglar silinsin mi?"):
                try:
                    days = int(input("Kaç günden eski loglar silinsin? "))
                except ValueError:
                    print("Geçersiz değer, tüm loglar silinecek.")
            clean_log_files(days_old=days)
        if temp:
            clean_temp_files()
    else:
        if args.all or args.cache:
            clean_cache_files()
        if args.all or args.logs:
            clean_log_files(days_old=args.days)
        if args.all or args.temp:
            clean_temp_files()
    
    print("\n✨ Temizlik tamamlandı!")
    return 0

if __name__ == "__main__":
    sys.exit(main())