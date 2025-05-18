# Telegram Kimlik Doğrulama ve Bot Başlatma Fix

Bu güncellemeler, Telegram botunuzun doğrulama kodu ve 2FA işlemlerini daha güvenilir şekilde yapabilmesini sağlar.

## Yapılan İyileştirmeler

1. **Güvenilir Input Mekanizması**: Standart input yanında dosyadan da girdi alabilen bir sistem eklendi. Bu, hem interaktif hem de otomatik mod için çalışır.

2. **Geçici Dosya Desteği**: Kimlik doğrulama kodları ve 2FA şifreleri için hem ortam değişkenleri hem de geçici dosyalar kullanılabilir.

3. **Oturum İzleme İyileştirmesi**: Bot başlatma sırasında süreç çıktıları daha etkili bir şekilde izleniyor.

4. **Yeni Test Aracı**: `test_auth.py` ile Telegram kimlik doğrulaması kolayca test edilebilir.

## Kullanım

### Doğrulama Kodu ve 2FA ile Bot Başlatma

```bash
# Normal interaktif mod
./start_auto.sh

# Doğrulama kodu ile
./start_auto.sh -c "123456"

# Doğrulama kodu ve 2FA şifresi ile
./start_auto.sh -c "123456" -p "gizlişifre"
```

### Kimlik Doğrulama Testi

```bash
# İnteraktif test
./test_auth.py

# Doğrulama kodu ile test
./test_auth.py --code "123456"

# Tam test
./test_auth.py --phone "+905382617727" --code "123456" --password "gizlişifre"
```

## Dosyadan Doğrulama Kodu/Şifre Gönderme

Bir terminal penceresinde botu çalıştırın:
```bash
./start_auto.sh
```

Diğer terminal penceresinde, doğrulama kodunu gönderin:
```bash
echo "123456" > ./.telegram_auth_code
```

2FA şifresi gerekirse:
```bash
echo "gizlişifre" > ./.telegram_2fa_password
```

## Sorun Giderme

1. İki farklı terminal penceresi açın: biri botu başlatmak için, diğeri doğrulama kodunu girmek için
2. Onay kodu almanızdan hemen sonra doğrulama kodunuzu `.telegram_auth_code` dosyasına yazın
3. Bot hala oturum açıyorsa, süreci durdurup (Ctrl+C) tekrar başlatın
4. Debug için `bot_autostart.log` dosyasını kontrol edin
