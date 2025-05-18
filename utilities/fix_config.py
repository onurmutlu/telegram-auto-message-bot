#!/usr/bin/env python3
# filepath: /Users/siyahkare/code/telegram-bot/fix_config.py
"""
API kimlik bilgilerinin doğru yüklenmesini zorlamak için config.py'yi düzenler.
"""
import os

print("API Kimlik Bilgilerini Düzeltme Aracı\n")

# .env dosyasından değerleri oku
env_path = os.path.join(os.getcwd(), '.env')
if not os.path.exists(env_path):
    print(f"HATA: {env_path} bulunamadı.")
    exit(1)

# Doğru API kimlik bilgileri
CORRECT_API_ID = 23692263
CORRECT_API_HASH = "ff5d6053b266f78d129f9343f40e77e"

print(f"Doğru API_ID: {CORRECT_API_ID}")
print(f"Doğru API_HASH: {CORRECT_API_HASH}\n")

# Dosyaya yaz
with open(env_path, 'r') as f:
    content = f.read()

# API_ID ve API_HASH değerlerini değiştir
import re

content = re.sub(r'API_ID=.*', f'API_ID={CORRECT_API_ID}', content)
content = re.sub(r'API_HASH=.*', f'API_HASH={CORRECT_API_HASH}', content)

with open(env_path, 'w') as f:
    f.write(content)

print(".env dosyası güncellendi.")

# app/core/config.py için doğrudan değer düzeltmesi
config_path = os.path.join(os.getcwd(), 'app', 'core', 'config.py')
if not os.path.exists(config_path):
    print(f"UYARI: {config_path} bulunamadı.")
else:
    with open(config_path, 'r') as f:
        config_content = f.read()
    
    # API_ID ve API_HASH validator'larını güçlendir
    api_id_validator = """
    @validator("API_ID", pre=True, always=True)
    def validate_api_id(cls, v):
        # Doğrudan doğru değeri kullan
        return 23692263
    """
    
    api_hash_validator = """
    @validator("API_HASH", pre=True, always=True)
    def validate_api_hash(cls, v):
        # Doğrudan doğru değeri kullan
        return "ff5d6053b266f78d129f9343f40e77e"
    """
    
    # Önceki validator'ları bul ve değiştir
    config_content = re.sub(
        r'@validator\("API_ID",[^\}]+\}',
        api_id_validator,
        config_content
    )
    
    config_content = re.sub(
        r'@validator\("API_HASH",[^\}]+\}',
        api_hash_validator,
        config_content
    )
    
    with open(config_path, 'w') as f:
        f.write(config_content)
    
    print("app/core/config.py dosyası güncellendi.")

# app/main.py için ClientSession oluşturma sırasında doğrudan değerleri kullan
main_path = os.path.join(os.getcwd(), 'app', 'main.py')
if os.path.exists(main_path):
    with open(main_path, 'r') as f:
        main_content = f.read()
    
    main_content = re.sub(
        r'self.client\s*=\s*TelegramClient\([^)]+\)',
        f'self.client = TelegramClient(settings.SESSION_NAME, {CORRECT_API_ID}, "{CORRECT_API_HASH}", device_model="Python Bot", system_version="1.0", app_version="1.0")',
        main_content
    )
    
    with open(main_path, 'w') as f:
        f.write(main_content)
    
    print("app/main.py dosyası güncellendi.")

# Oturum dosyalarını temizle
import glob
session_files = glob.glob("*.session*")
for session_file in session_files:
    try:
        os.remove(session_file)
        print(f"Oturum dosyası silindi: {session_file}")
    except:
        pass

print("\nTüm güncellemeler tamamlandı. Şimdi tekrar deneyin:")
print("bash start.sh")
