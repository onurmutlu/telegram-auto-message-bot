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
   ```bash
   pip install -r requirements.txt
   ```
3. .env dosyasını yapılandırın:

API_ID=your_api_id 
API_HASH=your_api_hash 
PHONE_NUMBER=your_phone_number

4. Botu çalıştırın:
   ```bash
   python main.py
   ```

## Kullanım

Bot komutları:
- `p` - Duraklat/Devam et
- `s` - Durum bilgisi göster
- `q` - Çıkış
- `h` - Yardım mesajı

## Yapılandırma

Mesaj şablonları ve diğer ayarlar `data` klasöründeki JSON dosyalarında saklanır:
- `messages.json`: Gruplara gönderilen genel mesajlar
- `invites.json`: Davet mesajları ve yönlendirmeler
- `responses.json`: Yanıt şablonları

## Loglama

Tüm işlemler `logs/bot.log` dosyasında detaylı olarak kaydedilir ve aynı zamanda konsola renkli formatta gösterilir.

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
│   └── logger.py             # Loglama yardımcıları
│
├── session/                  # Telegram oturum dosyaları
│   ├── member_session.session
│   └── member_session.session-journal
│
├── data/                     # Veri dosyaları
│   ├── users.db              # SQLite veritabanı
│   ├── messages.json         # Grup mesaj şablonları
│   ├── invites.json          # Davet şablonları
│   └── responses.json        # Yanıt şablonları
│
└── logs/                     # Log dosyaları
    └── bot.log               # Bot log kayıtları

## Lisans

Bu ürün, özel ticari lisans altında dağıtılmaktadır. Kiralama modeli ile kullandırılabilir. Daha fazla bilgi için SiyahKare Yazılım (@SiyahKare) ile iletişime geçin.

Copyright © 2025 SiyahKare Yazılım (@SiyahKare). Tüm hakları saklıdır.

