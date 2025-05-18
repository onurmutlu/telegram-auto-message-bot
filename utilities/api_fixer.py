#!/usr/bin/env python3
# filepath: /Users/siyahkare/code/telegram-bot/api_fixer.py
"""
Telegram API kimlik bilgilerini otomatik olarak düzeltir.
Bu betik:
1. .env dosyasını kontrol eder ve doğru API_HASH değerini ayarlar
2. Tüm oturum dosyalarını temizler
3. Bot'u yeniden başlatmak için talimatlar verir
"""
import os
import sys
import shutil

# Renk kodları
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_color(text, color=YELLOW):
    """Renkli metin yazdır"""
    print(f"{color}{text}{RESET}")

def main():
    """Ana işlev"""
    print_color("=" * 60, GREEN)
    print_color("TELEGRAM API KİMLİK BİLGİSİ DÜZELTME ARACI", GREEN)
    print_color("=" * 60, GREEN)
    
    # 1. .env dosyasını kontrol et ve düzelt
    env_path = ".env"
    if not os.path.exists(env_path):
        print_color(f"HATA: .env dosyası bulunamadı: {env_path}", RED)
        return False
    
    # Yedek al
    env_backup = f"{env_path}.bak"
    shutil.copy2(env_path, env_backup)
    print_color(f".env dosyasının yedeği alındı: {env_backup}", BLUE)
    
    # .env içeriğini oku
    with open(env_path, "r") as f:
        env_content = f.readlines()
    
    # API_HASH satırını bul ve düzelt
    new_content = []
    api_hash_updated = False
    
    for line in env_content:
        if line.strip().startswith("API_HASH="):
            # Değiştirme yapılacak
            old_value = line.strip()
            new_line = "API_HASH=ff5d6053b266f78d129f9343f40e77e\n"
            new_content.append(new_line)
            api_hash_updated = True
            print_color(f"API_HASH değeri güncellendi:\n  Eski: {old_value}\n  Yeni: {new_line.strip()}", GREEN)
        else:
            new_content.append(line)
    
    # Değişiklik yoksa bildir
    if not api_hash_updated:
        print_color("API_HASH satırı bulunamadı, değişiklik yapılmadı.", YELLOW)
    else:
        # Değişiklikleri kaydet
        with open(env_path, "w") as f:
            f.writelines(new_content)
        print_color(".env dosyası başarıyla güncellendi.", GREEN)
    
    # 2. Oturum dosyalarını temizle
    print_color("\nOturum dosyaları temizleniyor...", BLUE)
    cleaned = 0
    
    for filename in os.listdir("."):
        if filename.endswith(".session") or filename.endswith(".session-journal"):
            try:
                os.remove(filename)
                print_color(f"Silindi: {filename}")
                cleaned += 1
            except Exception as e:
                print_color(f"Silinemedi: {filename} - {e}", RED)
    
    print_color(f"Toplam {cleaned} oturum dosyası temizlendi.", GREEN if cleaned > 0 else YELLOW)
    
    # 3. Sonuç ve talimatlar
    print_color("\n" + "=" * 60, GREEN)
    print_color("İŞLEM TAMAMLANDI", GREEN)
    print_color("=" * 60, GREEN)
    print_color("\nYapılan değişiklikler:")
    print_color("1. API_HASH değeri güncellendi: ff5d6053b266f78d129f9343f40e77e")
    print_color(f"2. {cleaned} adet oturum dosyası temizlendi.")
    
    print_color("\nSıradaki adımlar:", BLUE)
    print_color("1. Çalışan tüm bot süreçlerini sonlandırın:", BLUE)
    print_color("   kill $(lsof -ti :8000) 2>/dev/null", YELLOW)
    print_color("2. Bot'u yeniden başlatın:", BLUE)
    print_color("   bash start.sh", YELLOW)
    
    return True

if __name__ == "__main__":
    if main():
        sys.exit(0)
    else:
        sys.exit(1)
