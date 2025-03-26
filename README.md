# Telegram Auto Message Bot

Ticari kullanım için tasarlanmış, Telegram gruplarına otomatik mesaj gönderen ve özel mesajları yöneten gelişmiş bir bot.

## Özellikler

- Gruplara otomatik ve özelleştirilmiş mesaj gönderimi
- Özel mesaj yönetimi ve grup davetlerinin otomatizasyonu
- Yönetici ve kurucu kontrolü ile güvenli kullanım
- Davet gönderimi için kullanıcı veritabanı yönetimi
- Detaylı loglama sistemi ve durum raporları
- Rate limiting ve akıllı gecikme sistemi

## Gereksinimler

- Python 3.7+
- Telethon kütüphanesi
- Telegram API kimlik bilgileri

## Kurulum

1. Repository'yi klonlayın
2. Bağımlılıkları yükleyin:
   pip install -r requirements.txt

3. .env dosyasını yapılandırın:
   API_ID=your_api_id 
   API_HASH=your_api_hash 
   PHONE_NUMBER=your_phone_number

4. Botu çalıştırın:
   python main.py

## Kullanım

Bot komutları:
- p - Duraklat/Devam et
- s - Durum bilgisi göster
- c - Konsolu temizle
- d - Debug modu aç/kapat
- u - Kullanıcı istatistiklerini göster
- q - Çıkış
- h - Yardım mesajı

### Komut Satırı Argümanları

Bot çeşitli komut satırı argümanlarıyla çalıştırılabilir:

# Debug modunda çalıştır
python main.py --debug

# Hata veren grupları sıfırla
python main.py --reset-errors

# Veritabanı optimizasyonu yap
python main.py --optimize-db

# Geliştirici modunda çalıştır
python main.py --env development

Kısa form komutlar da kullanılabilir:
- -d = --debug
- -r = --reset-errors  
- -o = --optimize-db
- -e = --env
- -b = --backup

## Test Etme

Bot uygulamasını test etmek için aşağıdaki yöntemler kullanılabilir:

### 1. Manuel Test

Temel işlevleri test etmek için:
# Debug modunda çalıştırarak
python main.py --debug

# Debug modunda ve veritabanını optimize ederek
python main.py --debug --optimize-db

### 2. Birim Testler

Birim testleri çalıştırmak için pytest paketini yükleyin:
pip install pytest pytest-asyncio pytest-cov

Testleri çalıştırma:
# Tek bir test dosyasını çalıştır
pytest tests/test_user_db.py -v

# Tüm testleri çalıştır
pytest tests/ -v

# Kod kapsama raporuyla testleri çalıştır
pytest --cov=bot --cov=database tests/

### 3. Telegram API Testi

Telegram API testleri yaparken dikkat edilmesi gerekenler:
- Test hesabı kullanın, ana hesabınızı kullanmaktan kaçının
- Az sayıda mesaj göndererek rate limiting'e takılmaktan kaçının
- API kısıtlamalarını test etmek için küçük sayılarla başlayın

## Yapılandırma

Mesaj şablonları ve diğer ayarlar data klasöründeki JSON dosyalarında saklanır:
- messages.json: Gruplara gönderilen genel mesajlar
- invites.json: Davet mesajları ve yönlendirmeler
- responses.json: Yanıt şablonları

## Loglama

Tüm işlemler logs/bot.log dosyasında detaylı olarak kaydedilir ve aynı zamanda konsola renkli formatta gösterilir.

## Gelişmiş Özellikler

- Flood kontrolü ve akıllı gecikme yönetimi
- Hata veren grupların otomatik tespiti
- Kullanıcı takibi ve veritabanı yönetimi
- Komut satırı kontrolü ve durum raporlama

## Dosya Yapısı

telegram_bot/
├── main.py                   # Ana program dosyası
├── requirements.txt          # Proje bağımlılıkları
├── .env                      # API kimlik bilgileri (gitignore'da)
├── README.md                 # Proje dokümantasyonu
├── LICENSE                   # Ticari lisans bilgisi
├── .gitignore                # Git dışlama dosyası
├── CHANGELOG.md              # Değişiklik kaydı
│
├── bot/                      # Bot modülleri
│   ├── __init__.py
│   ├── base.py               # Temel bot sınıfı
│   └── message_bot.py        # Ana bot uygulaması
│
├── config/                   # Yapılandırma modülleri
│   ├── __init__.py
│   └── settings.py           # Yapılandırma yönetimi
│
├── database/                 # Veritabanı işlemleri
│   ├── __init__.py
│   └── user_db.py            # Kullanıcı veritabanı yönetimi
│
├── utils/                    # Yardımcı modüller
│   ├── __init__.py
│   ├── logger.py             # Loglama yardımcıları
│   └── monitor.py            # Çalışma zamanı monitörü
│
├── tests/                    # Test dosyaları
│   ├── __init__.py
│   ├── test_user_db.py       # Veritabanı testleri
│   └── test_bot.py           # Bot fonksiyonları testleri
│
├── session/                  # Telegram oturum dosyaları
│   ├── member_session.session
│   └── member_session.session-journal
│
├── data/                     # Veri dosyaları
│   ├── users.db              # SQLite veritabanı
│   ├── backups/              # Veritabanı yedekleri
│   ├── messages.json         # Grup mesaj şablonları
│   ├── invites.json          # Davet şablonları
│   └── responses.json        # Yanıt şablonları
│
└── logs/                     # Log dosyaları
    ├── bot.log               # Bot log kayıtları
    └── detailed_bot.json     # Detaylı JSON formatında log

## Lisans

Bu ürün, özel ticari lisans altında dağıtılmaktadır. Kiralama modeli ile kullandırılabilir. Daha fazla bilgi için Arayiş Yazılım ile iletişime geçin.

Copyright © 2025 Arayiş Yazılım. Tüm hakları saklıdır.