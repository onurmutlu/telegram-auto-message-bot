#!/bin/bash

set -e

# Değişkenleri kontrol et
host=${1:-"localhost"}
port=${2:-5432}
shift 2

# Eğer argümanlar arasında --timeout varsa
timeout=15
if [[ "$1" == "--timeout" ]]; then
  timeout="$2"
  shift 2
fi

if [[ "$1" != "--" ]]; then
  echo "Beklenmeyen format: host:port -- komut şeklinde kullanın"
  exit 1
fi
shift 1

# Komutu oluştur
cmd="$@"

# Bilgilendirme
echo "Servis bekleniyor: $host:$port (timeout: ${timeout}s)"

# Sayacı başlat
elapsed=0
while [ $elapsed -lt $timeout ]; do
    nc -z "$host" "$port" > /dev/null 2>&1
    result=$?
    if [ $result -eq 0 ]; then
        echo "Servis hazır: $host:$port"
        
        # Ayrıca eğer postgres ise, pg_isready ile de kontrol edelim
        if [ "$port" == "5432" ]; then
            until PGPASSWORD=$POSTGRES_PASSWORD pg_isready -h "$host" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t 1; do
                echo "PostgreSQL hala hazırlanıyor - biraz daha bekleyelim..."
                sleep 1
                elapsed=$((elapsed+1))
            done
        fi
        
        # Eğer redis ise, ping ile kontrol edelim
        if [ "$port" == "6379" ]; then
            until redis-cli -h "$host" ping; do
                echo "Redis hala hazırlanıyor - biraz daha bekleyelim..."
                sleep 1
                elapsed=$((elapsed+1))
            done
        fi
        
        echo "Bağlantı kuruldu, komutu çalıştırılıyor: $cmd"
        exec $cmd
    fi
    sleep 1
    elapsed=$((elapsed+1))
    echo "Hala bekleniyor... ($elapsed/$timeout)"
done

echo "Zaman aşımı: $host:$port servisi $timeout saniye içinde hazır olmadı"
exit 1 