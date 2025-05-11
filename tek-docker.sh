#!/bin/bash
# Ultra minimal Docker testi
set -e

echo "=== ULTRA MİNİMAL DOCKER TESTİ ==="

# Docker imajı oluştur
echo "İmaj oluşturuluyor..."
docker build -t bot-test:latest -f Dockerfile.ultra-mini .

# Eski container'ı temizle (varsa)
docker rm -f telegram-bot-test 2>/dev/null || true

# Container'ı çalıştır
echo "Bot başlatılıyor..."
docker run --name telegram-bot-test -d bot-test:latest

# Durumu göster
echo "Container durumu:"
docker ps

# Logları göster
echo "Bot logları:"
docker logs telegram-bot-test

echo "=== TEST TAMAMLANDI ==="
echo "Logları izlemek için: docker logs -f telegram-bot-test"
echo "Container'ı durdurmak için: docker stop telegram-bot-test" 