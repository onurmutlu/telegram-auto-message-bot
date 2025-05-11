# Servis Yönetimi

Telegram Bot, birden çok servisi yöneten modüler bir mimari üzerine kurulmuştur. Bu sayfada, servis yönetiminin temel konseptlerini ve kullanımını bulabilirsiniz.

## Servis Mimarisi

Sistem aşağıdaki temel servislerden oluşur:

- **ServiceManager**: Tüm servislerin yaşam döngülerini yöneten ana bileşen
- **Client Service**: Telegram hesaplarını yöneten servis
- **Scheduler Service**: Zamanlanmış görevleri ve mesajları yöneten servis
- **API Service**: HTTP API ve web paneli sunan servis
- **Analytic Service**: Kullanım verilerini toplayan ve analiz eden servis

## ServiceManager Kullanımı

ServiceManager, tüm servislerin merkezi bir noktadan yönetilmesini sağlar.

### ServiceManager Örneği Oluşturma

```python
from app.services.service_manager import ServiceManager

# Service Manager'ı başlat
service_manager = ServiceManager()

# Servisleri kaydet
service_manager.register_service('client', ClientService())
service_manager.register_service('scheduler', SchedulerService())
```

### Servisleri Başlatma ve Durdurma

```python
# Tüm servisleri başlat
service_manager.start_all()

# Belirli bir servisi başlat
service_manager.start_service('client')

# Tüm servisleri durdur
service_manager.stop_all()

# Belirli bir servisi durdur
service_manager.stop_service('scheduler')
```

### Servis Durumu Kontrolü

```python
# Bir servisin durumunu kontrol et
status = service_manager.get_service_status('client')
print(f"Client servisi: {status}")

# Tüm servislerin durumunu görüntüle
all_statuses = service_manager.get_all_service_statuses()
for service_name, status in all_statuses.items():
    print(f"{service_name}: {status}")
```

## ServiceWrapper Kullanımı

`ServiceWrapper`, ServiceManager'ı saran ve daha basit bir arayüz sunan yardımcı bir sınıftır.

```python
from app.services.service_wrapper import ServiceWrapper

# ServiceWrapper başlat
wrapper = ServiceWrapper()

# Tüm servisleri başlat
wrapper.start()

# Durumları görüntüle
wrapper.show_status()

# Bir servisi yeniden başlat
wrapper.restart('client')

# Tüm servisleri durdur
wrapper.stop()
```

## CLI ile Servis Yönetimi

Komut satırı arayüzü ile servisleri yönetebilirsiniz:

```bash
# Tüm servisleri başlat
python -m app.cli start all

# Belirli bir servisi başlat
python -m app.cli start client

# Servislerin durumunu görüntüle
python -m app.cli status

# Belirli bir servisi durdur
python -m app.cli stop scheduler

# Tüm servisleri durdur
python -m app.cli stop all
```

## Özel Servislerin Oluşturulması

Kendi özel servisinizi oluşturmak için `BaseService` sınıfından türetmeniz gerekir:

```python
from app.services.base_service import BaseService

class MyCustomService(BaseService):
    def __init__(self):
        super().__init__(name="custom", depends_on=["client"])
        self.is_running = False

    async def start(self):
        # Servis başlatma işlemleri
        self.is_running = True
        self.logger.info("Custom servis başlatıldı")
        return True

    async def stop(self):
        # Servis durdurma işlemleri
        self.is_running = False
        self.logger.info("Custom servis durduruldu")
        return True

    async def status(self):
        # Servis durumu
        return {
            "running": self.is_running,
            "healthy": self.is_running
        }
```

## Servis Bağımlılıkları

Servisler, `depends_on` parametresi ile diğer servislere bağımlı olabilir. ServiceManager, bağımlılık sırasına göre servisleri başlatır ve durdurur:

```python
# Scheduler, client servisine bağımlı
scheduler = SchedulerService(depends_on=["client"])

# Service Manager bağımlılık sırasını otomatik hesaplar
service_manager.register_service('client', ClientService())
service_manager.register_service('scheduler', scheduler)

# Client servisi önce başlatılır, sonra scheduler
service_manager.start_all()
```

## Servis Yapılandırması

Servisler, yapılandırma parametrelerini alabilir:

```python
# Yapılandırma ile servis oluşturma
client_config = {
    "session_name": "my_session",
    "api_id": 12345,
    "api_hash": "your_api_hash"
}

client = ClientService(config=client_config)
service_manager.register_service('client', client)
```

## Hata İşleme

Servislerde hata olduğunda, ServiceManager hataları log'lar ve gerekirse yeniden başlatma dener:

```python
# Hata toleransını yapılandır
service_manager.configure(
    max_retries=3,                  # Maksimum yeniden deneme sayısı
    retry_interval=5,               # Yeniden denemeler arası saniye
    auto_restart_failed=True,       # Başarısız servisleri otomatik yeniden başlat
    graceful_shutdown_timeout=10    # Düzgün kapatma için saniye
)

# Hata durumunda geri çağırma 
def on_service_error(service_name, error):
    print(f"Servis hatası: {service_name} - {error}")

service_manager.on_error = on_service_error
```

## İleri Düzey Kullanım

ServiceManager, daha karmaşık servis yapılandırmaları için gelişmiş seçenekler sunar:

```python
# Asenkron olarak servisleri başlat
await service_manager.start_all_async()

# Belirli servisleri başlat
service_manager.start_services(['client', 'scheduler'])

# Servis sağlığını kontrol et
health = await service_manager.check_health()
for service_name, health_info in health.items():
    print(f"{service_name}: {'Sağlıklı' if health_info['healthy'] else 'Sağlıksız'}")
``` 