#!/bin/sh\necho "Dosyalar düzeltiliyor..."\ncp bot/services/gpt_service.py.backup  bot/services/gpt_service.py 2>/dev/null || cp -f bot/services/gpt_service.py bot/services/gpt_service.py.backup\ncat > bot/services/gpt_service.py << "EOF"\n\n"""OpenAI GPT entegrasyonu için basit servis."""\nimport logging\nfrom bot.services.base_service import BaseService\nlogger = logging.getLogger(__name__)\n\nclass GptService(BaseService):\n    """Basit OpenAI GPT entegrasyonu."""\n    \n    def __init__(self, client, config, db, stop_event=None):\n        """GptService başlatıcısı."""\n        super().__init__(\"gpt\", client, config, db, stop_event)\n        logger.info(\"GPT servisi başlatıldı\")\n    \n    async def initialize(self):\n        """Servisi başlatmadan önce hazırlar."""\n        await super().initialize()\n        return True\n        \n    async def run(self):\n        """Servisin ana çalışma döngüsü."""\n        logger.info(\"GPT servisi çalışıyor (pasif mod)\")\n        while self.running:\n            if self.stop_event.is_set():\n                break\n            await asyncio.sleep(60)\n    \n    async def get_status(self):\n        """Servisin mevcut durumunu döndürür."""\n        status = await super().get_status()\n        status.update({\n            \"service_type\": \"gpt\",\n            \"name\": \"GPT Servisi\",\n            \"active\": False,\n            \"api_available\": False,\n            \"status\": \"API Key yok - GPT devre dışı\"\n        })\n        return status\nEOF\necho "import asyncio satırı ekleniyor..."\nsed -i  1s/^/import asyncio\n/ bot/services/gpt_service.py\necho "Düzeltme tamamlandı."\n
