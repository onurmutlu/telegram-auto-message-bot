# Docker Çoklu Hesap Desteği

Bu doküman, Telegram Bot'un Docker kullanılarak çoklu hesap desteği ile nasıl çalıştırılacağını açıklar.

## Özellikler

- Her müşteri için ayrı bir Docker container oluşturulur.
- Her container, müşteri ID'sine göre yapılandırılır.
- Müşteri bazlı oturum dosyaları ve yapılandırma dosyaları desteklenir.
- PostgreSQL üzerinde müşteri bazlı şema desteği sağlanır.

---

## Yapılandırma

### 1. Ortam Değişkenleri

Her müşteri için `CUSTOMER_ID` ortam değişkeni kullanılır. Örnek:

```bash
CUSTOMER_ID=customer1