#!/bin/bash

# Docker temizleme script'i
echo "===> Docker containerları temizleniyor..."

# Mevcut konteynerler varsa durdur ve kaldır
echo "Telegram bot konteynerlerini durdurma..."
docker stop telegram-bot-staging telegram-bot-postgres-staging telegram-bot-redis-staging 2>/dev/null || true
docker rm telegram-bot-staging telegram-bot-postgres-staging telegram-bot-redis-staging 2>/dev/null || true

# Tüm durmuş konteynerleri temizle
echo "Durmuş konteynerleri temizleme..."
docker container prune -f

echo "===> Docker ağları temizleniyor..."
docker network prune -f

echo "===> Temizleme tamamlandı!" 