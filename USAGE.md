# Telegram Bot Kullanım Kılavuzu

Bu belge, Telegram bot'unuzun otomatik başlatılması ve çalıştırılması için gereken adımları ve yönergeleri içerir.

## Bot'u Başlatmak İçin

### 1. Standart Başlatma (İnteraktif Kimlik Doğrulama)

Eğer bot'u standart modda başlatmak istiyorsanız, aşağıdaki komutu kullanın:

```bash
./start_auto.sh
```

Bu komut, gerektiğinde size Telegram doğrulama kodunu ve varsa 2FA şifresini soracaktır.

### 2. Doğrulama Kodu İle Otomatik Başlatma

Eğer Telegram'dan alacağınız doğrulama kodunu önceden biliyorsanız, aşağıdaki şekilde parametreyle başlatabilirsiniz:

```bash
./start_auto.sh -c "DOĞRULAMA_KODU"
```

### 3. Doğrulama Kodu ve 2FA Şifresi İle Otomatik Başlatma

Hem doğrulama kodu hem de 2FA şifrenizi biliyorsanız:

```bash
./start_auto.sh -c "DOĞRULAMA_KODU" -p "2FA_ŞİFRESİ"
```

## Bot'u Durdurmak İçin

Bot'u durdurmak için aşağıdaki komutu kullanın:

```bash
./stop_auto.sh
```

## Bot'un Durumunu Kontrol Etmek İçin

Bot'un bağlantı durumunu ve grup bilgilerini kontrol etmek için:

```bash
python simple_bot_check.py
```

## Gruplara Mesaj Göndermek ve Listelemek İçin

Telegram gruplarını listelemek için:

```bash
python test_telegram_groups.py --only-list
```

Belirli bir gruba mesaj göndermek için:

```bash
python test_telegram_groups.py --message "Mesajınız" --target GRUP_INDEKSI
```

## Otomatik Başlatma Kaydı

Bot'u sistem başlangıcında otomatik olarak başlatmak için:

```bash
./install_autostart.sh
```

## Sorun Giderme

1. Eğer bot kimlik doğrulama hatası veriyorsa:
   - `.env` dosyasında doğru API kimlik bilgilerinizin olduğundan emin olun
   - Oturum dosyalarının silinmiş olup olmadığını kontrol edin
   - Gerekirse `app/sessions` dizinindeki oturum dosyalarını silin ve yeniden yetkilendirin

2. Bot bağlantı kuramıyorsa:
   - İnternet bağlantınızı kontrol edin
   - Telethon kütüphanesinin en son sürümde olduğundan emin olun: `pip install telethon --upgrade`
   - IP adresinizin Telegram API tarafından engellenmiş olmadığından emin olun

3. 2FA sorunları için:
   - Doğru 2FA şifresini girdiğinizden emin olun
   - Şifrenizi yeniden ayarlamanız gerekebilir
