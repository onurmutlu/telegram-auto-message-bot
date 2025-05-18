#!/usr/bin/env python3
# Ortam değişkenlerini okuyan test betiği

import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

# Ana klasördeki .env dosyasının tam yolunu al
env_path = Path('/Users/siyahkare/code/telegram-bot/.env')

print(f"Kontrol edilen .env dosyası: {env_path}")
print(f"Dosya var mı: {env_path.exists()}")

# Varsa dosyadaki içeriği doğrudan oku ve ekrana bas
if env_path.exists():
    print("\n.env dosyasının RAW içeriği:")
    with open(env_path, 'r') as f:
        env_content = f.read()
        print(env_content)

# Ortam değişkenlerini yükle
print("\nDotenv kütüphanesi ile .env dosyası yükleniyor...")
load_dotenv(dotenv_path=env_path, verbose=True)

# Ortam değişkenlerini oku
api_id = os.getenv("API_ID", "Tanımsız")
api_hash = os.getenv("API_HASH", "Tanımsız")

print("\nÇevre değişkenleri:")
print(f"API_ID: {api_id}")
print(f"API_HASH: {api_hash}")

# Doğrudan dosyayı satır satır oku ve API_HASH satırını bul
print("\nDosyadan doğrudan API_HASH satırı okunuyor:")
if env_path.exists():
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith("API_HASH="):
                print(f"Bulunan satır: {line}")
                api_hash_value = line.split("=", 1)[1]
                print(f"API_HASH değeri: {api_hash_value}")
                print(f"Karakter sayısı: {len(api_hash_value)}")
                
                # Doğru API_HASH ile karşılaştır
                expected_hash = "ff5d6053b266f78d1293f9343f40e77e"
                if api_hash_value == expected_hash:
                    print("✅ Dosyadaki API_HASH değeri doğru.")
                else:
                    print("❌ Dosyadaki API_HASH değeri beklenen değerden farklı!")
                    print(f"  Beklenen: {expected_hash}")
                    print(f"  Dosyada:  {api_hash_value}")
                break

print("\nTest tamamlandı.")
time.sleep(1)  # Çıktının görülebilmesi için bekle
