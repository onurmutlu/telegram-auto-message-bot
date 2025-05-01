# Telegram Bot - Birleştirilmiş Başlatma Sistemi

Bu klasör, Telegram botunun farklı ortamlarda (yerel, Docker, Docker Compose) tutarlı ve tek bir yöntemle çalıştırılabilmesi için gerekli tüm dosyaları içerir.

## Dosya Yapısı

- `main.py`: Birleştirilmiş ana bot modülü
- `run.py`: Kolay başlatma scripti (farklı modlarda başlatmak için)
- `Dockerfile`: Docker imajı oluşturma yapılandırması
- `docker-compose.yml`: Docker Compose yapılandırması
- `telegram-bot.service`: Linux sistemlerde systemd servis dosyası

## Yerel Başlatma

Botu doğrudan yerel olarak çalıştırmak için:

```bash
# Temel çalıştırma
python unified/run.py

# Debug modunda
python unified/run.py --debug

# Belirli bir servisi başlatmak için
python unified/run.py --service=grup
```

## Docker ile Çalıştırma

Docker kullanarak çalıştırmak için:

```bash
# İmaj oluştur ve başlat
python unified/run.py --mode=docker --build

# Arka planda çalıştır
python unified/run.py --mode=docker --detach

# Debug modunda
python unified/run.py --mode=docker --debug
```

## Docker Compose ile Çalıştırma

Docker Compose kullanarak çalıştırmak için:

```bash
# İmaj oluştur ve başlat
python unified/run.py --mode=docker-compose --build

# Arka planda çalıştır
python unified/run.py --mode=docker-compose --detach
```

## Sistem Servisi Olarak Kurulum

Linux sistemlerde otomatik başlatma için:

1. Servis dosyasını kopyalayın:
   ```bash
   sudo cp unified/telegram-bot.service /etc/systemd/system/
   ```

2. Servis dosyasını düzenleyin (kullanıcı, grup ve dizinleri düzenleyin):
   ```bash
   sudo nano /etc/systemd/system/telegram-bot.service
   ```

3. Sistemd'yi yenileyin ve servisi etkinleştirin:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable telegram-bot.service
   ```

4. Servisi başlatın:
   ```bash
   sudo systemctl start telegram-bot.service
   ```

5. Durumu kontrol edin:
   ```bash
   sudo systemctl status telegram-bot.service
   ```

## Parametreler

Tüm modlarda kullanılabilecek genel parametreler:

- `--debug`: Debug modunu etkinleştirir
- `--clean`: Başlamadan önce temizlik yapar
- `--config=DOSYA`: Belirli bir yapılandırma dosyası kullanır
- `--service=SERVIS`: Belirli bir servisi başlatır (grup, mesaj, davet)

Docker-özel parametreler:

- `--build`: Docker imajını yeniden oluşturur
- `--detach`, `-d`: Arkaplanda çalıştırır

## Çevre Değişkenleri

Aşağıdaki çevre değişkenleri .env dosyasında tanımlanmalıdır:

```
API_ID=12345
API_HASH=your_api_hash
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
BOT_TOKEN=your_bot_token
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=telegram_bot
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
``` 