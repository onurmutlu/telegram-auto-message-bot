#!/usr/bin/env python
import sys
import os

# Proje kök dizinini Python yoluna ekle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Ana modülü içe aktar
from app import main

# Ana uygulamayı başlat
if __name__ == "__main__":
    print("Telegram Bot başlatılıyor...")
    
    # Çevre değişkenlerini production moduna ayarla
    os.environ["ENV"] = "production"
    os.environ["DEBUG"] = "false"
    
    # Windows için asyncio ayarı
    if sys.platform == 'win32':
        import asyncio
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # AsyncIO event loop al
    import asyncio
    loop = asyncio.get_event_loop()
    
    try:
        # Ana uygulamayı başlat
        loop.run_until_complete(main.main())
    except KeyboardInterrupt:
        print("\nBot kullanıcı tarafından durduruldu.")
    except Exception as e:
        print(f"Kritik hata: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        print("Uygulama kapatılıyor...")
        loop.close()
