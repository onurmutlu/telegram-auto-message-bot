"""
Şablon yükleme komutları
"""
import os
import sys
import logging
import asyncio
import importlib
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

async def load_templates():
    """Şablonları yükler"""
    try:
        # Yükleme script'ini çalıştır
        script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "load_templates.py")
        
        if not os.path.exists(script_path):
            logger.error(f"Şablon yükleme script'i bulunamadı: {script_path}")
            return False, f"Şablon yükleme script'i bulunamadı: {script_path}"
        
        # Doğrudan modülü içe aktarmak yerine Python ile script'i çalıştır
        logger.info(f"Şablon yükleme script'i çalıştırılıyor: {script_path}")
        
        # Python yorumlayıcısının yolunu al
        python_executable = sys.executable
        
        # Şablon yükleme script'ini çalıştır
        result = subprocess.run(
            [python_executable, script_path],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logger.info("Şablonlar başarıyla yüklendi.")
            output = result.stdout.strip() or "Şablonlar başarıyla yüklendi."
            return True, output
        else:
            error = result.stderr.strip()
            logger.error(f"Şablon yükleme hatası: {error}")
            return False, f"Şablon yükleme hatası: {error}"
        
    except Exception as e:
        logger.error(f"Şablon yükleme işlemi sırasında hata: {e}")
        return False, f"Hata: {str(e)}"

def run_templates():
    """CLI için templates çalıştırıcı"""
    result, message = asyncio.run(load_templates())
    
    if result:
        print("\033[92m" + message + "\033[0m")  # Yeşil
    else:
        print("\033[91m" + message + "\033[0m")  # Kırmızı
    
    return result 