# Telegram Bot Kullanım Kılavuzu

Bu belge, Telegram Bot'u kurma, çalıştırma ve yönetme süreçlerini açıklar.

## İçindekiler

1. [Giriş](#giriş)
2. [Kurulum](#kurulum)
3. [Bot Çalıştırma](#bot-çalıştırma)
4. [CLI Kullanımı](#cli-kullanımı)
5. [Servislerin Yönetimi](#servislerin-yönetimi)
6. [Otomatik Mesajlaşma](#otomatik-mesajlaşma)
7. [Sorun Giderme](#sorun-giderme)

## Giriş

Bu Telegram Bot, gruplar ve kullanıcılarla otomatik etkileşim sağlayan, aktivite izleyen ve çeşitli servisler sunan gelişmiş bir araçtır. Bot modüler bir yapıya sahiptir ve farklı servisler ekleyerek/çıkararak özelleştirilebilir.

## Kurulum

### Gereksinimler

- Python 3.9+
- pip veya pip3
- Telegram API anahtarları (API_ID, API_HASH)
- Telegram hesabı

### Adımlar

1. Depoyu klonlayın:
   ```
   git clone https://github.com/kullanici/telegram-bot.git
   cd telegram-bot
   ```

2. Sanal ortam oluşturun ve etkinleştirin:
   ```
   python -m venv .venv
   source .venv/bin/activate  # Linux/Mac
   # VEYA
   .venv\Scripts\activate     # Windows
   ```

3. Bağımlılıkları yükleyin:
   ```
   pip install -r requirements.txt
   ```

4. `.env` dosyasını oluşturun:
   ```
   cp .env.example .env
   ```

5. `.env` dosyasını düzenleyin ve API kimlik bilgilerinizi ekleyin:
   ```
   API_ID=123456
   API_HASH=your_api_hash
   SESSION_NAME=telegram_session
   ```

## Bot Çalıştırma

Bot'u iki yolla çalıştırabilirsiniz: CLI arayüzü ile veya doğrudan başlatma betiğiyle.

### CLI Arayüzü ile Çalıştırma (Önerilen)

CLI arayüzü, tüm bot işlemlerini yönetmek için interaktif bir arabirim sağlar:

```
./bot_cli.py
```

### Doğrudan Betik ile Çalıştırma

Bu seçenek, bot'u arka planda veya ön planda çalıştırmanızı sağlar:

```
# Ön planda çalıştırma
./start.sh

# Arka planda çalıştırma
./start.sh --background
```

Bot'u durdurmak için:

```
./stop.sh
```

## CLI Kullanımı

CLI arayüzü, aşağıdaki işlevleri sağlar:

- Telegram hesabına giriş yapma
- Bot'u başlatma/durdurma
- Dashboard'u açma
- Servis durumunu izleme
- Mesajlaşma ayarlarını yapılandırma

## Servislerin Yönetimi

Bot, aşağıdaki servisleri içerir:

- **DirectMessageService**: Özel mesajları yönetir
- **PromoService**: Tanıtım mesajlarını yönetir
- **EngagementService**: Gruplara otomatik mesajlar gönderir
- **ActivityService**: Aktiviteleri izler
- **HealthService**: Bot sağlığını izler

## Otomatik Mesajlaşma

Bot, gruplara otomatik mesajlar göndererek etkileşimi artırabilir. Bu özelliği yapılandırmak için:

1. CLI'yı başlatın: `./bot_cli.py`
2. Ana menüden "Mesajlaşma Ayarları"nı seçin
3. Otomatik mesajlaşmayı etkinleştirin ve aralık belirleyin

Veya `.env` dosyasında aşağıdaki değişkenleri ayarlayın:

```
AUTO_ENGAGE=True
ENGAGE_INTERVAL=1  # Saat cinsinden
ENGAGE_MODE=Grup aktivitesine göre
```

## Sorun Giderme

### Bot Bağlantı Sorunları

Telegram API bağlantı sorunları yaşıyorsanız:

1. `.env` dosyasındaki API kimlik bilgilerini kontrol edin
2. `fix_bot.sh` scriptini çalıştırın: `./fix_bot.sh`
3. Logları kontrol edin: `cat bot_output.log`

### Oturum Sorunları

Telegram oturum sorunları yaşıyorsanız:

1. CLI aracını kullanarak yeniden giriş yapın: `./bot_cli.py`
2. Veya oturum dosyalarını temizleyin: `rm app/sessions/telegram_session.*`
3. Ardından botu yeniden başlatın

### Otomasyon Hataları

Eğer otomatik mesajlaşma çalışmıyorsa:

1. `.env` dosyasında `AUTO_ENGAGE=True` olduğunu kontrol edin
2. Log dosyalarını inceleyin: `tail -f bot.log`
3. Botun bir gruba ekli olduğundan emin olun 