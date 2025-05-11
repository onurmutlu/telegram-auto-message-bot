# Başlangıç

Bu bölümde Telegram Bot'un kurulumu ve çalıştırılması için adım adım rehber bulabilirsiniz.

## Gereksinimler

Telegram Bot'u çalıştırmak için gereken temel gereksinimler:

- Python 3.10+
- PostgreSQL 14+
- Docker ve Docker Compose (opsiyonel, ama önerilen)
- Git

Detaylı gereksinimler listesi için [Gereksinimler](gereksinimler.md) sayfasına bakabilirsiniz.

## Kurulum Seçenekleri

Telegram Bot'u kurmanın iki ana yöntemi vardır:

1. **Docker ile Kurulum** (Önerilen): Tüm bağımlılıkları ve servisleri tek bir komutla çalıştırabilirsiniz.
2. **Manuel Kurulum**: Gereksinimleri manuel olarak kurup yapılandırabilirsiniz.

## Docker ile Kurulum

### 1. Repo'yu Klonlayın

```bash
git clone https://github.com/username/telegram-bot.git
cd telegram-bot
```

### 2. Ortam Değişkenleri Oluşturun

```bash
cp .env.example .env
nano .env  # Gerekli değişkenleri yapılandırın
```

### 3. Docker Compose ile Çalıştırın

```bash
docker-compose up -d
```

Tüm servisler otomatik olarak başlatılacak ve birbirine bağlanacaktır.

## Manuel Kurulum

### 1. Repo'yu Klonlayın

```bash
git clone https://github.com/username/telegram-bot.git
cd telegram-bot
```

### 2. Virtual Environment Oluşturun

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# veya
.venv\Scripts\activate     # Windows
```

### 3. Bağımlılıkları Yükleyin

```bash
pip install -e .  # Development modunda kurar
# veya
pip install -r requirements.txt
```

### 4. PostgreSQL Veritabanı Kurun

PostgreSQL'i yükleyip çalıştırdıktan sonra bir veritabanı oluşturun:

```bash
createdb telegram_bot
```

### 5. Ortam Değişkenleri Oluşturun

```bash
cp .env.example .env
nano .env  # Gerekli değişkenleri yapılandırın
```

### 6. Veritabanı Migrasyonları Çalıştırın

```bash
alembic upgrade head
```

### 7. Uygulamayı Çalıştırın

```bash
python -m app.launch
```

## İlk Kurulum Sonrası Yapılması Gerekenler

1. Web arayüzüne giriş yapın: `http://localhost:8000/api/docs`
2. Telegram hesaplarınızı ekleyin ve yapılandırın
3. Servisleri kontrol edin ve başlatın

Daha detaylı bilgi için [Temel Kullanım](../kullanim/temel.md) bölümüne bakabilirsiniz. 