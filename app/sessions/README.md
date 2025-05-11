# Telegram Oturum Dosyaları

Bu dizin, Telegram API ile etkileşim için kullanılan Telethon oturum dosyalarını içerir.

## Dosya Türleri

Bu dizinde üç tür dosya bulunur:

1. `.session` - Ana Telethon oturum dosyaları
2. `.session.bak` - Yedek oturum dosyaları
3. `.redirect` - Oturum yönlendirme dosyaları

## Güvenlik

Bu dosyalar oturum kimlik bilgilerini içerdiği için gitignore dosyasına eklenmelidir ve hiçbir zaman sürüm kontrolüne dahil edilmemelidir.

## Kullanım

Telethon istemcisi başlatılırken bu konumdaki oturum dosyalarını kullanmak için:

```python
from telethon import TelegramClient

# Oturum konumunu belirt
session_file = "app/sessions/telegram_session"

# İstemciyi başlat
client = TelegramClient(session_file, api_id, api_hash)
``` 