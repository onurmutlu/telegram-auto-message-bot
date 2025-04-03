"""
# ============================================================================ #
# Dosya: update_headers.py
# Yol: /Users/siyahkare/code/telegram-bot/tests/update_headers.py
# İşlev: Telegram bot bileşeni
#
# Build: 2025-04-01-00:07:55
# Versiyon: v3.4.0
# ============================================================================ #
#
# Bu modül, Telegram bot uygulamasının bileşenlerinden biridir.
# - İlgili servislere entegrasyon
# - Hata yönetimi ve loglama
# - Asenkron işlem desteği
#
# ============================================================================ #
"""

#!/usr/bin/env python3
"""
Header güncelleyici
"""
import os
import sys
import datetime
import re
from pathlib import Path

# Güncel zaman damgası oluştur
TIMESTAMP = datetime.datetime.now().strftime("%Y-%m-%d-%H:%M:%S")
VERSION = "v3.4.0"

# Dosya açıklamaları sözlüğü - genişletin
FILE_DESCRIPTIONS = {
    "conftest.py": "Telegram bot test ortamı ve fixture'lar",
    "test_message_service.py": "MessageService sınıfı için birim testler",
    "test_reply_service.py": "ReplyService sınıfı için birim testler",
    "test_dm_service.py": "DirectMessageService sınıfı için birim testler",
    "test_error_handler.py": "ErrorHandler sınıfı için birim testler",
    "test_integration.py": "Servisler arası entegrasyon testleri",
    "message_service.py": "Gruplara otomatik mesaj gönderim servisi",
    "reply_service.py": "Bot yanıtlarını yöneten servis",
    "dm_service.py": "Direkt mesaj ve davet servisi",
    "error_handler.py": "Hata yakalama ve işleme araçları"
}

# Dosya detay açıklamaları
FILE_DETAILS = {
    "conftest.py": [
        "Bu modül, test ortamı için gerekli tüm fixture'ları içerir:",
        "- Mock servisler (MessageService, ReplyService, DirectMessageService)",
        "- Test yapılandırma (Config) ve veritabanı (UserDatabase)",
        "- Log yapılandırma ve test raporlama araçları", 
        "- Asenkron test desteği ve pytest hook'ları",
        "",
        "Kullanım: pytest ile otomatik olarak yüklenir"
    ],
    "test_message_service.py": [
        "Bu modül, MessageService sınıfının işlevlerini test eder:",
        "- Grup mesajları gönderme",
        "- Çalıştırma/durdurma ve durum yönetimi",
        "- Grup aktivite analizi ve mesaj zamanlaması",
        "",
        "Kullanım: python -m pytest tests/test_message_service.py -v"
    ],
    "test_error_handler.py": [
        "Bu modül, ErrorHandler sınıfı için kapsamlı test senaryoları içerir:",
        "- Başlatma ve yapılandırma testleri",
        "- Metod varlık ve davranış testleri",
        "- Hata durumlarının kontrolü",
        "",
        "Kullanım: python -m pytest tests/test_error_handler.py -v"
    ]
    # Diğer dosyalar için detaylar eklenebilir
}

def get_description(filename):
    """Dosya için açıklama metni döndürür"""
    base_name = os.path.basename(filename)
    return FILE_DESCRIPTIONS.get(base_name, "Telegram bot bileşeni")

def get_details(filename):
    """Dosya için detay açıklamaları döndürür"""
    base_name = os.path.basename(filename)
    
    if base_name in FILE_DETAILS:
        return FILE_DETAILS[base_name]
    
    # Genel detaylar
    if base_name.startswith("test_"):
        # Test dosyası için varsayılan detaylar
        return [
            f"Bu test modülü, {base_name[5:-3]} için birim testleri içerir:",
            "- Temel işlevsellik testleri",
            "- Sınır koşulları ve hata durumları",
            "- Mock nesnelerle izolasyon",
            "",
            f"Kullanım: python -m pytest tests/{base_name} -v"
        ]
    else:
        # Uygulama dosyası için varsayılan detaylar
        return [
            "Bu modül, Telegram bot uygulamasının bileşenlerinden biridir.",
            "- İlgili servislere entegrasyon",
            "- Hata yönetimi ve loglama",
            "- Asenkron işlem desteği"
        ]

def update_header(file_path):
    """Dosya header'ını günceller"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Dosya adı ve açıklaması
    filename = os.path.basename(file_path)
    description = get_description(filename)
    details = get_details(filename)
    
    # Yeni header oluştur
    new_header = [
        '"""',
        "# ============================================================================ #",
        f"# Dosya: {filename}",
        f"# Yol: {file_path}",
        f"# İşlev: {description}",
        "#",
        f"# Build: {TIMESTAMP}",
        f"# Versiyon: {VERSION}",
        "# ============================================================================ #",
        "#"
    ]
    
    # Detayları ekle
    for line in details:
        new_header.append(f"# {line}")
    
    new_header.append("#")
    new_header.append("# ============================================================================ #")
    new_header.append('"""')
    
    # Mevcut docstring'i ara ve değiştir
    docstring_pattern = r'"""[\s\S]*?"""'
    if re.match(docstring_pattern, content.lstrip()):
        # Docstring varsa değiştir
        new_content = re.sub(docstring_pattern, '\n'.join(new_header), content.lstrip(), count=1)
    else:
        # Docstring yoksa ekle
        new_content = '\n'.join(new_header) + '\n\n' + content
    
    # Dosyayı güncelle
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"✅ {file_path} güncellendi")

def main():
    """Ana işlev"""
    if len(sys.argv) < 2:
        print("Kullanım: python update_headers.py <dizin_veya_dosya>")
        sys.exit(1)
    
    target = sys.argv[1]
    
    if os.path.isdir(target):
        # Dizindeki tüm .py dosyalarını güncelle
        for root, _, files in os.walk(target):
            for file in files:
                if file.endswith('.py'):
                    update_header(os.path.join(root, file))
    elif os.path.isfile(target) and target.endswith('.py'):
        # Tek dosyayı güncelle
        update_header(target)
    else:
        print(f"Hata: {target} geçerli bir Python dosyası veya dizin değil")
        sys.exit(1)

if __name__ == "__main__":
    main()