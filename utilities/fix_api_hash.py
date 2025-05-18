#!/usr/bin/env python3
"""
API HASH doğrulama ve düzeltme aracı.
Bu betik, hatalı bir şekilde kesilen API_HASH değerini bulur ve
tam ve doğru API_HASH ile değiştirir.
"""
import os
import sys
import re
import dotenv
import logging

# Loglama ayarlama
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def main():
    print("\n== API HASH DÜZELTME ARACI ==\n")
    
    # .env dosyasını yükle
    dotenv_path = os.path.join(os.getcwd(), '.env')
    if not os.path.exists(dotenv_path):
        logger.error(f"HATA: .env dosyası bulunamadı: {dotenv_path}")
        return False
    
    # .env içeriğini oku
    with open(dotenv_path, 'r') as f:
        env_content = f.read()
    
    # API_HASH değerini bul
    api_hash_match = re.search(r'API_HASH=([^\n]+)', env_content)
    if not api_hash_match:
        logger.error("HATA: .env dosyasında API_HASH değeri bulunamadı.")
        return False
    
    current_api_hash = api_hash_match.group(1)
    logger.info(f"Mevcut API_HASH: {current_api_hash}")
    
    # API_HASH uzunluğunu kontrol et
    if len(current_api_hash) == 32:
        logger.info("API_HASH değeri zaten 32 karakter uzunluğunda ve doğru formatta görünüyor.")
        choice = input("Yine de değiştirmek istiyor musunuz? (e/h): ").lower()
        if choice != 'e':
            logger.info("İşlem iptal edildi.")
            return True
    else:
        logger.warning(f"DİKKAT: API_HASH değeri 32 karakter değil ({len(current_api_hash)} karakter).")
        logger.warning("Bu, API kimlik doğrulama hatalarına neden olabilir.")
    
    # Yeni API_HASH değerini iste
    logger.info("\nLütfen my.telegram.org adresinden tam ve doğru API_HASH değerinizi girin.")
    logger.info("API_HASH değeri 32 karakter uzunluğunda olmalıdır.")
    new_api_hash = input("Yeni API_HASH değeri: ").strip()
    
    # Yeni değeri doğrula
    if len(new_api_hash) != 32:
        logger.warning(f"Girilen değer 32 karakter değil ({len(new_api_hash)} karakter).")
        choice = input("Yine de devam etmek istiyor musunuz? (e/h): ").lower()
        if choice != 'e':
            logger.info("İşlem iptal edildi.")
            return False
    
    # Değiştir
    new_env_content = env_content.replace(f'API_HASH={current_api_hash}', f'API_HASH={new_api_hash}')
    
    # Değişikliği kaydet
    with open(dotenv_path, 'w') as f:
        f.write(new_env_content)
    
    logger.info(f"\nAPI_HASH değeri başarıyla güncellendi: {new_api_hash}")
    logger.info("Artık botunuzu yeniden başlatabilirsiniz.")
    return True

if __name__ == "__main__":
    if main():
        sys.exit(0)
    else:
        sys.exit(1)
