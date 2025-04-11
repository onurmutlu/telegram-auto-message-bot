# Telegram Auto Message Bot - Ticari Lisanslı Gelişmiş Pazarlama ve Yönetim Aracı v3.5.0

Telegram Auto Message Bot, işletmelerin ve topluluk yöneticilerinin Telegram gruplarını etkili bir şekilde yönetmeleri, pazarlama stratejilerini otomatikleştirmeleri ve kullanıcı etkileşimini artırmaları için tasarlanmış, ticari lisanslı gelişmiş bir araçtır. Bu bot, Telegram'daki varlığınızı güçlendirmenize, hedef kitlenize ulaşmanıza ve marka bilinirliğinizi artırmanıza yardımcı olur.

## İçindekiler
- [Telegram Auto Message Bot - Ticari Lisanslı Gelişmiş Pazarlama ve Yönetim Aracı v3.5.0](#telegram-auto-message-bot---ticari-lisanslı-gelişmiş-pazarlama-ve-yönetim-aracı-v350)
  - [İçindekiler](#i̇çindekiler)
  - [Neden Telegram Auto Message Bot?](#neden-telegram-auto-message-bot)
  - [v3.5.0'daki Yeni Özellikler](#v350daki-yeni-özellikler)
  - [Temel Özellikler](#temel-özellikler)
  - [Gelişmiş Özellikler](#gelişmiş-özellikler)
  - [Gereksinimler](#gereksinimler)
  - [Kurulum](#kurulum)
  - [Kullanım](#kullanım)
    - [Temel Bot Komutları](#temel-bot-komutları)
    - [Komut Satırı Argümanları](#komut-satırı-argümanları)
  - [Test Etme](#test-etme)
    - [1. Manuel Test](#1-manuel-test)
    - [2. Birim Testler](#2-birim-testler)
    - [3. Telegram API Testi](#3-telegram-api-testi)
  - [Yapılandırma](#yapılandırma)
  - [Loglama](#loglama)
  - [Dosya Yapısı](#dosya-yapısı)
  - [Yardımcı Araçlar](#yardımcı-araçlar)
- [Yeni branch oluştur ve geçiş yap](#yeni-branch-oluştur-ve-geçiş-yap)
- [Değişiklikleri kontrol et](#değişiklikleri-kontrol-et)
- [Değişiklikleri stage et](#değişiklikleri-stage-et)
- [Commit yap](#commit-yap)
- [Branch'i remote'a gönder](#branchi-remotea-gönder)
- [Main branch'e geç ve branch'i birleştir](#main-branche-geç-ve-branchi-birleştir)
- [Local branch'i sil](#local-branchi-sil)
- [Remote branch'i sil](#remote-branchi-sil)
  - [Lisans](#lisans)

## Neden Telegram Auto Message Bot?

- **Hedef Kitleye Ulaşım**: Telegram gruplarındaki potansiyel müşterilere ve topluluk üyelerine otomatik olarak ulaşın.
- **Zaman ve Kaynak Tasarrufu**: Pazarlama ve yönetim görevlerini otomatikleştirerek zamandan ve kaynaklardan tasarruf edin.
- **Etkileşimi Artırma**: Kullanıcılarla etkileşimi artırarak topluluğunuzu daha aktif ve bağlı hale getirin.
- **Veri Odaklı Kararlar**: Detaylı raporlama ve istatistikler sayesinde pazarlama stratejilerinizi optimize edin.
- **Güvenli ve Güvenilir**: Gelişmiş güvenlik özellikleri ve hata yönetimi ile botunuzun sorunsuz çalışmasını sağlayın.

## v3.5.0'daki Yeni Özellikler

- **Kullanıcı-Grup İlişkisi**: Kullanıcıların bulunduğu grupları daha etkili takip eden gelişmiş ilişkisel veritabanı yapısı.
- **Otomatik Grup Keşfi**: Hedef grupların veritabanından dinamik olarak alınması ile manuel yapılandırma ihtiyacını azaltma.
- **Gelişmiş Davet Servisi**: Kullanıcılara periyodik davet gönderimi yapan özel davet servisi.
- **Akıllı Hız Sınırlama**: FloodWait hatalarından kaçınmak için adaptif rate limiting algoritması.
- **Daha Güçlü Veritabanı Yapısı**: Foreign key kısıtlamaları ve indeksler ile optimize edilmiş veritabanı.

## Temel Özellikler

- **Gelişmiş Otomatik Mesaj Gönderimi**:
    - Hedeflenen Telegram gruplarına otomatik ve özelleştirilmiş mesajlar gönderin.
    - Mesajları belirli zamanlarda göndermek için zamanlama özelliği kullanın.
    - Farklı hedef kitlelere yönelik mesajlar için A/B testleri yapın.
- **Akıllı Özel Mesaj Yönetimi**:
    - Yeni kullanıcılara otomatik olarak kişiselleştirilmiş davet mesajları gönderin.
    - Kullanıcıların sorularına hızlı ve etkili yanıtlar vermek için otomatik yanıtlayıcı kullanın.
    - Potansiyel müşterilerle doğrudan etkileşim kurarak satış fırsatları yaratın.
- **Güvenli Yönetici ve Kurucu Kontrolü**:
    - Botun yetkilerini ve erişimini güvenli bir şekilde yönetin.
    - Yönetici ve kurucu rolleri atayarak botun kullanımını kontrol altında tutun.
    - Yetkisiz erişimi engellemek için gelişmiş güvenlik önlemleri kullanın.
- **Detaylı Kullanıcı Veritabanı Yönetimi**:
    - Kullanıcı verilerini güvenli bir şekilde saklayın ve yönetin.
    - Kullanıcıları ilgi alanlarına, demografik özelliklerine veya davranışlarına göre segmentlere ayırın.
    - Hedefli pazarlama kampanyaları için kullanıcı verilerini kullanın.
- **Kapsamlı Loglama ve Durum Raporları**:
    - Botun tüm işlemlerini detaylı olarak kaydedin ve analiz edin.
    - Mesaj gönderim istatistikleri, kullanıcı etkileşimi ve hata raporları gibi önemli verilere erişin.
    - Veriye dayalı kararlar alarak botun performansını optimize edin.
- **Akıllı Rate Limiting ve Gecikme Sistemi**:
    - Telegram API'sinin sınırlamalarına uyum sağlayarak botun sorunsuz çalışmasını sağlayın.
    - Mesaj gönderim hızını otomatik olarak ayarlayarak spam olarak işaretlenmekten kaçının.
    - Kullanıcı deneyimini olumsuz etkilemeden etkili bir pazarlama stratejisi uygulayın.
- **Hata Yönetimi ve İzleme**:
    - Botun karşılaştığı hataları otomatik olarak tespit edin ve çözün.
    - Hata raporlarını analiz ederek botun performansını artırın.
    - Kesintisiz çalışma için proaktif önlemler alın.
- **Özelleştirilebilir Mesaj Şablonları**:
    - Markanıza ve hedef kitlenize uygun özelleştirilmiş mesaj şablonları oluşturun.
    - Mesajları daha ilgi çekici hale getirmek için resim, video ve diğer medya öğeleri ekleyin.
    - Farklı pazarlama kampanyaları için farklı şablonlar kullanın.
- **Komut Satırı Arayüzü (CLI) ile Kolay Yönetim**:
    - Botu komut satırı üzerinden kolayca yönetin ve yapılandırın.
    - Durumu kontrol edin, ayarları değiştirin ve görevleri başlatın/durdurun.
    - Teknik bilgiye sahip olmayan kullanıcılar için bile basit ve anlaşılır bir arayüz sunun.
- **Gerçek Zamanlı Durum İzleme**:
    - Botun çalışma durumu, gönderilen mesaj sayısı, hata raporları ve diğer önemli metrikleri gerçek zamanlı olarak izleyin.
    - Performansı takip ederek botun verimliliğini artırın.
    - Anormallikleri tespit ederek hızlıca müdahale edin.
- **Esnek Veritabanı Yönetimi**:
    - Kullanıcı verilerini güvenli ve verimli bir şekilde saklamak için SQLite veritabanı kullanın.
    - Veritabanını yedekleyin ve geri yükleyin.
    - Veritabanı performansını optimize edin.
- **Çoklu Dil Desteği**:
    - Botu farklı dillerde kullanın ve hedef kitlenize yerel dilde mesajlar gönderin.
    - Küresel pazarlarda etkili bir şekilde iletişim kurun.
    - Dil tercihlerini otomatik olarak algılayın ve mesajları uygun dilde gönderin.
- **Entegrasyon Kolaylığı**:
    - Diğer pazarlama ve CRM araçlarıyla kolayca entegre edin.
    - Verileri otomatik olarak senkronize edin ve iş akışlarınızı optimize edin.
    - API'ler aracılığıyla özel entegrasyonlar oluşturun.

## Gelişmiş Özellikler

- Flood kontrolü ve akıllı gecikme yönetimi
- Hata veren grupların otomatik tespiti
- Kullanıcı takibi ve veritabanı yönetimi
- Komut satırı kontrolü ve durum raporlama
- Debug bot ile ayrıntılı hata takibi ve geliştirici bilgilendirme
- Veritabanı şema otomatik güncelleme sistemi (v3.5.0)
- Kullanıcı-grup ilişkisi veritabanı yapısı (v3.5.0)

## Gereksinimler

- Python 3.7+
- Telethon kütüphanesi
- Telegram API kimlik bilgileri
- Diğer gerekli bağımlılıklar için requirements.txt dosyasına bakın

## Kurulum

1. Repository'yi klonlayın
   ```bash
   git clone [repository_url]
   ```
2. Bağımlılıkları yükleyin:
   ```bash
   pip install -r requirements.txt
   ```

3. .env dosyasını yapılandırın:
   ```bash
   API_ID=your_api_id 
   API_HASH=your_api_hash 
   PHONE_NUMBER=your_phone_number
   ```

4. Botu çalıştırın:
   ```bash
   python main.py
   ```

## Kullanım

### Temel Bot Komutları
- `p` - Duraklat/Devam et
- `s` - Durum bilgisi göster
- `c` - Konsolu temizle
- `q` - Çıkış
- `h` - Yardım mesajı

### Komut Satırı Argümanları

Bot çeşitli komut satırı argümanlarıyla çalıştırılabilir:

```bash
# Debug modunda çalıştır
python main.py --debug

# Hata veren grupları sıfırla
python main.py --reset-errors

# Veritabanı optimizasyonu yap
python main.py --optimize-db

# Geliştirici modunda çalıştır
python main.py --env development
```

Kısa form komutlar da kullanılabilir:
- `-d` = `--debug`
- `-r` = `--reset-errors`  
- `-o` = `--optimize-db`
- `-e` = `--env`
- `-b` = `--backup`

## Test Etme

Bot uygulamasını test etmek için aşağıdaki yöntemler kullanılabilir:

### 1. Manuel Test

Temel işlevleri test etmek için:
```bash
# Debug modunda çalıştırarak
python main.py --debug

# Debug modunda ve veritabanını optimize ederek
python main.py --debug --optimize-db
```

### 2. Birim Testler

Birim testleri çalıştırmak için pytest paketini yükleyin:
```bash
pip install pytest pytest-asyncio pytest-cov
```

Testleri çalıştırma:
```bash
# Tek bir test dosyasını çalıştır
pytest tests/test_user_db.py -v

# Tüm testleri çalıştır
pytest tests/ -v

# Kod kapsama raporuyla testleri çalıştır
pytest --cov=bot --cov=database tests/
```

### 3. Telegram API Testi

Telegram API testleri yaparken dikkat edilmesi gerekenler:
- Test hesabı kullanın, ana hesabınızı kullanmaktan kaçının
- Az sayıda mesaj göndererek rate limiting'e takılmaktan kaçının
- API kısıtlamalarını test etmek için küçük sayılarla başlayın

## Yapılandırma

Mesaj şablonları ve diğer ayarlar data klasöründeki JSON dosyalarında saklanır:
- `messages.json`: Gruplara gönderilen genel mesajlar
- `invites.json`: Davet mesajları ve yönlendirmeler
- `responses.json`: Yanıt şablonları

## Loglama

Tüm işlemler `logs/bot.log` dosyasında detaylı olarak kaydedilir ve aynı zamanda konsola renkli formatta gösterilir.

## Dosya Yapısı

```
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
│   ├── core.py               # Temel bot sınıfı
│   ├── tasks.py              # Bot görev yönetimi
│   └── handlers/             # Mesaj işleyicileri
│       ├── __init__.py
│       ├── group_handler.py
│       ├── message_handler.py
│       └── user_handler.py
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
```

## Yardımcı Araçlar

Proje için çeşitli yardımcı araçlar `tools/` dizini altında bulunur:

- `tools/cleanup.py`: Önbellek ve geçici dosyaları temizler
- `tools/create_session.py`: Telegram API oturumu oluşturur
- `tools/migrate_handlers.py`: Legacy kodları modernize eder
- `tools/monitor_dashboard.py`: Bot durum izleme paneli


Özet Komutlar

# Yeni branch oluştur ve geçiş yap
git checkout -b v3.4.0

# Değişiklikleri kontrol et
git status

# Değişiklikleri stage et
git add .

# Commit yap
git commit -m "v3.4.0: Yeni özellikler ve hata düzeltmeleri"

# Branch'i remote'a gönder
git push origin v3.4.0

# Main branch'e geç ve branch'i birleştir
git checkout main
git merge v3.4.0

# Local branch'i sil
git branch -d v3.4.0

# Remote branch'i sil
git push origin --delete v3.4.0


## Lisans

Bu ürün, özel ticari lisans altında dağıtılmaktadır. Kiralama modeli ile kullandırılabilir. Daha fazla bilgi için Arayiş Yazılım ile iletişime geçin.

Copyright © 2025 SiyahKare Yazılım. Tüm hakları saklıdır.