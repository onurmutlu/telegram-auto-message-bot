#!/usr/bin/env python3
# API kimliklerini doğrulayan test betiği

import os
import sys
import logging
from dotenv import load_dotenv
import time

# .env dosyasını yükle
load_dotenv(verbose=True)

# Loglama yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("api_test.log")
    ]
)

logger = logging.getLogger(__name__)

def main():
    # Banner göster
    print("\n" + "="*50)
    print("TELEGRAM API KİMLİK DOĞRULAMA TEST ARACI")
    print("="*50)
    
    # Çalışma dizinini göster
    print(f"\nÇalışma dizini: {os.getcwd()}")
    print(f"Python sürümü: {sys.version}\n")
    
    # API bilgilerini al
    api_id = os.getenv("API_ID", "Tanımsız")
    api_hash = os.getenv("API_HASH", "Tanımsız")
    session_name = os.getenv("SESSION_NAME", "Tanımsız")
    phone = os.getenv("PHONE", "Tanımsız")
    
    # API bilgilerini görüntüle
    print("API Kimlik Bilgileri:")
    print(f"API ID: {api_id}")
    
    # API_HASH güvenliği için sadece ilk ve son 5 karakteri göster
    if api_hash != "Tanımsız" and len(api_hash) > 10:
        displayed_hash = f"{api_hash[:5]}...{api_hash[-5:]}"
        hash_length = len(api_hash)
    else:
        displayed_hash = api_hash
        hash_length = len(api_hash) if api_hash != "Tanımsız" else 0
        
    print(f"API HASH: {displayed_hash} (Uzunluk: {hash_length} karakter)")
    print(f"Session adı: {session_name}")
    print(f"Telefon numarası: {phone}")
    
    # API_HASH değerini karakter karakter incele
    if api_hash != "Tanımsız":
        print("\nAPI_HASH Karakter Analizi:")
        for i, char in enumerate(api_hash):
            print(f"Pozisyon {i+1}: '{char}' (ASCII: {ord(char)})")
    
    # Doğru API_HASH ile karşılaştır
    expected_hash = "ff5d6053b266f78d1293f9343f40e77e"
    if api_hash == expected_hash:
        print("\n✅ API_HASH değeri doğru.")
    else:
        print("\n❌ API_HASH değeri beklenen değerden farklı!")
        print(f"  Beklenen: {expected_hash}")
        print(f"  Okunan:   {api_hash}")
        
        # Farklılıkları göster
        if api_hash != "Tanımsız":
            print("\nFarklılık analizi:")
            for i, (expected, actual) in enumerate(zip(expected_hash, api_hash)):
                if expected != actual:
                    print(f"  Pozisyon {i+1}: Beklenen '{expected}', Okunan '{actual}'")
            
            # Uzunluk farklı mı?
            if len(expected_hash) != len(api_hash):
                print(f"\n  Uzunluk farklı: Beklenen {len(expected_hash)}, Okunan {len(api_hash)}")
                
                # Hangi karakterlerin eksik olduğunu bul
                if len(expected_hash) > len(api_hash):
                    # Karakterleri eşleştirerek eksik olanı bul
                    for i in range(min(len(expected_hash), len(api_hash))):
                        if expected_hash[i] != api_hash[i]:
                            print(f"  İlk farklılık pozisyon {i+1}'de: Beklenen '{expected_hash[i]}', Okunan '{api_hash[i]}'")
                            break
                    else:
                        # Burada her iki dizi aynı, ancak biri daha kısa
                        missing = expected_hash[len(api_hash):]
                        print(f"  Eksik karakterler: '{missing}' (pozisyon {len(api_hash)+1}'den itibaren)")
    
    print("\nTest tamamlandı.")
    
    # Dosyaların görülebildiğini bir saniye bekle
    print("\nÇıktının tamamlanması için bekleniyor...")
    time.sleep(1)

if __name__ == "__main__":
    main()
