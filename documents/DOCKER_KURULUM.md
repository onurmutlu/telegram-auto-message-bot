# Docker ile Telegram Bot Kurulumu

Bu döküman, Telegram Bot'unuzu Docker kullanarak nasıl kuracağınızı ve çalıştıracağınızı açıklar.

## Gereksinimler

- Docker ve Docker Compose kurulu olmalı
- Telegram API kimlik bilgileri (API_ID, API_HASH, BOT_TOKEN)

## Hızlı Başlangıç

En hızlı ve kolay yöntem, CLI tabanlı kurulum scriptimizi kullanmaktır.

```bash
# Scripti çalıştırılabilir yapın
chmod +x cli-docker-run.sh

# Scripti çalıştırın (interaktif olarak adımları takip edeceksiniz)
./cli-docker-run.sh
```

Bu script, tüm Docker kurulumunu adım adım görsel olarak yapacak ve olası hataları gösterecektir.

## Ortam Değişkenlerini Hazırlama

Bot'un çalışması için gereken değişkenleri `.env` dosyasında tanımlamalısınız:

```bash
# Örnek .env dosyasını kopyalayın ve düzenleyin
cp example.env.docker .env

# Düzenleyin
nano .env
```

## Manuel Kurulum Adımları

Eğer script çalışmazsa, aşağıdaki adımları manuel olarak uygulayabilirsiniz:

1. **Docker Ağı Oluşturma**
   ```bash
   docker network create telegram-network
   ```

2. **PostgreSQL Başlatma**
   ```bash
   docker run --name postgres-db \
       --network telegram-network \
       -e POSTGRES_USER=botuser \
       -e POSTGRES_PASSWORD=botpass \
       -e POSTGRES_DB=botdb \
       -v $(pwd)/data/postgres:/var/lib/postgresql/data \
       -p 5432:5432 \
       -d postgres:14-alpine
   ```

3. **Redis Başlatma**
   ```bash
   docker run --name redis-cache \
       --network telegram-network \
       -v $(pwd)/data/redis:/data \
       -p 6379:6379 \
       -d redis:7-alpine
   ```

4. **Bot Konteynerini Başlatma**
   ```bash
   # Önce Docker imajını oluşturun
   docker build -f Dockerfile.cli -t telegram-bot-cli:latest .

   # Sonra konteyneri başlatın
   docker run --name telegram-bot \
       --network telegram-network \
       -e API_ID="12345678" \
       -e API_HASH="abcdef1234567890abcdef1234567890" \
       -e BOT_TOKEN="1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ" \
       -e DATABASE_URL="postgresql://botuser:botpass@postgres-db:5432/botdb" \
       -e REDIS_URL="redis://redis-cache:6379/0" \
       -v $(pwd)/logs:/app/logs \
       -v $(pwd)/sessions:/app/sessions \
       -p 8000:8000 \
       -d telegram-bot-cli:latest
   ```

## Sık Karşılaşılan Sorunlar ve Çözümleri

### Docker Konteynerler Başlatılamıyor

Eğer konteynerler başlatılamıyorsa:

```bash
# Docker servisinin çalıştığından emin olun
docker info

# Eski konteynerleri tamamen temizleyin
docker stop $(docker ps -a -q)
docker rm $(docker ps -a -q)
```

### Veritabanı Bağlantı Hataları

Eğer bot veritabanına bağlanamıyorsa:

```bash
# PostgreSQL konteynerinin çalıştığından emin olun
docker ps | grep postgres

# PostgreSQL loglarını kontrol edin
docker logs postgres-db

# PostgreSQL konteynerine bağlanın
docker exec -it postgres-db psql -U botuser -d botdb
```

### Redis Bağlantı Hataları

```bash
# Redis konteynerinin çalıştığından emin olun
docker ps | grep redis

# Redis'e bağlanarak test edin
docker exec -it redis-cache redis-cli ping
```

### Bot Loglarında Hatalar

```bash
# Bot loglarını kontrol edin
docker logs telegram-bot
```

## Docker İmajlarını Yeniden Oluşturma

Bot kodunuzda değişiklik yaptıysanız, imajı yeniden oluşturmanız gerekir:

```bash
# Konteyneri durdurun
docker stop telegram-bot

# Konteyneri silin
docker rm telegram-bot

# Yeni imaj oluşturun
docker build -f Dockerfile.cli -t telegram-bot-cli:latest .

# Konteyneri yeniden başlatın
docker run --name telegram-bot [diğer parametreler...]
```

## Docker Compose ile Çalıştırma

Alternatif olarak, Docker Compose kullanabilirsiniz:

```bash
# docker-compose.yml dosyasını kullanarak başlatın
docker-compose -f docker-compose.simple.yml up -d

# Logları kontrol edin
docker-compose -f docker-compose.simple.yml logs -f
``` 