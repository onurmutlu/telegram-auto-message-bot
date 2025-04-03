"""
# ============================================================================ #
# Dosya: test_message_loading.py
# Yol: /Users/siyahkare/code/telegram-bot/tests/test_message_loading.py
# İşlev: Telegram bot bileşeni
#
# Build: 2025-04-01-00:07:55
# Versiyon: v3.4.0
# ============================================================================ #
#
# Bu test modülü, message_loading için birim testleri içerir:
# - Temel işlevsellik testleri
# - Sınır koşulları ve hata durumları
# - Mock nesnelerle izolasyon
# 
# Kullanım: python -m pytest tests/test_message_loading.py -v
#
# ============================================================================ #
"""

#!/usr/bin/env python3
# test_message_loading.py

import os
import sys
import json
from pathlib import Path

# Çalışma dizinini kontrol et ve gerekirse değiştir
current_dir = Path.cwd()
print(f"Çalışma dizini: {current_dir}")

# Proje kök dizinini bul
if current_dir.name == "telegram_bot":
    project_root = current_dir
elif current_dir.name == "tests" and current_dir.parent.name == "telegram_bot":
    project_root = current_dir.parent
elif current_dir.name == "python" and (current_dir / "telegram_bot").exists():
    project_root = current_dir / "telegram_bot"
else:
    # Sabit yol kullan
    project_root = Path("/Users/siyahkare/code/python/telegram_bot")

print(f"Proje kök dizini: {project_root}")

# data dizinini kontrol et
data_dir = project_root / "data"
print(f"Kontrol edilen data dizini: {data_dir}")

if not data_dir.exists():
    print(f"HATA: 'data' dizini bulunamadı: {data_dir}")
    sys.exit(1)

# messages.json dosyasını kontrol et
messages_file = data_dir / "messages.json"
if not messages_file.exists():
    print(f"HATA: 'messages.json' dosyası bulunamadı: {messages_file}")
    sys.exit(1)

# JSON formatını kontrol et
try:
    with open(messages_file, 'r', encoding='utf-8') as f:
        messages_data = json.load(f)
    
    # Format kontrol: doğrudan liste veya nesnedeki 'group_messages' listesi
    if isinstance(messages_data, list):
        messages = messages_data
        print("Doğrudan liste formatı kullanılıyor (önerilen)")
    elif isinstance(messages_data, dict) and "group_messages" in messages_data:
        messages = messages_data["group_messages"]
        print("Eski nesne formatı kullanılıyor ('group_messages' anahtarı)")
    else:
        print("HATA: Desteklenmeyen mesaj formatı")
        sys.exit(1)
    
    if not isinstance(messages, list):
        print("HATA: Mesajlar bir liste değil")
        sys.exit(1)
    
    print(f"BAŞARILI: {len(messages)} adet mesaj şablonu yüklendi")
    print("İlk 3 mesaj:")
    for i, msg in enumerate(messages[:3]):
        print(f"{i+1}. {msg[:50]}{'...' if len(msg) > 50 else ''}")
    
except json.JSONDecodeError as e:
    print(f"HATA: 'messages.json' geçersiz JSON format: {str(e)}")
    sys.exit(1)
except Exception as e:
    print(f"HATA: {str(e)}")
    sys.exit(1)