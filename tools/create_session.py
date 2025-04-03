from telethon.sync import TelegramClient
import os
from dotenv import load_dotenv

# Debug ekleyelim
print(f"Çalışma dizini: {os.getcwd()}")

# Tam yol belirterek .env dosyasını yükle
env_path = os.path.join(os.path.dirname(__file__), '.env')
print(f".env tam yolu: {env_path}")
print(f".env dosyası var mı: {os.path.exists(env_path)}")
load_dotenv(dotenv_path=env_path)

# .env dosyasının içeriğini göster (güvenlik için bazı karakterleri gizleyerek)
if os.path.exists(env_path):
    with open(env_path, 'r') as f:
        for line in f:
            if line.strip() and "=" in line:
                key, val = line.strip().split('=', 1)
                if 'API' in key:
                    masked_val = val[:4] + '*' * (len(val) - 8) + val[-4:] if len(val) > 8 else '****'
                    print(f"{key}={masked_val}")
                elif 'PHONE' in key:
                    masked_val = val[:4] + '*' * (len(val) - 7) + val[-3:] if len(val) > 7 else '****'
                    print(f"{key}={masked_val}")

# Telegram API bilgilerinizi doğrudan girin
api_id = 23692263  # API ID'nizi buraya yazın (sayısal değer olmalı)
api_hash = 'ff5d6053b266f78d1293f9343f40e77e'  # API Hash'inizi buraya yazın
phone_number = '+905382617727'  # Telefon numaranızı buraya yazın

# Oturum dosyası oluştur
with TelegramClient("mysession", api_id, api_hash) as client:
    print("📱 Telegram'a bağlanılıyor...")
    
    # Oturum aç
    if not client.is_user_authorized():
        client.send_code_request(phone_number)
        code = input("Telefonunuza gelen kodu girin: ")
        try:
            client.sign_in(phone_number, code)
        except Exception as e:
            if "Two-steps verification" in str(e):
                password = input("İki faktörlü doğrulama şifrenizi girin: ")
                client.sign_in(password=password)
    
    me = client.get_me()
    print(f"✅ Oturum başarıyla oluşturuldu: {me.username} ({me.first_name})")
    print(f"💾 Session dosyası: mysession.session")