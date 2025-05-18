# Telegram Marketing Suite - Kurulum ve Kullanım Kılavuzu

## Gereksinimler
- **Node.js**: v16 veya üstü
- **npm**: Node Package Manager
- **Python**: 3.9 veya üstü
- **PostgreSQL**: Veritabanı için
- **Docker ve Docker Compose**: Çoklu hesap desteği için
- **Telegram Bot API Token**: BotFather'dan alınabilir

---

## Kurulum Adımları

### 1. Depoyu Klonlayın
```bash
git clone https://github.com/kullanici/telegram-bot.git
cd telegram-bot
```

### 2. Bağımlılıkları Yükleyin
#### Node.js Bağımlılıkları
```bash
npm install
```

#### Python Bağımlılıkları
```bash
pip install -r requirements.txt
```

### 3. Ortam Değişkenlerini Ayarlayın
`.env` dosyasını oluşturun ve aşağıdaki bilgileri ekleyin:
```
BOT_TOKEN=telegram_bot_api_token
API_ID=your_api_id
API_HASH=your_api_hash
DB_CONNECTION=postgresql://username:password@localhost:5432/telegram_bot
```

### 4. Veritabanını Ayarlayın
PostgreSQL kullanıyorsanız:
```bash
psql -U postgres -c "CREATE DATABASE telegram_bot;"
```

### 5. Docker ile Çoklu Hesap Desteği (Opsiyonel)
Docker Compose kullanarak çoklu hesap desteği için:
```bash
docker-compose up -d
```

---

## Kullanım

### Botu Başlatın
```bash
npm start
```
veya Python için:
```bash
python main.py
```

### Botu Test Edin
Telegram'da botunuzu bulun ve `/start` komutunu göndererek çalıştığını doğrulayın.

---

## Komutlar ve Argümanlar

### Temel Komutlar
- `/start`: Botu başlatır
- `/help`: Yardım mesajını gösterir

### Komut Satırı Argümanları
```bash
python main.py --debug
python main.py --reset-errors
```

---

## Sorun Giderme
- **Hata**: `ModuleNotFoundError`
  - Çözüm: `pip install -r requirements.txt` komutunu çalıştırın.
- **Veritabanı Bağlantı Sorunu**
  - Çözüm: PostgreSQL'in çalıştığını doğrulayın ve bağlantı bilgilerini kontrol edin.

---

## Ek Bilgiler
- Daha fazla bilgi için [Telegram Bot API belgelerine](https://core.telegram.org/bots/api) göz atabilirsiniz.
